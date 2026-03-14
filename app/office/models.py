"""AgentsOffice 容器层 Pydantic 请求/响应模型。"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---- Agent 模型 ----

AgentStatus = Literal["idle", "running", "error", "disabled"]
AgentType = Literal["general", "generator", "evaluator", "collector", "auditor"]


class AgentCreateRequest(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    agent_type: str = "general"
    model_config_data: Dict[str, Any] = Field(default_factory=dict, alias="model_config")
    extra_metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata")

    model_config = {"populate_by_name": True}


class AgentUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    agent_type: Optional[str] = None
    model_config_data: Optional[Dict[str, Any]] = Field(default=None, alias="model_config")
    extra_metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata")

    model_config = {"populate_by_name": True}


class AgentStatusUpdateRequest(BaseModel):
    status: AgentStatus
    error_message: Optional[str] = None


# ---- Skill 模型 ----

SkillType = Literal["tool", "api", "knowledge", "internal"]
SkillStatus = Literal["active", "deprecated", "disabled"]


class SkillCreateRequest(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    skill_type: str = "tool"
    endpoint: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class SkillResponse(BaseModel):
    skill_id: str
    name: str
    display_name: str
    description: Optional[str] = None
    skill_type: str
    endpoint: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: str
    updated_at: str


class AgentSkillBindRequest(BaseModel):
    config: Dict[str, Any] = Field(default_factory=dict)


# ---- Agent 响应模型（放在 SkillResponse 之后，避免前向引用问题） ----

class AgentResponse(BaseModel):
    agent_id: str
    name: str
    slug: str
    description: Optional[str] = None
    agent_type: str
    status: str
    agent_model_config: Dict[str, Any] = Field(default_factory=dict, alias="model_config")
    last_active_at: Optional[str] = None
    error_message: Optional[str] = None
    agent_metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata")
    created_at: str
    updated_at: str

    model_config = {"populate_by_name": True}


class AgentDetailResponse(AgentResponse):
    skills: List[SkillResponse] = Field(default_factory=list)
    recent_events: List[Dict[str, Any]] = Field(default_factory=list)
    total_cost: float = 0.0


# ---- 成本模型 ----

class CostByAgentItem(BaseModel):
    agent_id: Optional[str] = None
    agent_slug: str
    agent_name: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    call_count: int = 0


class CostByModelItem(BaseModel):
    model_name: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    call_count: int = 0


class CostSummary(BaseModel):
    period: str
    total_cost: float = 0.0
    total_tokens: int = 0
    call_count: int = 0


class CostSummaryResponse(BaseModel):
    today: CostSummary
    this_week: CostSummary
    this_month: CostSummary


# ---- 任务模型（复用现有 tasks 表） ----

class TaskListItem(BaseModel):
    task_id: str
    trace_id: str
    task_type: str
    status: str
    agent_id: Optional[str] = None
    agent_slug: Optional[str] = None
    created_at: str
    updated_at: str


class TaskDetailResponse(BaseModel):
    task_id: str
    trace_id: str
    task_type: str
    status: str
    agent_id: Optional[str] = None
    agent_slug: Optional[str] = None
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str
    events: List[Dict[str, Any]] = Field(default_factory=list)


# ---- 事件模型（复用现有 agent_events 表） ----

class EventListItem(BaseModel):
    event_id: int
    trace_id: str
    agent_name: str
    event_type: str
    session_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
