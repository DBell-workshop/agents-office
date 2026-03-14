from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_sync_engine(database_url: str):
    """创建同步 SQLAlchemy engine，配置连接池。"""
    return create_engine(
        database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


def build_session_factory(database_url: str) -> sessionmaker[Session]:
    """创建绑定到指定数据库的 session 工厂。"""
    engine = build_sync_engine(database_url)
    return sessionmaker(bind=engine, expire_on_commit=False)
