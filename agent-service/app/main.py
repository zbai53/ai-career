import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import anthropic
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse

from app.agents.resume_agent import ResumeAgent, UnsupportedFileTypeError, TextExtractionError, ResumeParseError

app = FastAPI(title="AI Career Agent Service")

_MODEL = "claude-haiku-4-5-20251001"
_ALLOWED_SUFFIXES = {".pdf", ".docx"}


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
        result = agent.parse(tmp_path)
        return result.model_dump()

    except UnsupportedFileTypeError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except (TextExtractionError, ResumeParseError) as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Unexpected error: {exc}"})
    finally:
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink()
