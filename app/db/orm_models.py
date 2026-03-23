from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# ---- 1. products ----

class ProductRow(Base):
    __tablename__ = "products"

    product_id = Column(Text, primary_key=True)
    sku = Column(Text)
    name = Column(Text, nullable=False)
    category = Column(Text)
    brand = Column(Text)
    attributes = Column(JSONB, nullable=False, server_default="{}")
    source_platform = Column(Text)
    source_url = Column(Text)
    raw_data = Column(JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---- 2. courses ----

class CourseRow(Base):
    __tablename__ = "courses"

    course_id = Column(Text, primary_key=True)
    product_id = Column(Text)
    product_name = Column(Text, nullable=False)
    objective = Column(Text, nullable=False)
    required_points = Column(JSONB, nullable=False, server_default="[]")
    product_facts = Column(JSONB, nullable=False, server_default="{}")
    content_version = Column(Integer, nullable=False, default=0)
    latest_content = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---- 3. training_attempts ----

class TrainingAttemptRow(Base):
    __tablename__ = "training_attempts"

    attempt_id = Column(Text, primary_key=True)
    course_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    audio_url = Column(Text)
    mock_transcript = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---- 4. comparison_tasks ----

class ComparisonTaskRow(Base):
    __tablename__ = "comparison_tasks"

    comparison_task_id = Column(Text, primary_key=True)
    source_product_id = Column(Text, nullable=False)
    source_product_name = Column(Text, nullable=False)
    targets = Column(JSONB, nullable=False, server_default="[]")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---- 5. tasks ----

class TaskRow(Base):
    __tablename__ = "tasks"

    task_id = Column(Text, primary_key=True)
    trace_id = Column(Text, nullable=False)
    task_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="pending")
    input = Column("input", JSONB, nullable=False, server_default="{}")
    output = Column(JSONB)
    error = Column(Text)
    agent_id = Column(Text)       # AgentsOffice: 关联 Agent
    agent_slug = Column(Text)     # AgentsOffice: Agent slug 冗余字段
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed')"),
    )


# ---- 6. agent_events ----

class AgentEventRow(Base):
    __tablename__ = "agent_events"

    event_id = Column(BigInteger, primary_key=True, autoincrement=True)
    trace_id = Column(Text, nullable=False)
    agent_name = Column(Text, nullable=False)
    event_type = Column(Text, nullable=False)
    session_id = Column(Text)
    payload = Column(JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---- 7. audit_logs ----

class AuditLogRow(Base):
    __tablename__ = "audit_logs"

    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    trace_id = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    actor = Column(Text)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(Text, nullable=False)
    before_state = Column(JSONB)
    after_state = Column(JSONB)
    detail = Column("detail", JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---- 8. agents (AgentsOffice) ----

class AgentRow(Base):
    __tablename__ = "agents"

    agent_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
    slug = Column(Text, nullable=False, unique=True)
    description = Column(Text)
    agent_type = Column(Text, nullable=False, default="general")
    status = Column(Text, nullable=False, default="idle")
    model_config = Column(JSONB, nullable=False, server_default="{}")
    last_active_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    extra_metadata = Column("metadata", JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('idle', 'running', 'error', 'disabled')"),
    )


# ---- 9. skills (AgentsOffice) ----

class SkillRow(Base):
    __tablename__ = "skills"

    skill_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
    display_name = Column(Text, nullable=False)
    description = Column(Text)
    skill_type = Column(Text, nullable=False, default="tool")
    endpoint = Column(Text)
    config = Column(JSONB, nullable=False, server_default="{}")
    status = Column(Text, nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("skill_type IN ('tool', 'api', 'knowledge', 'internal')"),
        CheckConstraint("status IN ('active', 'deprecated', 'disabled')"),
    )


# ---- 10. agent_skills (AgentsOffice) ----

# (moved below)


# ---- 13. conversations (AgentsOffice Chat History) ----

class ConversationRow(Base):
    __tablename__ = "conversations"

    conversation_id = Column(Text, primary_key=True)
    title = Column(Text, nullable=False, server_default="")
    status = Column(Text, nullable=False, server_default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived', 'deleted')"),
    )


# ---- 14. chat_messages (AgentsOffice Chat History) ----

class ChatMessageRow(Base):
    __tablename__ = "chat_messages"

    message_id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(Text, ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False)
    role = Column(Text, nullable=False)
    agent_slug = Column(Text)
    agent_name = Column(Text)
    content = Column(Text, nullable=False, server_default="")
    message_type = Column(Text)
    extra_metadata = Column("metadata", JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---- 10 (original). agent_skills (AgentsOffice) ----

class AgentSkillRow(Base):
    __tablename__ = "agent_skills"

    agent_id = Column(Text, ForeignKey("agents.agent_id"), primary_key=True)
    skill_id = Column(Text, ForeignKey("skills.skill_id"), primary_key=True)
    config = Column(JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---- 11. cost_records (AgentsOffice) ----

class CostRecordRow(Base):
    __tablename__ = "cost_records"

    record_id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(Text, ForeignKey("agents.agent_id"))
    agent_slug = Column(Text, nullable=False)
    task_id = Column(Text)
    trace_id = Column(Text, nullable=False)
    model_name = Column(Text, nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    input_cost = Column(Numeric(12, 6), nullable=False, default=0)
    output_cost = Column(Numeric(12, 6), nullable=False, default=0)
    total_cost = Column(Numeric(12, 6), nullable=False, default=0)
    duration_ms = Column(Integer)
    extra_metadata = Column("metadata", JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---- 12. model_pricing (AgentsOffice) ----

class DashboardRow(Base):
    __tablename__ = "dashboards"

    dashboard_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False, unique=True)
    description = Column(Text)
    template_key = Column(Text)  # 来源模板 key（如 "618", "double11", "daily"）
    layout = Column(JSONB, nullable=False, server_default="[]")  # 大屏布局配置
    charts = Column(JSONB, nullable=False, server_default="[]")  # ECharts 图表配置列表
    data_sources = Column(JSONB, nullable=False, server_default="[]")  # 数据源配置
    refresh_config = Column(JSONB, nullable=False, server_default="{}")  # 刷新策略
    status = Column(Text, nullable=False, default="draft")
    created_by = Column(Text)  # agent_slug
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active', 'archived')"),
    )


class ModelPricingRow(Base):
    __tablename__ = "model_pricing"

    model_name = Column(Text, primary_key=True)
    display_name = Column(Text, nullable=False)
    provider = Column(Text, nullable=False, default="openai")
    input_price_per_1k = Column(Numeric(10, 6), nullable=False)
    output_price_per_1k = Column(Numeric(10, 6), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
