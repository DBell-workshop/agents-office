"""跨平台商品比价 Skill — Phase 2: LLM 语义分析 + 可插拔数据源。

状态机流程：
  INIT → on_start(query) → DataSource 搜索多平台 → yield 搜索结果 → AWAITING_USER
  AWAITING_USER → on_resume(selected_ids) → LLM 语义比价分析 → yield 比价结论 → DONE
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.services.skills.base import BaseSkill, SkillState, SkillStepResult

log = logging.getLogger(__name__)


# ============================================================
# 比价分析（算法降级 + LLM 语义分析）
# ============================================================

def _build_comparison_fallback(selected: List[Dict[str, Any]]) -> Dict[str, Any]:
    """降级方案：纯算法比价（无 LLM 时使用）。"""
    selected.sort(key=lambda p: p["price"])
    cheapest = selected[0]
    most_expensive = selected[-1]
    savings = most_expensive["price"] - cheapest["price"]

    brands = {p["brand"] for p in selected}
    if len(brands) == 1:
        comparison_type = "same_product"
        type_label = "同款商品跨平台比价"
    else:
        comparison_type = "similar_products"
        type_label = "同类商品横向对比"

    return {
        "comparison_type": comparison_type,
        "type_label": type_label,
        "products": selected,
        "cheapest": {
            "product_id": cheapest["product_id"],
            "name": cheapest["name"],
            "platform": cheapest["platform"],
            "price": cheapest["price"],
        },
        "price_range": {
            "min": cheapest["price"],
            "max": most_expensive["price"],
            "savings": savings,
        },
        "recommendation": (
            f"最低价在【{cheapest['platform']}】，"
            f"{cheapest['name']}，售价 ¥{cheapest['price']:.0f}"
            + (f"，比最高价便宜 ¥{savings:.0f}" if savings > 0 else "")
            + "。"
        ),
        "promotions_summary": {
            p["platform"]: p["promotions"] for p in selected
        },
    }


_COMPARISON_PROMPT = """\
你是一位专业的电商比价分析师。用户选择了以下商品进行对比，请从语义层面分析它们的异同，并给出购买建议。

## 待对比商品

{products_text}

## 分析要求

1. **同款判断**：根据商品名称、品牌、容量/规格等语义信息，判断这些商品的关系：
   - same_product：同一品牌同一型号，仅跨平台价格不同
   - similar_products：同品类但不同品牌/不同型号，可横向对比
   - different_products：品类差异较大，不建议直接对比

2. **多维度对比**：从以下维度分析（仅分析有依据的维度）：
   - 价格竞争力（含促销活动）
   - 品牌口碑（基于评分和评价数量）
   - 性价比综合评估

3. **购买建议**：给出具体的推荐理由，不要只说"最便宜"

## 输出格式

