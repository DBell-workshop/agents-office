"""商品搜索服务 — 查询 PostgreSQL 中的 Best Buy 商品数据。

供理货员 Agent 通过 Function Calling 使用。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.config import settings
from app.db.engine import build_session_factory

_SessionFactory = None


def _get_session():
    global _SessionFactory
    if _SessionFactory is None:
        if not settings.database_url_sync:
            raise RuntimeError("DATABASE_URL_SYNC not configured")
        _SessionFactory = build_session_factory(settings.database_url_sync)
    return _SessionFactory()


def search_products(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """搜索商品，支持关键词、品类、品牌、价格范围筛选。"""
    session = _get_session()
    try:
        conditions = []
        params: Dict[str, Any] = {}

        if keyword:
            words = keyword.split()
            if len(words) > 1:
                # 多关键词：每个词 OR 匹配 name 或 description
                word_clauses = []
                for i, word in enumerate(words):
                    param_key = f"kw_{i}"
                    word_clauses.append(f"(name ILIKE :{param_key} OR attributes->>'description' ILIKE :{param_key})")
                    params[param_key] = f"%{word}%"
                conditions.append(f"({' OR '.join(word_clauses)})")
            else:
                conditions.append("(name ILIKE :kw OR attributes->>'description' ILIKE :kw)")
                params["kw"] = f"%{keyword}%"

        if category:
            conditions.append("category = :cat")
            params["cat"] = category

        if brand:
            conditions.append("brand ILIKE :brand")
            params["brand"] = f"%{brand}%"

        if min_price is not None:
            conditions.append("(attributes->>'price')::numeric >= :min_p")
            params["min_p"] = min_price

        if max_price is not None:
            conditions.append("(attributes->>'price')::numeric <= :max_p")
            params["max_p"] = max_price

        where = " AND ".join(conditions) if conditions else "TRUE"
        params["lim"] = limit

        sql = text(f"""
            SELECT product_id, name, category, brand, attributes
            FROM products
            WHERE {where}
              AND attributes->>'price' IS NOT NULL
            ORDER BY (attributes->>'price')::numeric ASC
            LIMIT :lim
        """)

        rows = session.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        session.close()


def compare_products(product_ids: List[str]) -> Dict[str, Any]:
    """批量查询商品详情并返回结构化对比结果，方便 LLM 做横向对比分析。"""
    session = _get_session()
    try:
        results = []
        not_found = []
        for pid in product_ids:
            sql = text("SELECT product_id, name, category, brand, attributes FROM products WHERE product_id = :pid")
            row = session.execute(sql, {"pid": pid}).fetchone()
            if row:
                results.append(_row_to_dict(row))
            else:
                not_found.append(pid)

        comparison = {
            "count": len(results),
            "products": [
                {
                    "product_id": p["product_id"],
                    "name": p["name"],
                    "brand": p["brand"],
                    "price_usd": p["price"],
                    "description": p["description"],
                    "category": p["category"],
                    "model_number": p["model_number"],
                }
                for p in results
            ],
            "not_found": not_found,
        }
        return comparison
    finally:
        session.close()


def get_product_detail(product_id: str) -> Optional[Dict[str, Any]]:
    """根据 product_id 获取商品详情。"""
    session = _get_session()
    try:
        sql = text("SELECT product_id, name, category, brand, attributes FROM products WHERE product_id = :pid")
        row = session.execute(sql, {"pid": product_id}).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        session.close()


def get_category_stats() -> List[Dict[str, Any]]:
    """获取各品类商品数量和价格范围统计。"""
    session = _get_session()
    try:
        sql = text("""
            SELECT
                category,
                COUNT(*) as count,
                ROUND(MIN((attributes->>'price')::numeric), 2) as min_price,
                ROUND(MAX((attributes->>'price')::numeric), 2) as max_price,
                ROUND(AVG((attributes->>'price')::numeric), 2) as avg_price
            FROM products
            WHERE attributes->>'price' IS NOT NULL
            GROUP BY category
            ORDER BY count DESC
        """)
        rows = session.execute(sql).fetchall()
        return [
            {
                "category": r[0],
                "count": r[1],
                "min_price": float(r[2]) if r[2] else 0,
                "max_price": float(r[3]) if r[3] else 0,
                "avg_price": float(r[4]) if r[4] else 0,
            }
            for r in rows
        ]
    finally:
        session.close()


def _row_to_dict(row) -> Dict[str, Any]:
    """将数据库行转为前端友好的字典。"""
    attrs = row[4] if isinstance(row[4], dict) else json.loads(row[4])
    return {
        "product_id": row[0],
        "name": row[1],
        "category": row[2],
        "brand": row[3],
        "price": attrs.get("price"),
        "description": attrs.get("description", ""),
        "image_url": attrs.get("image_url", ""),
        "model_number": attrs.get("model_number", ""),
    }
