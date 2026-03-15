from __future__ import annotations

import json
import logging

from app.models import ComparisonTaskRecord
from app.services.openclaw_adapter import OpenClawAdapter, normalize_offer

log = logging.getLogger(__name__)

_COMPARISON_PROMPT = """\
你是电商比价分析师。请对以下商品报价进行多维度分析，给出简洁的对比结论和购买建议。

## 商品报价

{offers_text}

## 输出格式

返回 JSON（不要包含 markdown 代码块标记）：
{{
  "comparable_type": "same_sku 或 similar_products 或 different_products",
  "deltas": ["价格差异点1", "促销差异点2", ...],
  "recommendations": ["购买建议1", "建议2", ...],
  "best_offer": {{
    "platform": "推荐平台",
    "reason": "推荐理由（一句话）"
  }}
}}"""


def _build_offers_text(offers: list[dict]) -> str:
    lines = []
    for i, o in enumerate(offers, 1):
        gifts = ", ".join(o.get("gift_items", [])) or "无"
        lines.append(
            f"{i}. 【{o.get('platform', '未知')}】\n"
            f"   原价: {o.get('original_price', '-')} | 到手价: {o.get('final_price', '-')}\n"
            f"   优惠: {', '.join(o.get('coupon_desc', [])) or '无'}\n"
            f"   赠品: {gifts}"
        )
    return "\n".join(lines)


def _summarize_with_llm(offers: list[dict]) -> dict:
    """使用真实 LLM 进行比价分析（同步调用）。"""
    from app.services.llm_service import chat_completion

    offers_text = _build_offers_text(offers)
    prompt = _COMPARISON_PROMPT.format(offers_text=offers_text)

    try:
        result = chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1024,
        )
        content = result.get("content", "").strip()

        # 提取 JSON
        if "```" in content:
            parts = content.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    content = part
                    break
        else:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                content = content[start : end + 1]

        analysis = json.loads(content)
        return {
            "deltas": analysis.get("deltas", []),
            "recommendations": analysis.get("recommendations", []),
            "comparable_type": analysis.get("comparable_type", "similar_products"),
            "best_offer": analysis.get("best_offer"),
            "usage": result.get("usage"),
        }
    except Exception as e:
        log.warning("LLM 比价分析失败，降级到算法方案: %s", e)
        return _summarize_fallback(offers)


def _summarize_fallback(offers: list[dict]) -> dict:
    """降级方案：纯算法比价（LLM 调用失败时使用）。"""
    if len(offers) < 2:
        return {
            "deltas": ["报价数量不足，无法对比。"],
            "recommendations": ["请添加至少两个目标平台。"],
            "comparable_type": "insufficient_targets",
        }

    sorted_offers = sorted(offers, key=lambda x: x.get("final_price", 0))
    best = sorted_offers[0]
    second = sorted_offers[1]
    diff = second.get("final_price", 0) - best.get("final_price", 0)

    deltas = [
        f"{best['platform']} 到手价最低，比 {second['platform']} 便宜 {diff:.0f} 元",
    ]
    if best.get("gift_items"):
        deltas.append(f"{best['platform']} 还赠送: {', '.join(best['gift_items'])}")

    return {
        "deltas": deltas,
        "recommendations": [
            "建议对比截图留存后再做决策。",
            "如果置信度不高，建议人工复核。",
        ],
        "comparable_type": "same_sku",
    }


class ComparisonWorkflow:
    def __init__(self) -> None:
        self.collector = OpenClawAdapter()

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

        summary = _summarize_with_llm(offers)
        comparable_type = summary.get("comparable_type", "same_sku" if len(offers) >= 2 else "insufficient_targets")

        result = {
            "comparison_task_id": task.comparison_task_id,
            "source_product_id": task.source_product_id,
            "source_product_name": task.source_product_name,
            "comparable_type": comparable_type,
            "offers": offers,
            "deltas": summary["deltas"],
            "recommendations": summary["recommendations"],
            "evidence": evidence,
        }
        if summary.get("best_offer"):
            result["best_offer"] = summary["best_offer"]
        if summary.get("usage"):
            result["llm_usage"] = summary["usage"]
        return result
