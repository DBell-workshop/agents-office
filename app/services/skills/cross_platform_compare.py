"""跨平台商品比价 Skill — Phase 2: LLM 语义分析 + 可插拔数据源。

支持两种入口模式：
  A) 关键词搜索模式：
     INIT → on_start(query) → DataSource 搜索多平台 → 用户选商品 → LLM 比价 → DONE
  B) URL 粘贴模式：
     INIT → on_start(urls) → DataSource fetch_product 逐个提取 → 直接 LLM 比价 → DONE
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.services.skills.base import BaseSkill, SkillState, SkillStepResult

log = logging.getLogger(__name__)

# URL 检测正则
_URL_RE = re.compile(r"https?://\S+")


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
你是一位资深电商比价分析师，擅长帮消费者做出最聪明的购买决策。
用户选择了以下商品进行对比，请从多个维度深入分析，给出专业的购买建议。

## 待对比商品

{products_text}

## 分析要求

### 1. 同款识别
根据商品名称、品牌、型号、规格等语义信息，精准判断商品关系：
- **same_product**: 同一品牌同一型号（仅平台/卖家不同）→ 重点比价格和卖家
- **similar_products**: 同品类不同品牌/型号 → 重点比性能和性价比
- **different_products**: 品类差异大，不建议直接对比

### 2. 多维度对比（仅分析有依据的维度）

**价格维度：**
- 当前售价对比（含折算到手价）
- 促销活动的实际价值（满减、优惠券、百亿补贴等）
- 原价与现价的折扣力度

**卖家维度：**
- 官方旗舰店 vs 第三方卖家 vs 个人店铺
- 从店铺名称判断卖家类型和可信度
- 同平台多卖家时，是否有正品保障风险

**口碑维度：**
- 评分高低及评价数量（评价数多更可信）
- 不同平台的评价体系差异（拼多多评价数普遍偏高但可信度不同）

**性价比综合评估：**
- 不是最便宜就最好 — 综合价格、卖家信誉、售后保障
- 如果价格差异 <5%，优先推荐卖家更可靠的选项
- 百亿补贴/官方旗舰店通常比个人卖家更有保障

### 3. 购买建议
给出具体的推荐，说明：推荐哪个、在哪买、为什么。
如果存在「价格最低但卖家不可靠」的情况，明确提示风险。

## 输出格式

请严格返回以下 JSON 格式（不要包含 markdown 代码块标记）。
注意：每个字段的值要简洁，dimension 的 summary 控制在30字以内，recommendation 控制在100字以内。
{{
  "comparison_type": "same_product 或 similar_products 或 different_products",
  "type_label": "对比类型的中文标题",
  "recommendation": "2-3句简洁的购买建议",
  "best_value": {{
    "product_index": 最佳性价比商品的序号（从1开始），
    "reason": "一句话说明原因"
  }},
  "dimensions": [
    {{
      "name": "维度名",
      "summary": "简洁的对比结论（30字以内）"
    }}
  ]
}}"""


def _build_products_text(selected: List[Dict[str, Any]]) -> str:
    """构建商品描述文本，供 LLM 分析。"""
    products_lines = []
    for i, p in enumerate(selected, 1):
        promos = "、".join(p.get("promotions", [])) or "无"
        specs_str = ""
        if p.get("specs"):
            specs_str = " | ".join(f"{k}: {v}" for k, v in p["specs"].items())
            specs_str = f"\n   规格: {specs_str}"
        shop_info = ""
        if p.get("shop_name"):
            shop_info = f"\n   店铺: {p['shop_name']}"
        products_lines.append(
            f"{i}. 【{p.get('platform', '未知')}】{p.get('name', '未知商品')}\n"
            f"   品牌: {p.get('brand', '未知')} | 价格: ¥{p.get('price', 0)} "
            f"(原价 ¥{p.get('original_price', p.get('price', 0))})\n"
            f"   促销: {promos} | 评分: {p.get('rating', '-')} | "
            f"评价数: {p.get('review_count', 0)}"
            + specs_str
            + shop_info
        )
    return "\n".join(products_lines)


