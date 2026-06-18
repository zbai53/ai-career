import os
import tempfile
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import anthropic
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.agents.resume_agent import ResumeAgent, UnsupportedFileTypeError, TextExtractionError, ResumeParseError
from app.agents.jd_agent import JDAgent, JDFetchError, JDParseError
from app.agents.match_agent import MatchAgent
from app.graph.workflow import get_workflow_state, run_workflow
from app.models.job_description import ParsedJobDescription
from app.models.resume import ParsedResume

app = FastAPI(title="AI Career Agent Service")

_MODEL = "claude-haiku-4-5-20251001"
_ALLOWED_SUFFIXES = {".pdf", ".docx"}


class JDParseRequest(BaseModel):
    text: Optional[str] = None
    url: Optional[str] = None


class MatchRequest(BaseModel):
    resume: dict
    jd: dict


class WorkflowRunRequest(BaseModel):
    user_id: str
    resume_file_path: Optional[str] = None
    jd_text: Optional[str] = None
    thread_id: Optional[str] = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/llm")
async def health_llm():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse(
            status_code=503,
            content={"status": "llm-unavailable", "error": "ANTHROPIC_API_KEY is not set"},
        )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=_MODEL,
            max_tokens=16,
            messages=[{"role": "user", "content": "Respond with only: ok"}],
        )
        return {"status": "ok", "model": message.model}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "llm-unavailable", "error": str(e)},
        )


@app.post("/api/resume/parse")
async def parse_resume(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Unsupported file type '{suffix}'. Upload a .pdf or .docx file."
            },
        )

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        agent = ResumeAgent()
        result, agent_run = agent.parse(tmp_path)
        return {**result.model_dump(), "agent_run": agent_run}

    except UnsupportedFileTypeError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except (TextExtractionError, ResumeParseError) as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Unexpected error: {exc}"})
    finally:
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink()


@app.post("/api/jd/parse")
async def parse_jd(body: JDParseRequest):
    if not body.text and not body.url:
        return JSONResponse(
            status_code=400,
            content={"error": "Provide at least one of 'text' or 'url'."},
        )
    try:
        agent = JDAgent()
        if body.text:
            result, agent_run = agent.parse_text(body.text)
        else:
            result, agent_run = agent.parse_url(body.url)
        return {**result.model_dump(), "agent_run": agent_run}
    except JDFetchError as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    except JDParseError as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Unexpected error: {exc}"})


@app.post("/api/match")
async def match_resume_to_jd(body: MatchRequest):
    try:
        resume = ParsedResume.model_validate(body.resume)
        jd = ParsedJobDescription.model_validate(body.jd)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": f"Validation failed: {exc}"})

    try:
        agent = MatchAgent()
        result, agent_run = agent.match(resume, jd)
        return {**result.model_dump(), "agent_run": agent_run}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Match failed: {exc}"})


@app.post("/api/workflow/run")
async def workflow_run(body: WorkflowRunRequest):
    """
    Invoke the full LangGraph workflow and return the final state.

    Accepts pre-parsed inputs:
      - resume_file_path: path to an uploaded .pdf/.docx file (triggers ResumeAgent)
      - jd_text: raw JD text or URL (triggers JDAgent)

    The workflow runs to completion (or error) before this endpoint returns.
    Use thread_id to namespace the checkpoint — defaults to user_id.
    """
    try:
        final_state = run_workflow(
            user_id=body.user_id,
            resume_file_path=body.resume_file_path,
            jd_text=body.jd_text,
            thread_id=body.thread_id,
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Workflow failed: {exc}"},
        )

    if final_state.get("error"):
        return JSONResponse(
            status_code=500,
            content={"error": final_state["error"]},
        )

    return final_state


@app.get("/api/workflow/status/{thread_id}")
async def workflow_status(thread_id: str):
    """
    Return the current checkpoint state for a running or completed workflow.

    Useful for polling progress from the frontend or Spring Boot.
    Returns current_step, next pending nodes, and any available results.
    """
    try:
        snap = get_workflow_state(thread_id)
    except Exception as exc:
        return JSONResponse(
            status_code=404,
            content={"error": f"No checkpoint found for thread_id '{thread_id}': {exc}"},
        )

    state_values = snap["values"]
    return {
        "thread_id":    thread_id,
        "current_step": state_values.get("current_step"),
        "next":         snap["next"],
        "is_complete":  len(snap["next"]) == 0,
        "error":        state_values.get("error"),
        "match_result": state_values.get("match_result"),
        "agent_runs":   len(state_values.get("agent_runs") or []),
        "created_at":   snap["created_at"],
    }


@app.post("/api/agent-runs")
async def receive_agent_run(body: dict):
    """
    Passthrough endpoint for agent-run records.

    Accepts an agent_run dict (as produced by log_agent_run) and returns it
    as-is. The caller (Spring Boot) is responsible for persisting the record.
    """
    return body
