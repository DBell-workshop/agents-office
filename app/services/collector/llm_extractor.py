"""LLM 网页内容提取 — 通用商品信息结构化。

从 browser.py 提取的公共模块，供 BrowserDataSource 和
InteractiveBrowserCollector 共同使用。
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ============================================================
# LLM Prompt
# ============================================================

EXTRACT_SEARCH_RESULTS_PROMPT = """\
你是一位网页内容分析专家。以下是一个电商平台搜索结果页面的文本内容。
请从中提取商品列表信息。

## 平台信息
- 平台名称: {platform}
- 搜索关键词: {query}
{hints_section}

## 页面内容

{page_content}

## 提取要求

从页面中提取最多 {max_products} 个与搜索关键词最相关的商品，每个商品包含以下字段（尽可能提取，缺失的字段留空）：

请严格返回 JSON 数组格式（不要包含 markdown 代码块标记）：
[
  {{
    "name": "商品完整名称",
    "brand": "品牌名（从商品名称或店铺信息推断）",
    "price": 价格数值（当前售价，数字类型），
    "original_price": 原价数值（划线价，没有则与 price 相同），
    "promotions": ["促销信息1", "促销信息2"],
    "rating": 评分数值（0-5，没有则 null），
    "review_count": 评价数量（整数，没有则 0），
    "url": "商品详情页链接（如果页面中能找到）",
    "image_url": "商品图片链接（如果能找到）",
    "specs": {{"规格名1": "值1", "规格名2": "值2"}},
    "shop_name": "店铺名称（如果能找到）"
  }}
]

如果页面内容不包含商品信息（例如验证码页面、登录页面），请返回空数组 []。"""


EXTRACT_PRODUCT_DETAIL_PROMPT = """\
你是一位网页内容分析专家。以下是一个电商商品详情页面的文本内容。
请从中提取该商品的详细信息。

## 页面内容

{page_content}

## 提取要求

请提取该商品的完整信息，严格返回 JSON 格式（不要包含 markdown 代码块标记）：
{{
  "name": "商品完整名称",
  "brand": "品牌名",
  "price": 当前售价（数字类型），
  "original_price": 原价/划线价（数字类型，没有则与 price 相同），
  "promotions": ["促销活动1", "促销活动2"],
  "rating": 评分（0-5，没有则 null），
  "review_count": 评价数量（整数，没有则 0），
  "url": "当前页面URL",
  "image_url": "商品主图链接",
  "specs": {{"规格名1": "值1", "规格名2": "值2"}},
  "platform": "判断这是哪个电商平台（京东/淘宝/拼多多/其他）",
  "shop_name": "店铺名称（如果能找到）"
}}

如果页面内容不是商品页面（例如验证码、登录页），请返回 {{"error": "原因描述"}}。"""


# ============================================================
# 工具函数
# ============================================================

def clean_llm_json(content: str) -> str:
    """清理 LLM 返回中可能包含的 markdown 代码块标记。"""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()


def generate_product_id(platform: str, name: str, url: str) -> str:
    """根据平台+商品名+URL 生成稳定的 product_id。"""
    prefix_map = {"京东": "jd", "淘宝": "tb", "拼多多": "pdd"}
    prefix = prefix_map.get(platform, "web")
    hash_input = f"{platform}:{name}:{url}"
    short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
    return f"{prefix}_{short_hash}"


def normalize_product_fields(product: Dict[str, Any], platform: str) -> Dict[str, Any]:
    """标准化商品字段类型。"""
    product["platform"] = platform
    if not product.get("product_id"):
        product["product_id"] = generate_product_id(
            platform, product.get("name", ""), product.get("url", "")
        )
    for field in ("price", "original_price", "rating"):
        if field in product and product[field] is not None:
            try:
                product[field] = float(product[field])
            except (ValueError, TypeError):
                product[field] = 0.0
    if "review_count" in product:
        try:
            product["review_count"] = int(product["review_count"])
        except (ValueError, TypeError):
            product["review_count"] = 0
    return product


# ============================================================
# LLM 提取函数
# ============================================================

async def llm_extract_search_results(
    page_content: str,
    platform: str,
    query: str,
    hints: str = "",
    max_products: int = 5,
    model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """让 LLM 从搜索结果页面文本中提取商品列表。"""
    from app.services.llm_service import async_chat_completion

    hints_section = f"- 平台特征提示: {hints}" if hints else ""
    prompt = EXTRACT_SEARCH_RESULTS_PROMPT.format(
        platform=platform,
        query=query,
        hints_section=hints_section,
        page_content=page_content,
        max_products=max_products,
    )

    try:
        kwargs: Dict[str, Any] = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 2048,
        }
        if model:
            kwargs["model"] = model
        result = await async_chat_completion(**kwargs)
        content = clean_llm_json(result.get("content", ""))
        products = json.loads(content)
        if not isinstance(products, list):
            return []

        return [normalize_product_fields(p, platform) for p in products]

    except (json.JSONDecodeError, Exception) as e:
        log.warning("LLM 提取搜索结果失败 (%s): %s", platform, e)
        return []


async def llm_extract_product_detail(
    page_content: str,
    model: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """让 LLM 从商品详情页面文本中提取结构化信息。"""
    from app.services.llm_service import async_chat_completion

    prompt = EXTRACT_PRODUCT_DETAIL_PROMPT.format(page_content=page_content)

    try:
        kwargs: Dict[str, Any] = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1024,
        }
        if model:
            kwargs["model"] = model
        result = await async_chat_completion(**kwargs)
        content = clean_llm_json(result.get("content", ""))
        product = json.loads(content)

        if "error" in product:
            log.warning("LLM 判断页面非商品页: %s", product["error"])
            return None

        platform = product.get("platform", "未知")
        product["product_id"] = generate_product_id(
            platform, product.get("name", ""), product.get("url", "")
        )
        return product

    except (json.JSONDecodeError, Exception) as e:
        log.warning("LLM 提取商品详情失败: %s", e)
        return None