async def _build_comparison_with_llm(selected: List[Dict[str, Any]]) -> Dict[str, Any]:
    """LLM 语义比价分析：理解商品语义，多维度对比，生成购买建议。"""
    from app.services.llm_service import async_chat_completion

    products_text = _build_products_text(selected)
    prompt = _COMPARISON_PROMPT.format(products_text=products_text)

    try:
        result = await async_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048,
        )

        content = result.get("content", "").strip()
        # 提取 JSON：先尝试从 ```json ... ``` 中提取，再尝试找第一个 { 到最后一个 }
        if "```" in content:
            # 去掉 markdown 代码块
            parts = content.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    content = part
                    break
        else:
            # 直接找 JSON 对象边界
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                content = content[start : end + 1]

        llm_analysis = json.loads(content)
    except (json.JSONDecodeError, KeyError, Exception) as e:
        log.warning("LLM 比价分析失败，降级到算法方案: %s", e)
        return _build_comparison_fallback(selected)

    # 合并 LLM 语义分析 + 事实数据
    selected_sorted = sorted(selected, key=lambda p: p.get("price", 0))
    cheapest = selected_sorted[0]
    most_expensive = selected_sorted[-1]
    savings = most_expensive.get("price", 0) - cheapest.get("price", 0)

    # 最佳性价比（LLM 推荐 > 最低价）
    best_value = llm_analysis.get("best_value", {})
    best_idx = best_value.get("product_index", 1) - 1
    if 0 <= best_idx < len(selected):
        best_product = selected[best_idx]
    else:
        best_product = cheapest

    return {
        "comparison_type": llm_analysis.get("comparison_type", "similar_products"),
        "type_label": llm_analysis.get("type_label", "商品对比分析"),
        "products": selected,
        "cheapest": {
            "product_id": cheapest.get("product_id", ""),
            "name": cheapest.get("name", ""),
            "platform": cheapest.get("platform", ""),
            "price": cheapest.get("price", 0),
        },
        "best_value": {
            "product_id": best_product.get("product_id", ""),
            "name": best_product.get("name", ""),
            "platform": best_product.get("platform", ""),
            "price": best_product.get("price", 0),
            "reason": best_value.get("reason", ""),
        },
        "price_range": {
            "min": cheapest.get("price", 0),
            "max": most_expensive.get("price", 0),
            "savings": savings,
        },
        "recommendation": llm_analysis.get(
            "recommendation",
            _build_comparison_fallback(selected)["recommendation"],
        ),
        "dimensions": llm_analysis.get("dimensions", []),
        "promotions_summary": {
            p.get("platform", "未知"): p.get("promotions", []) for p in selected
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
    """跨平台商品比价 Skill。

    支持两种入口：
      1. 关键词搜索: params={"query": "小厨宝"} → 搜索 → 用户选商品 → 比价
      2. URL 粘贴:   params={"query": "https://... https://..."} → 直接提取 → 比价
    """

    name = "cross_platform_compare"
    display_name = "跨平台比价"
    description = "在多个电商平台搜索同类商品，对比价格、促销和评价，给出购买建议。也支持直接粘贴商品链接比价"
    agent_slugs = ["price_comparator"]

    async def on_start(self, params: Dict[str, Any]) -> SkillStepResult:
        """根据输入自动选择模式：URL 粘贴直达比价 / 关键词搜索。"""
        query = params.get("query", "")
        urls = _URL_RE.findall(query)

        if len(urls) >= 2:
            return await self._start_url_mode(urls)
        else:
            return await self._start_search_mode(query, params.get("platforms"))

    async def _start_url_mode(self, urls: List[str]) -> SkillStepResult:
        """URL 粘贴模式：逐个提取商品信息 → 直接比价（跳过用户选择步骤）。"""
        from app.services.datasources import get_datasource

        datasource = get_datasource()
        products: List[Dict[str, Any]] = []
        failed_urls: List[str] = []

        for url in urls[:4]:  # 最多处理 4 个 URL
            product = await datasource.fetch_product(url)
            if product:
                products.append(product)
            else:
                failed_urls.append(url)

        if len(products) < 2:
            error_msg = f"成功提取 {len(products)} 个商品，至少需要 2 个才能比价。"
            if failed_urls:
                error_msg += f" 以下链接提取失败: {', '.join(failed_urls)}"
            return SkillStepResult(
                next_state="error",
                events=[{"event": "skill_error", "data": {"error": error_msg}}],
            )

        # URL 模式直接进入比价，不需要用户选择
        comparison = await _build_comparison_with_llm(products)

        events = []
        if failed_urls:
            events.append({
                "event": "skill_interact",
                "data": {
                    "interaction_type": "warning",
                    "content": f"注意：{len(failed_urls)} 个链接提取失败，仅对比成功提取的商品",
                },
            })

        events.append({
            "event": "skill_interact",
            "data": {
                "interaction_type": "comparison_result",
                "content": comparison.get("recommendation", "比价分析完成"),
                "payload": comparison,
            },
        })

        return SkillStepResult(
            next_state="done",
            events=events,
            context_update={
                "mode": "url",
                "urls": urls,
                "products": products,
                "comparison": comparison,
            },
        )

    async def _start_search_mode(
        self, query: str, platforms: Optional[List[str]] = None
    ) -> SkillStepResult:
        """关键词搜索模式：搜索多平台 → 返回结果等待用户选择。"""
        from app.services.datasources import get_datasource

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
                "mode": "search",
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
