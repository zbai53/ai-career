from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

app = FastAPI(title="AI Career Agent Service")


@app.get("/health")
async def health():
    return {"status": "ok"}
