from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import ApiEnvelope, make_id
from app.office.router import router as office_router

app = FastAPI(title="AgentsOffice", version="0.1.0")
app.include_router(office_router, prefix="/api/v1/office", tags=["AgentsOffice"])

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# 主静态文件目录
app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")
# 单独挂载 office 目录以支持 /static/office/ 自动返回 index.html
app.mount("/static/office", StaticFiles(directory=STATIC_DIR / "office", html=True), name="static_office")


def envelope(trace_id: str, data: dict, error: Optional[str] = None) -> ApiEnvelope:
    return ApiEnvelope(trace_id=trace_id, request_id=make_id("req"), data=data, error=error)


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/v1/health")
def health() -> ApiEnvelope:
    trace_id = make_id("trc")
    return envelope(trace_id=trace_id, data={"status": "ok"})