请严格返回以下 JSON 格式（不要包含 markdown 代码块标记）：
{{
  "comparison_type": "same_product 或 similar_products 或 different_products",
  "type_label": "对比类型的中文标题，如「美的小厨宝 5L 跨平台比价」或「小厨宝品牌横评」",
  "recommendation": "2-3句话的购买建议，包含具体推荐商品、平台、理由",
  "dimensions": [
    {{
      "name": "维度名称",
      "summary": "该维度的对比结论"
    }}
  ]
}}"""


async def _build_comparison_with_llm(selected: List[Dict[str, Any]]) -> Dict[str, Any]:
    """LLM 语义比价分析：理解商品语义，多维度对比，生成购买建议。"""
    from app.services.llm_service import async_chat_completion

    # 构建商品描述文本（含 specs 信息）
    products_lines = []
    for i, p in enumerate(selected, 1):
        promos = "、".join(p.get("promotions", [])) or "无"
        specs_str = ""
        if p.get("specs"):
            specs_str = " | ".join(f"{k}: {v}" for k, v in p["specs"].items())
            specs_str = f"\n   规格: {specs_str}"
        products_lines.append(
            f"{i}. 【{p['platform']}】{p['name']}\n"
            f"   品牌: {p['brand']} | 价格: ¥{p['price']} (原价 ¥{p.get('original_price', p['price'])})\n"
            f"   促销: {promos} | 评分: {p.get('rating', '-')} | 评价数: {p.get('review_count', 0)}"
            + specs_str
        )
    products_text = "\n".join(products_lines)

    prompt = _COMPARISON_PROMPT.format(products_text=products_text)

    try:
        result = await async_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1024,
        )

        content = result.get("content", "").strip()
        # 清理可能的 markdown 代码块标记
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        llm_analysis = json.loads(content)
    except (json.JSONDecodeError, KeyError, Exception) as e:
        log.warning("LLM 比价分析失败，降级到算法方案: %s", e)
        return _build_comparison_fallback(selected)

    # 合并 LLM 语义分析 + 事实数据（价格排序、促销汇总）
    selected_sorted = sorted(selected, key=lambda p: p["price"])
    cheapest = selected_sorted[0]
    most_expensive = selected_sorted[-1]
    savings = most_expensive["price"] - cheapest["price"]

    return {
        "comparison_type": llm_analysis.get("comparison_type", "similar_products"),
        "type_label": llm_analysis.get("type_label", "商品对比分析"),
        "products": selected,
        "cheapest": {
            "product_id": cheapest["product_id"],
            "name": cheapest["name"],
            "platform": cheapest["platform"],
            "price": cheapest["price"],
        },
        "price_range": {
            "min": cheapest["price"],
            "max": most_expensive["price"],
            "savings": savings,
        },
        "recommendation": llm_analysis.get(
            "recommendation",
            _build_comparison_fallback(selected)["recommendation"],
        ),
        "dimensions": llm_analysis.get("dimensions", []),
        "promotions_summary": {
            p["platform"]: p["promotions"] for p in selected
        },
    }


# ============================================================
# Skill 实现
# ============================================================

def _flatten_search_results(
    search_results: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """展平多平台搜索结果为单一列表。"""
    products = []
    for platform_products in search_results.values():
        products.extend(platform_products)
    return products


class CrossPlatformCompareSkill(BaseSkill):
    """跨平台商品比价 Skill。"""

    name = "cross_platform_compare"
    display_name = "跨平台比价"
    description = "在多个电商平台搜索同类商品，对比价格、促销和评价，给出购买建议"
    agent_slugs = ["shopping_guide"]

    async def on_start(self, params: Dict[str, Any]) -> SkillStepResult:
        """接收搜索关键词，通过 DataSource 搜索多平台商品。

        params: {"query": "小厨宝", "platforms": ["京东", "淘宝"]}
        """
        from app.services.datasources import get_datasource

        query = params.get("query", "")
        platforms = params.get("platforms")

        datasource = get_datasource()
        search_results = await datasource.search(query=query, platforms=platforms)

        total_count = sum(len(v) for v in search_results.values())

        events = [
            {
                "event": "skill_interact",
                "data": {
                    "interaction_type": "search_results",
                    "content": f"已在 {len(search_results)} 个平台找到 {total_count} 个相关商品",
                    "payload": {
                        "query": query,
                        "platforms": list(search_results.keys()),
                        "results": search_results,
                        "total_count": total_count,
                    },
                },
            },
        ]

        return SkillStepResult(
            next_state="awaiting_user",
            events=events,
            context_update={
                "query": query,
                "search_results": search_results,
            },
            user_prompt={
                "type": "select_products",
                "message": "请选择要对比的商品（2-4个）",
                "min_select": 2,
                "max_select": 4,
            },
        )

    async def on_resume(
        self,
        state: SkillState,
        context: Dict[str, Any],
        user_input: Any,
    ) -> SkillStepResult:
        """用户选择商品后执行 LLM 语义比价分析。"""
        selected_ids = user_input.get("product_ids", [])

        # 从上下文中的搜索结果里查找选中的商品
        search_results = context.get("search_results", {})
        all_products = _flatten_search_results(search_results)
        selected = [p for p in all_products if p["product_id"] in selected_ids]

        if not selected:
            return SkillStepResult(
                next_state="error",
                events=[
                    {
                        "event": "skill_error",
                        "data": {"error": "未找到选择的商品"},
                    },
                ],
            )

        comparison = await _build_comparison_with_llm(selected)

        if "error" in comparison:
            return SkillStepResult(
                next_state="error",
                events=[
                    {
                        "event": "skill_error",
                        "data": {"error": comparison["error"]},
                    },
                ],
            )

        events = [
            {
                "event": "skill_interact",
                "data": {
                    "interaction_type": "comparison_result",
                    "content": comparison.get("recommendation", "比价分析完成"),
                    "payload": comparison,
                },
            },
        ]

        return SkillStepResult(
            next_state="done",
            events=events,
            context_update={
                "selected_ids": selected_ids,
                "comparison": comparison,
            },
        )

    def validate_user_input(
        self,
        state: SkillState,
        context: Dict[str, Any],
        user_input: Any,
    ) -> Optional[str]:
        if not isinstance(user_input, dict):
            return "输入格式错误，需要 {product_ids: [...]}"
        ids = user_input.get("product_ids")
        if not ids or not isinstance(ids, list):
            return "请选择至少2个商品进行对比"
        if len(ids) < 2:
            return "至少选择2个商品"
        if len(ids) > 4:
            return "最多选择4个商品"
        return None
