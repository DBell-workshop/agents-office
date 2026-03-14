from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class MockTranscriptResult:
    transcript: str
    pause_count: int
    filler_count: int


class MockLLMService:
    def generate_training_content(
        self,
        product_name: str,
        objective: str,
        required_points: list[str],
        product_facts: dict[str, str],
        scene: str,
    ) -> dict:
        points = required_points or ["main selling point", "price advantage", "after-sales policy"]
        fact_lines = [f"{k}: {v}" for k, v in product_facts.items()]
        script = (
            f"Today I will introduce {product_name}. "
            f"This training objective is: {objective}. "
            f"In {scene}, highlight these points: "
            + "; ".join(points)
            + "."
        )
        if fact_lines:
            script += " Product facts: " + " | ".join(fact_lines) + "."

        qa_pairs = [
            {"q": f"What is the value of {points[0]}?", "a": f"Explain {points[0]} using one customer scenario."},
            {"q": "How to handle price concerns?", "a": "Compare total value, then explain current promotions."},
        ]

        return {
            "script_text": script,
            "qa_pairs": qa_pairs,
            "evidence_refs": [f"fact:{k}" for k in product_facts.keys()],
        }

    def summarize_comparison(self, offers: list[dict]) -> dict:
        if len(offers) < 2:
            return {
                "deltas": ["Not enough offers to compare."],
                "recommendations": ["Add at least two target platforms."],
            }

        sorted_offers = sorted(offers, key=lambda x: x.get("final_price", 0))
        best = sorted_offers[0]
        second = sorted_offers[1]
        diff = second["final_price"] - best["final_price"]

        deltas = [
            f"{best['platform']} has the lowest final price, lower by {diff} compared with {second['platform']}",
        ]
        if best.get("gift_items"):
            deltas.append(f"{best['platform']} also provides gifts: {', '.join(best['gift_items'])}")

        recommendations = [
            "Use evidence screenshots before applying strategy changes.",
            "If confidence is low, require manual review before decision.",
        ]

        return {"deltas": deltas, "recommendations": recommendations}


class MockTTSService:
    def synthesize(self, script_text: str, voice: str = "neutral") -> dict:
        duration_ms = max(8000, len(script_text) * 20)
        return {
            "audio_id": f"mock_audio_{abs(hash(script_text)) % 100000}",
            "audio_url": "https://example.invalid/mock-training-audio.mp3",
            "duration_ms": duration_ms,
            "voice": voice,
        }


class MockASRService:
    def transcribe(self, transcript_hint: Optional[str]) -> MockTranscriptResult:
        text = transcript_hint or (
            "This product has strong battery life and clear after-sales policy. "
            "I will explain the price value clearly to the customer."
        )
        pause_count = text.count("...") + text.count(" uh ")
        filler_count = len(re.findall(r"\b(um|uh|like)\b", text.lower()))
        return MockTranscriptResult(transcript=text, pause_count=pause_count, filler_count=filler_count)


class ScoringService:
    def evaluate(
        self,
        transcript: str,
        required_points: list[str],
        product_facts: dict[str, str],
        rubric_version: str,
    ) -> dict:
        lower = transcript.lower()

        coverage_hits = sum(1 for p in required_points if p.lower() in lower)
        coverage_score = int((coverage_hits / max(1, len(required_points))) * 100)

        accuracy_score = 90
        issues: list[dict] = []

        # Simple fact mismatch rule for mock prototype.
        if "24 installments" in lower and product_facts.get("installments") == "12 installments":
            accuracy_score = 60
            issues.append(
                {
                    "type": "fact_error",
                    "content": "Installment count mismatch: expected 12 installments.",
                    "evidence_ref": "fact:installments",
                }
            )

        compliance_score = 90
        if "best in the world" in lower:
            compliance_score = 60
            issues.append(
                {
                    "type": "compliance_risk",
                    "content": "Absolute claim detected: 'best in the world'.",
                    "evidence_ref": "policy:absolute_claim",
                }
            )

        fluency_penalty = lower.count("...") * 8 + lower.count(" um ") * 5 + lower.count(" uh ") * 5
        fluency_score = max(40, 95 - fluency_penalty)

        naturalness_score = min(95, 70 + coverage_hits * 8)

        total = int(
            accuracy_score * 0.30
            + coverage_score * 0.20
            + fluency_score * 0.15
            + naturalness_score * 0.10
            + coverage_score * 0.15
            + compliance_score * 0.10
        )

        suggestions = [
            "Use a clearer opening and present key selling points first.",
            "Avoid long pauses and reduce filler words.",
        ]
        if coverage_hits < len(required_points):
            suggestions.insert(0, "Cover all required selling points before pricing details.")

        return {
            "rubric_version": rubric_version,
            "scores": {
                "accuracy": accuracy_score,
                "coverage": coverage_score,
                "fluency": fluency_score,
                "naturalness": naturalness_score,
                "compliance": compliance_score,
                "total": total,
            },
            "issues": issues,
            "suggestions": suggestions,
        }
