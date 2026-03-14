from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import (
    ApiEnvelope,
    ComparisonRunRequest,
    ComparisonTaskCreateRequest,
    ComparisonTaskRecord,
    CourseCreateRequest,
    CourseRecord,
    EvaluateAttemptRequest,
    GenerateContentRequest,
    TaskRecord,
    TrainingAttemptCreateRequest,
    TrainingAttemptRecord,
    make_id,
)
from app.office.router import router as office_router
from app.services.orchestrator import orchestrator
from app.store import store

app = FastAPI(title="Ecommerce AI Lab Prototype", version="0.1.0")
app.include_router(office_router, prefix="/api/v1/office", tags=["AgentsOffice"])

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def envelope(trace_id: str, data: dict, error: Optional[str] = None) -> ApiEnvelope:
    return ApiEnvelope(trace_id=trace_id, request_id=make_id("req"), data=data, error=error)


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/v1/health")
def health() -> ApiEnvelope:
    trace_id = make_id("trc")
    return envelope(trace_id=trace_id, data={"status": "ok"})


@app.post("/api/v1/training/courses")
def create_course(payload: CourseCreateRequest) -> ApiEnvelope:
    trace_id = make_id("trc")
    course = CourseRecord(course_id=make_id("course"), **payload.model_dump())
    store.put_course(course)
    return envelope(trace_id=trace_id, data={"course_id": course.course_id, "status": "draft"})


@app.post("/api/v1/training/courses/{course_id}:generate-content")
def generate_training_content(
    course_id: str,
    payload: GenerateContentRequest,
    background_tasks: BackgroundTasks,
) -> ApiEnvelope:
    trace_id = make_id("trc")
    if store.get_course(course_id) is None:
        raise HTTPException(status_code=404, detail="course not found")

    task = TaskRecord(
        task_id=make_id("task"),
        trace_id=trace_id,
        task_type="training.generate_content",
        input={"course_id": course_id, **payload.model_dump()},
    )
    store.put_task(task)
    background_tasks.add_task(orchestrator.run_training_content_task, task.task_id, course_id, payload.scene)
    return envelope(trace_id=trace_id, data={"task_id": task.task_id, "status": task.status})


@app.post("/api/v1/training/attempts")
def create_training_attempt(payload: TrainingAttemptCreateRequest) -> ApiEnvelope:
    trace_id = make_id("trc")
    if store.get_course(payload.course_id) is None:
        raise HTTPException(status_code=404, detail="course not found")

    attempt = TrainingAttemptRecord(attempt_id=make_id("attempt"), **payload.model_dump())
    store.put_training_attempt(attempt)
    return envelope(trace_id=trace_id, data={"attempt_id": attempt.attempt_id, "status": "submitted"})


@app.post("/api/v1/training/attempts/{attempt_id}:evaluate")
def evaluate_training_attempt(
    attempt_id: str,
    payload: EvaluateAttemptRequest,
    background_tasks: BackgroundTasks,
) -> ApiEnvelope:
    trace_id = make_id("trc")
    if store.get_training_attempt(attempt_id) is None:
        raise HTTPException(status_code=404, detail="attempt not found")

    task = TaskRecord(
        task_id=make_id("task"),
        trace_id=trace_id,
        task_type="training.evaluate",
        input={"attempt_id": attempt_id, **payload.model_dump()},
    )
    store.put_task(task)
    background_tasks.add_task(
        orchestrator.run_training_evaluation_task,
        task.task_id,
        attempt_id,
        payload.rubric_version,
    )
    return envelope(trace_id=trace_id, data={"task_id": task.task_id, "status": task.status})


@app.post("/api/v1/comparison/tasks")
def create_comparison_task(payload: ComparisonTaskCreateRequest) -> ApiEnvelope:
    trace_id = make_id("trc")
    task = ComparisonTaskRecord(
        comparison_task_id=make_id("cmp"),
        source_product_id=payload.source_product_id,
        source_product_name=payload.source_product_name,
        targets=[target.model_dump() for target in payload.targets],
    )
    store.put_comparison_task(task)
    return envelope(
        trace_id=trace_id,
        data={"comparison_task_id": task.comparison_task_id, "status": "created"},
    )


@app.post("/api/v1/comparison/tasks/{comparison_task_id}:run")
def run_comparison(
    comparison_task_id: str,
    payload: ComparisonRunRequest,
    background_tasks: BackgroundTasks,
) -> ApiEnvelope:
    trace_id = make_id("trc")
    if store.get_comparison_task(comparison_task_id) is None:
        raise HTTPException(status_code=404, detail="comparison task not found")

    task = TaskRecord(
        task_id=make_id("task"),
        trace_id=trace_id,
        task_type="comparison.run",
        input={"comparison_task_id": comparison_task_id, **payload.model_dump()},
    )
    store.put_task(task)
    background_tasks.add_task(
        orchestrator.run_comparison_task,
        task.task_id,
        comparison_task_id,
        payload.template_version,
    )
    return envelope(trace_id=trace_id, data={"task_id": task.task_id, "status": task.status})


@app.get("/api/v1/tasks/{task_id}")
def get_task(task_id: str) -> ApiEnvelope:
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return envelope(
        trace_id=task.trace_id,
        data={
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status,
            "output": task.output,
            "error": task.error,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        },
    )
