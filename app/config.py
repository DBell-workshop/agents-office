from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()  # 从项目根目录 .env 文件加载环境变量


def _get_database_url_sync() -> Optional[str]:
    val = os.getenv("DATABASE_URL_SYNC", "").strip()
    return val if val else None


@dataclass(frozen=True)
class Settings:
    # ---------- 数据库 ----------
    database_url_sync: Optional[str] = field(default_factory=_get_database_url_sync)

    # ---------- LLM API Keys ----------
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "").strip()
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "").strip()

    # ---------- 默认模型 ----------
    default_llm_model: str = os.getenv("DEFAULT_LLM_MODEL", "gemini/gemini-2.0-flash").strip()

    # ---------- 数据源 ----------
    datasource_mode: str = os.getenv("DATASOURCE_MODE", "mock").strip().lower()

    # ---------- OpenClaw（已弃用，保留向后兼容） ----------
    openclaw_mode: str = os.getenv("OPENCLAW_MODE", "mock").strip().lower()
    openclaw_remote_base_url: str = os.getenv("OPENCLAW_REMOTE_BASE_URL", "http://127.0.0.1:9001").strip()
    openclaw_timeout_seconds: float = float(os.getenv("OPENCLAW_TIMEOUT_SECONDS", "15"))

    @property
    def has_any_llm_key(self) -> bool:
        """是否配置了至少一个 LLM API Key。"""
        return bool(
            self.gemini_api_key
            or self.anthropic_api_key
            or self.openai_api_key
            or self.deepseek_api_key
            or self.dashscope_api_key
        )


settings = Settings()
