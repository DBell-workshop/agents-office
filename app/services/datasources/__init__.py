"""商品数据源 — 抽象接口 + 可插拔实现。"""
from __future__ import annotations

from app.services.datasources.base import ProductDataSource
from app.services.datasources.mock import MockDataSource

__all__ = ["ProductDataSource", "MockDataSource", "get_datasource"]


def get_datasource() -> ProductDataSource:
    """根据配置返回当前使用的数据源实例。

    当前默认 MockDataSource，后续可根据 settings 切换到真实采集。
    """
    return MockDataSource()
