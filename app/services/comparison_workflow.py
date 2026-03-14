from __future__ import annotations

from app.models import ComparisonTaskRecord
from app.services.mock_services import MockLLMService
from app.services.openclaw_adapter import OpenClawAdapter, normalize_offer


class ComparisonWorkflow:
    def __init__(self) -> None:
        self.collector = OpenClawAdapter()
        self.llm = MockLLMService()

    def run(self, task: ComparisonTaskRecord, template_version: str) -> dict:
        offers: list[dict] = []
        evidence: list[dict] = []

        for target in task.targets:
            collected = self.collector.collect(
                platform=target["platform"],
                url=target["url"],
                template_version=template_version,
            )
            offer = normalize_offer(platform=target["platform"], raw_fields=collected.raw_fields)
            offers.append(offer)
            evidence.append(
                {
                    "platform": target["platform"],
                    "url": target["url"],
                    "snapshot_id": collected.snapshot_id,
                    "screenshot_urls": collected.screenshot_urls,
                    "raw_fields": collected.raw_fields,
                }
            )

        summary = self.llm.summarize_comparison(offers)
        comparable_type = "same_sku" if len(offers) >= 2 else "insufficient_targets"

        return {
            "comparison_task_id": task.comparison_task_id,
            "source_product_id": task.source_product_id,
            "source_product_name": task.source_product_name,
            "comparable_type": comparable_type,
            "offers": offers,
            "deltas": summary["deltas"],
            "recommendations": summary["recommendations"],
            "evidence": evidence,
        }
