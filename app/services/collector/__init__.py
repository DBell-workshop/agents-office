"""用户参与式浏览器采集 — 全局采集器生命周期管理。"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)

_active_collector: Optional["InteractiveBrowserCollector"] = None  # noqa: F821


async def get_or_create_collector() -> "InteractiveBrowserCollector":
    """获取或创建采集器实例（同一时刻只允许一个）。"""
    global _active_collector
    if _active_collector is not None and _active_collector.status != "closed":
        return _active_collector

    from app.services.collector.interactive_browser import InteractiveBrowserCollector

    _active_collector = InteractiveBrowserCollector()
    return _active_collector


async def close_collector() -> None:
    """关闭当前采集器。"""
    global _active_collector
    if _active_collector:
        await _active_collector.close()
        _active_collector = None


def get_collector_status() -> dict:
    """获取当前采集器状态。"""
    if _active_collector is None or _active_collector.status == "closed":
        return {"status": "idle", "platform": "", "query": "", "product_count": 0}
    return _active_collector.get_status()
