"""商品数据源 — 抽象接口 + 可插拔实现。"""
from __future__ import annotations

import logging

from app.services.datasources.base import ProductDataSource
from app.services.datasources.mock import MockDataSource

__all__ = ["ProductDataSource", "MockDataSource", "get_datasource"]

log = logging.getLogger(__name__)


def get_datasource() -> ProductDataSource:
    """根据配置返回当前使用的数据源实例。

    DATASOURCE_MODE 环境变量控制:
      - "mock"（默认）: 使用本地模拟数据
      - "browser": 使用 Playwright + LLM 浏览器采集
    """
    from app.config import settings

    mode = settings.datasource_mode

    if mode == "browser":
        from app.services.datasources.browser import BrowserDataSource

        log.info("数据源模式: browser（Playwright + LLM 采集）")
        return BrowserDataSource()

    log.info("数据源模式: mock（本地模拟数据）")
    return MockDataSource()
