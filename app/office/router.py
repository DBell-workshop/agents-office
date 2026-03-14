"""AgentsOffice 容器层 API Router -- 挂载到 /api/v1/office/。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field

from app.models import ApiEnvelope, make_id
from app.office.models import (
    AgentCreateRequest,
    AgentSkillBindRequest,
    AgentStatusUpdateRequest,
    AgentUpdateRequest,
    SkillCreateRequest,
)
from app.office.store import office_store

logger = logging.getLogger(__name__)
router = APIRouter()


def _envelope(trace_id: str, data: dict, error: Optional[str] = None) -> ApiEnvelope:
    return ApiEnvelope(trace_id=trace_id, request_id=make_id("req"), data=data, error=error)


# ================================================================
# Chat API — 用户对话入口
# ================================================================

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    history: List[Dict[str, str]] = Field(default_factory=list)


@router.post("/chat")
def chat(payload: ChatRequest) -> ApiEnvelope:
    """用户发送消息，调度员路由到合适的 Agent 处理。"""
    trace_id = make_id("trc")
    conversation_id = payload.conversation_id or make_id("conv")

    try:
        from app.services.dispatcher import dispatch

        # 读取 per-agent 模型配置
        agent_models = {}
        try:
            if office_store is not None:
                agent_models = office_store.get_agent_model_configs()
        except Exception:
            pass  # 未配置时使用默认模型

        result = dispatch(
            user_message=payload.message,
            conversation_history=payload.history or None,
            dispatcher_model=agent_models.get("dispatcher"),
            agent_models=agent_models,
        )

        return _envelope(
            trace_id=trace_id,
            data={
                "conversation_id": conversation_id,
                "messages": result["messages"],
                "agent_movements": result["agent_movements"],
            },
        )
    except Exception as e:
        logger.exception("Chat dispatch failed")
        return _envelope(
            trace_id=trace_id,
            data={
                "conversation_id": conversation_id,
                "messages": [
                    {
                        "role": "system",
                        "agent_slug": "system",
                        "agent_name": "系统",
                        "content": f"调度员暂时无法响应，请稍后再试。错误: {str(e)[:200]}",
                    }
                ],
                "agent_movements": [],
            },
            error=str(e)[:200],
        )


def _require_store():
    """确保 office_store 可用，否则抛 503。"""
    if office_store is None:
        raise HTTPException(
            status_code=503,
            detail="Database not configured. Set DATABASE_URL_SYNC to enable AgentsOffice.",
        )
    return office_store


# ================================================================
# Agent 管理 API
# ================================================================

@router.post("/agents")
def create_agent(payload: AgentCreateRequest) -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    agent_id = make_id("agt")
    data = {
        "name": payload.name,
        "slug": payload.slug,
        "description": payload.description,
        "agent_type": payload.agent_type,
        "model_config": payload.model_config_data,
        "metadata": payload.extra_metadata,
    }
    agent = store.create_agent(agent_id, data)
    return _envelope(trace_id=trace_id, data=agent)


@router.get("/agents")
def list_agents(
    status: Optional[str] = Query(None),
    agent_type: Optional[str] = Query(None),
) -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    agents = store.list_agents(status=status, agent_type=agent_type)
    return _envelope(trace_id=trace_id, data={"agents": agents, "total": len(agents)})


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str) -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    agent = store.get_agent_detail(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return _envelope(trace_id=trace_id, data=agent)


@router.put("/agents/{agent_id}")
def update_agent(agent_id: str, payload: AgentUpdateRequest) -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    data = {}
    if payload.name is not None:
        data["name"] = payload.name
    if payload.description is not None:
        data["description"] = payload.description
    if payload.agent_type is not None:
        data["agent_type"] = payload.agent_type
    if payload.model_config_data is not None:
        data["model_config"] = payload.model_config_data
    if payload.extra_metadata is not None:
        data["metadata"] = payload.extra_metadata
    agent = store.update_agent(agent_id, data)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return _envelope(trace_id=trace_id, data=agent)


@router.patch("/agents/{agent_id}/status")
def update_agent_status(agent_id: str, payload: AgentStatusUpdateRequest) -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    agent = store.update_agent_status(
        agent_id,
        status=payload.status,
        error_message=payload.error_message,
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return _envelope(trace_id=trace_id, data=agent)


# ================================================================
# Skills 管理 API
# ================================================================

@router.post("/skills")
def create_skill(payload: SkillCreateRequest) -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    skill_id = make_id("skl")
    data = {
        "name": payload.name,
        "display_name": payload.display_name,
        "description": payload.description,
        "skill_type": payload.skill_type,
        "endpoint": payload.endpoint,
        "config": payload.config,
    }
    skill = store.create_skill(skill_id, data)
    return _envelope(trace_id=trace_id, data=skill)


@router.get("/skills")
def list_skills(
    skill_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
) -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    skills = store.list_skills(skill_type=skill_type, status=status)
    return _envelope(trace_id=trace_id, data={"skills": skills, "total": len(skills)})


@router.post("/agents/{agent_id}/skills/{skill_id}")
def bind_skill(
    agent_id: str,
    skill_id: str,
    payload: Optional[AgentSkillBindRequest] = None,
) -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    config = payload.config if payload else {}
    ok = store.bind_skill(agent_id, skill_id, config=config)
    if not ok:
        raise HTTPException(status_code=404, detail="agent or skill not found")
    return _envelope(trace_id=trace_id, data={"agent_id": agent_id, "skill_id": skill_id, "bound": True})


@router.delete("/agents/{agent_id}/skills/{skill_id}")
def unbind_skill(agent_id: str, skill_id: str) -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    ok = store.unbind_skill(agent_id, skill_id)
    if not ok:
        raise HTTPException(status_code=404, detail="binding not found")
    return _envelope(trace_id=trace_id, data={"agent_id": agent_id, "skill_id": skill_id, "unbound": True})


# ================================================================
# Agent 配置 API（per-agent 模型/参数配置）
# ================================================================

class AgentConfigPayload(BaseModel):
    # 模型配置
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    # 身份定义
    display_name: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    color: Optional[str] = None
    active: Optional[bool] = None


@router.get("/agent-config")
def get_agent_config() -> ApiEnvelope:
    """返回所有 Agent 的完整定义（模型配置 + 身份/行为）。

    合并 DB 配置 + BUILTIN_AGENTS 默认值，确保前端拿到所有 agent 的模型信息。
    """
    trace_id = make_id("trc")
    store = _require_store()
    db_configs = store.get_all_agent_configs()

    # 从 dispatcher 加载 BUILTIN 定义，补充 DB 中缺失的 agent
    from app.services.dispatcher import BUILTIN_AGENTS
    from app.config import settings

    merged: Dict[str, Any] = {}
    for slug, defn in BUILTIN_AGENTS.items():
        merged[slug] = {
            "model_name": defn.get("model_name") or settings.default_llm_model,
            "temperature": defn.get("temperature", 0.7),
            "max_tokens": defn.get("max_tokens", 2048),
            "display_name": defn.get("display_name", slug),
            "role": defn.get("role", ""),
            "system_prompt": defn.get("system_prompt", ""),
            "color": defn.get("color", ""),
            "active": defn.get("active", True),
        }

    # DB 配置覆盖 BUILTIN 默认值
    for slug, cfg in db_configs.items():
        if slug in merged:
            for k, v in cfg.items():
                if v is not None and v != "":
                    merged[slug][k] = v
        else:
            merged[slug] = cfg

    return _envelope(trace_id=trace_id, data={"configs": merged})


@router.put("/agent-config/{slug}")
def update_agent_config(slug: str, payload: AgentConfigPayload) -> ApiEnvelope:
    """更新指定 Agent 的完整配置（模型 + 身份/行为）。"""
    trace_id = make_id("trc")
    store = _require_store()
    config: Dict[str, Any] = {
        "model_name": payload.model_name,
        "temperature": payload.temperature,
        "max_tokens": payload.max_tokens,
    }
    # 只传入非 None 的身份字段
    if payload.display_name is not None:
        config["display_name"] = payload.display_name
    if payload.role is not None:
        config["role"] = payload.role
    if payload.system_prompt is not None:
        config["system_prompt"] = payload.system_prompt
    if payload.color is not None:
        config["color"] = payload.color
    if payload.active is not None:
        config["active"] = payload.active
    agent = store.update_agent_config_by_slug(slug, config)
    return _envelope(trace_id=trace_id, data=agent)


# ================================================================
# AI 提示词优化 API
# ================================================================

class RefinePromptRequest(BaseModel):
    draft: str = Field(..., min_length=1, description="用户输入的自然语言描述")
    agent_name: str = ""
    agent_role: str = ""


_REFINE_META_PROMPT = """\
你是一位专业的 AI Agent 系统提示词设计师。

