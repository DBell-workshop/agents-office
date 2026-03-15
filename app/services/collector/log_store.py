"""采集日志持久化存储 — JSON 文件。"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_LOG_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "collector_logs.json"


def _load_logs() -> List[Dict[str, Any]]:
    if not _LOG_FILE.exists():
        return []
    try:
        with open(_LOG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_logs(logs: List[Dict[str, Any]]) -> None:
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def append_log(entry: Dict[str, Any]) -> None:
    """追加一条采集日志。"""
    logs = _load_logs()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **entry,
    }
    logs.append(record)
    _save_logs(logs)


def get_logs(limit: int = 200) -> List[Dict[str, Any]]:
    """获取采集日志（最新的在后面）。"""
    logs = _load_logs()
    return logs[-limit:]


def clear_logs() -> int:
    """清空所有采集日志，返回删除条数。"""
    logs = _load_logs()
    count = len(logs)
    _save_logs([])
    return count
