from __future__ import annotations

from app.models import now_iso
from app.services.comparison_workflow import ComparisonWorkflow
from app.services.training_workflow import TrainingWorkflow
from app.store import store


class Orchestrator:
    def __init__(self) -> None:
        self.training = TrainingWorkflow()
        self.comparison = ComparisonWorkflow()

    def run_training_content_task(self, task_id: str, course_id: str, scene: str) -> None:
        store.update_task(task_id, status="running")
        try:
            course = store.get_course(course_id)
            if course is None:
                raise ValueError(f"course not found: {course_id}")

            content = self.training.generate_content(course=course, scene=scene)
            store.update_course_content(course_id=course_id, content=content)
            store.update_task(task_id, status="succeeded", output=content)
        except Exception as exc:  # pragma: no cover - defensive path
            store.update_task(task_id, status="failed", error=str(exc))

    def run_training_evaluation_task(self, task_id: str, attempt_id: str, rubric_version: str) -> None:
        store.update_task(task_id, status="running")
        try:
            attempt = store.get_training_attempt(attempt_id)
            if attempt is None:
                raise ValueError(f"attempt not found: {attempt_id}")

            course = store.get_course(attempt.course_id)
            if course is None:
                raise ValueError(f"course not found: {attempt.course_id}")

            report = self.training.evaluate_attempt(course=course, attempt=attempt, rubric_version=rubric_version)
            store.update_task(task_id, status="succeeded", output=report)
        except Exception as exc:  # pragma: no cover - defensive path
            store.update_task(task_id, status="failed", error=str(exc))

    def run_comparison_task(self, task_id: str, comparison_task_id: str, template_version: str) -> None:
        store.update_task(task_id, status="running")
        try:
            comparison_task = store.get_comparison_task(comparison_task_id)
            if comparison_task is None:
                raise ValueError(f"comparison task not found: {comparison_task_id}")

            report = self.comparison.run(task=comparison_task, template_version=template_version)
            report["generated_at"] = now_iso()
            store.update_task(task_id, status="succeeded", output=report)
        except Exception as exc:  # pragma: no cover - defensive path
            store.update_task(task_id, status="failed", error=str(exc))


orchestrator = Orchestrator()
