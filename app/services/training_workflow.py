from __future__ import annotations

from app.models import CourseRecord, TrainingAttemptRecord
from app.services.mock_services import MockASRService, MockLLMService, MockTTSService, ScoringService


class TrainingWorkflow:
    def __init__(self) -> None:
        self.llm = MockLLMService()
        self.tts = MockTTSService()
        self.asr = MockASRService()
        self.scoring = ScoringService()

    def generate_content(self, course: CourseRecord, scene: str) -> dict:
        content = self.llm.generate_training_content(
            product_name=course.product_name,
            objective=course.objective,
            required_points=course.required_points,
            product_facts=course.product_facts,
            scene=scene,
        )
        audio = self.tts.synthesize(content["script_text"])
        content["audio"] = audio
        return content

    def evaluate_attempt(self, course: CourseRecord, attempt: TrainingAttemptRecord, rubric_version: str) -> dict:
        transcript_result = self.asr.transcribe(attempt.mock_transcript)
        scoring = self.scoring.evaluate(
            transcript=transcript_result.transcript,
            required_points=course.required_points,
            product_facts=course.product_facts,
            rubric_version=rubric_version,
        )
        return {
            "attempt_id": attempt.attempt_id,
            "course_id": course.course_id,
            "transcript": transcript_result.transcript,
            "pause_count": transcript_result.pause_count,
            "filler_count": transcript_result.filler_count,
            **scoring,
        }