用户正在为一个名为「{agent_name}」的 AI Agent 编写角色定义。
该 Agent 的职责描述为：{agent_role}

用户提供了一段初步想法（可能很简短或不够结构化），请你根据这段内容，\
生成一份专业、完整、结构化的 system prompt。

## 输出要求
1. 以「你是...」开头，明确定义角色身份
2. 用 Markdown 分节组织（## 你的职责、## 工作方式、## 回复风格、## 注意事项）
3. 保留用户原始意图，不要凭空发明用户没有提到的职责
4. 如果用户的描述很模糊，做合理推断并在括号中标注「(根据上下文推断)」
5. 语气专业但不生硬，适合作为 AI Agent 的指令
6. 直接输出 system prompt 内容，不要加任何前言或解释
"""


@router.post("/agent-config/{slug}/refine-prompt")
def refine_prompt(slug: str, payload: RefinePromptRequest) -> ApiEnvelope:
    """用 AI 将用户的自然语言描述优化为专业的 system prompt。"""
    trace_id = make_id("trc")
    _require_store()

    from app.services.llm_service import chat_completion

    # 读取当前 agent 使用的模型，用同一个模型来做优化
    store = _require_store()
    all_configs = store.get_all_agent_configs()
    agent_cfg = all_configs.get(slug, {})
    refine_model = agent_cfg.get("model_name") or None  # None = 使用系统默认模型

    meta_prompt = _REFINE_META_PROMPT.format(
        agent_name=payload.agent_name or slug,
        agent_role=payload.agent_role or "未指定",
    )

    try:
        result = chat_completion(
            messages=[
                {"role": "system", "content": meta_prompt},
                {"role": "user", "content": payload.draft},
            ],
            model=refine_model,
            temperature=0.6,
            max_tokens=2048,
        )
        refined = result["content"].strip()
        return _envelope(
            trace_id=trace_id,
            data={
                "refined_prompt": refined,
                "model_used": result.get("model", ""),
                "usage": result.get("usage", {}),
            },
        )
    except Exception as e:
        logger.exception("Refine prompt failed")
        raise HTTPException(status_code=502, detail=f"AI 优化失败: {str(e)[:200]}")


# ================================================================
# 可用模型 API
# ================================================================

@router.get("/models")
def list_models() -> ApiEnvelope:
    """动态返回所有可用 LLM Chat 模型及定价，从 LiteLLM 实时读取。

    每个模型包含 available 字段，表示对应 provider 的 API Key 是否已配置。
    """
    from app.config import settings as app_settings

    trace_id = make_id("trc")
    models = _get_available_models(app_settings)

    provider_available = {
        "google": bool(app_settings.gemini_api_key),
        "anthropic": bool(app_settings.anthropic_api_key),
        "openai": bool(app_settings.openai_api_key),
        "deepseek": bool(app_settings.deepseek_api_key),
    }

    for m in models:
        m["available"] = provider_available.get(m.get("provider", ""), False)

    return _envelope(
        trace_id=trace_id,
        data={
            "models": models,
            "total": len(models),
            "provider_status": provider_available,
        },
    )


# provider 到友好名称的映射
_PROVIDER_MAP = {
    "gemini": "google",
    "openai": "openai",
    "anthropic": "anthropic",
    "deepseek": "deepseek",
}

# 推荐模型精选列表 — 只展示每个 provider 的主力 chat 模型
# 按 provider 分组，组内按推荐度排序
_RECOMMENDED_MODELS: Dict[str, list] = {
    "gemini": [
        "gemini/gemini-2.5-flash",
        "gemini/gemini-2.5-pro",
        "gemini/gemini-2.0-flash",
        "gemini/gemini-2.5-flash-lite",
        "gemini/gemini-3-flash-preview",
        "gemini/gemini-3-pro-preview",
    ],
    "openai": [
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-mini",
        "o3",
        "o3-mini",
        "o4-mini",
    ],
    "anthropic": [
        "claude-sonnet-4-6",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
        "claude-opus-4-6",
        "claude-opus-4-5",
    ],
    "deepseek": [
        "deepseek/deepseek-chat",
        "deepseek/deepseek-reasoner",
        "deepseek/deepseek-r1",
        "deepseek/deepseek-v3.2",
    ],
}


# 手工覆盖的显示名 — 对自动生成效果不好的模型单独指定
_DISPLAY_NAME_OVERRIDES: Dict[str, str] = {
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "claude-sonnet-4-5": "Claude Sonnet 4.5",
    "claude-haiku-4-5": "Claude Haiku 4.5",
    "claude-opus-4-6": "Claude Opus 4.6",
    "claude-opus-4-5": "Claude Opus 4.5",
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o Mini",
    "gpt-4.1": "GPT-4.1",
    "gpt-4.1-mini": "GPT-4.1 Mini",
    "gpt-4.1-nano": "GPT-4.1 Nano",
    "o3": "o3",
    "o3-mini": "o3 Mini",
    "o4-mini": "o4 Mini",
    "deepseek/deepseek-chat": "DeepSeek Chat",
    "deepseek/deepseek-reasoner": "DeepSeek Reasoner",
    "deepseek/deepseek-r1": "DeepSeek R1",
    "deepseek/deepseek-v3.2": "DeepSeek V3.2",
}


def _model_display_name(model_name: str) -> str:
    """将 LiteLLM 模型标识符转成友好显示名。"""
    if model_name in _DISPLAY_NAME_OVERRIDES:
        return _DISPLAY_NAME_OVERRIDES[model_name]
    name = model_name
    # 去掉 provider 前缀
    if "/" in name:
        name = name.split("/", 1)[1]
    # 用空格替换连字符，首字母大写
    return name.replace("-", " ").title()


def _get_available_models(app_settings: Any) -> list:
    """从 LiteLLM model_cost 动态读取推荐模型列表及定价。"""
    import litellm

    cost_map = litellm.model_cost
    results = []

    for provider, model_names in _RECOMMENDED_MODELS.items():
        api_provider = _PROVIDER_MAP.get(provider, provider)
        for model_name in model_names:
            info = cost_map.get(model_name)
            if not info:
                continue
            inp_per_1k = float(info.get("input_cost_per_token", 0)) * 1000
            out_per_1k = float(info.get("output_cost_per_token", 0)) * 1000

            # 生成友好显示名
            display = _model_display_name(model_name)

            results.append({
                "model_name": model_name,
                "display_name": display,
                "provider": api_provider,
                "input_price_per_1k": round(inp_per_1k, 6),
                "output_price_per_1k": round(out_per_1k, 6),
            })

    return results


# ================================================================
# 成本监控 API
# ================================================================

@router.get("/costs/by-agent")
def costs_by_agent(
    start: Optional[str] = Query(None, description="ISO datetime"),
    end: Optional[str] = Query(None, description="ISO datetime"),
) -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    start_dt = _parse_datetime(start)
    end_dt = _parse_datetime(end)
    items = store.costs_by_agent(start=start_dt, end=end_dt)
    return _envelope(trace_id=trace_id, data={"items": items, "total": len(items)})


@router.get("/costs/by-model")
def costs_by_model(
    start: Optional[str] = Query(None, description="ISO datetime"),
    end: Optional[str] = Query(None, description="ISO datetime"),
) -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    start_dt = _parse_datetime(start)
    end_dt = _parse_datetime(end)
    items = store.costs_by_model(start=start_dt, end=end_dt)
    return _envelope(trace_id=trace_id, data={"items": items, "total": len(items)})


@router.get("/costs/summary")
def cost_summary() -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    summary = store.cost_summary()
    return _envelope(trace_id=trace_id, data=summary)


# ================================================================
# 任务中心 API
# ================================================================

@router.get("/tasks")
def list_tasks(
    status: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    agent_slug: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    tasks = store.list_tasks(
        status=status,
        task_type=task_type,
        agent_slug=agent_slug,
        limit=limit,
        offset=offset,
    )
    return _envelope(trace_id=trace_id, data={"tasks": tasks, "total": len(tasks)})


@router.get("/tasks/{task_id}")
def get_task_detail(task_id: str) -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    task = store.get_task_detail(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return _envelope(trace_id=trace_id, data=task)


# ================================================================
# 事件日志 API
# ================================================================

@router.get("/events")
def list_events(
    agent_name: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    trace_id_filter: Optional[str] = Query(None, alias="trace_id"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ApiEnvelope:
    trace_id = make_id("trc")
    store = _require_store()
    events = store.list_events(
        agent_name=agent_name,
        event_type=event_type,
        trace_id=trace_id_filter,
        limit=limit,
        offset=offset,
    )
    return _envelope(trace_id=trace_id, data={"events": events, "total": len(events)})


# ================================================================
# 文件上传 API（数据工程师用）
# ================================================================

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)) -> ApiEnvelope:
    """上传 CSV/Excel 文件，返回文件路径和解析预览。"""
    trace_id = make_id("trc")

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("csv", "xlsx", "xls"):
        raise HTTPException(status_code=400, detail=f"不支持的文件格式 .{ext}，请上传 .csv 或 .xlsx 文件")

    from app.services.data_engineer import UPLOAD_DIR, parse_file

    # 安全文件名
    import re
    safe_name = re.sub(r"[^\w.\-]", "_", file.filename)
    save_path = UPLOAD_DIR / safe_name

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB
        raise HTTPException(status_code=413, detail="文件过大，最大支持 50MB")

    save_path.write_bytes(content)

    # 自动解析预览
    analysis = parse_file(str(save_path))

    return _envelope(trace_id=trace_id, data={
        "file_path": str(save_path),
        "file_name": safe_name,
        "size_bytes": len(content),
        "analysis": analysis,
    })


@router.get("/uploads")
def list_uploads() -> ApiEnvelope:
    """列出所有已上传的文件。"""
    trace_id = make_id("trc")
    from app.services.data_engineer import list_uploaded_files
    files = list_uploaded_files()
    return _envelope(trace_id=trace_id, data={"files": files, "total": len(files)})


@router.get("/user-tables")
def list_user_tables_api() -> ApiEnvelope:
    """列出用户创建的所有数据表。"""
    trace_id = make_id("trc")
    from app.services.data_engineer import list_user_tables
    result = list_user_tables()
    return _envelope(trace_id=trace_id, data=result)


# ================================================================
# 辅助函数
# ================================================================

def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """将 ISO 格式字符串解析为 datetime，返回 None 表示无筛选。"""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None
