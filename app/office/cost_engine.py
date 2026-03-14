"""成本计算引擎 -- 确定性逻辑模块，从 model_pricing 读价格并计算费用。"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.orm_models import ModelPricingRow


def _load_pricing_map(session: Session) -> Dict[str, Tuple[Decimal, Decimal]]:
    """从 model_pricing 表加载所有活跃模型的定价。

    Returns:
        {model_name: (input_price_per_1k, output_price_per_1k)}
    """
    rows = session.query(ModelPricingRow).filter(ModelPricingRow.is_active.is_(True)).all()
    return {
        row.model_name: (row.input_price_per_1k, row.output_price_per_1k)
        for row in rows
    }


def calculate_cost(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    session: Session,
) -> Tuple[Decimal, Decimal, Decimal]:
    """根据模型定价计算单次调用费用。

    Args:
        model_name: 模型名称（如 "gpt-4o"）
        input_tokens: 输入 token 数
        output_tokens: 输出 token 数
        session: SQLAlchemy Session

    Returns:
        (input_cost, output_cost, total_cost)，单位：美元
    """
    pricing = session.get(ModelPricingRow, model_name)
    if pricing is None or not pricing.is_active:
        # 未知模型，费用置零
        zero = Decimal("0")
        return zero, zero, zero

    input_cost = Decimal(str(input_tokens)) / Decimal("1000") * pricing.input_price_per_1k
    output_cost = Decimal(str(output_tokens)) / Decimal("1000") * pricing.output_price_per_1k
    total_cost = input_cost + output_cost
    return input_cost, output_cost, total_cost


def get_pricing_list(session: Session) -> list:
    """获取所有模型定价列表。"""
    rows = session.query(ModelPricingRow).order_by(ModelPricingRow.provider, ModelPricingRow.model_name).all()
    return [
        {
            "model_name": row.model_name,
            "display_name": row.display_name,
            "provider": row.provider,
            "input_price_per_1k": float(row.input_price_per_1k),
            "output_price_per_1k": float(row.output_price_per_1k),
            "is_active": row.is_active,
        }
        for row in rows
    ]
