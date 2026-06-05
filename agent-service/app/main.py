import os
from dotenv import load_dotenv

load_dotenv()

import anthropic
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="AI Career Agent Service")

_MODEL = "claude-haiku-4-5-20251001"


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
