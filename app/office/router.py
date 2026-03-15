"""AgentsOffice 容器层 API Router -- 挂载到 /api/v1/office/。"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.models import ApiEnvelope, ProductImportRequest, make_id
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


class DirectChatRequest(BaseModel):
    message: str
    agent_slug: str
    conversation_id: Optional[str] = None
    history: List[Dict[str, str]] = Field(default_factory=list)


@router.post("/chat")
async def chat(payload: ChatRequest) -> ApiEnvelope:
    """用户发送消息，调度员路由到合适的 Agent 处理。"""
    trace_id = make_id("trc")
    conversation_id = payload.conversation_id or make_id("conv")

    try:
        from app.services.agents import dispatch

        # 读取 per-agent 模型配置（含 api_base / api_key）
        agent_models: Dict[str, Dict[str, str]] = {}
        try:
            if office_store is not None:
                agent_models = office_store.get_agent_model_configs()
        except Exception:
            pass  # 未配置时使用默认模型

        # 持久化：如果是新会话，先创建
        is_new_conv = payload.conversation_id is None
        if is_new_conv and office_store is not None:
            try:
                office_store.create_conversation(conversation_id)
            except Exception:
                logger.warning("Failed to create conversation record")

        # 持久化用户消息
        if office_store is not None:
            try:
                office_store.add_chat_message(
                    conversation_id=conversation_id,
                    role="user",
                    content=payload.message,
                )
            except Exception:
                logger.warning("Failed to persist user message")

        # 调度员模型从 agent_models dict 中提取
        dispatcher_cfg = agent_models.get("dispatcher", {})
        dispatcher_model = dispatcher_cfg.get("model_name") if dispatcher_cfg else None

        result = await dispatch(
            user_message=payload.message,
            conversation_history=payload.history or None,
            dispatcher_model=dispatcher_model,
            agent_models=agent_models,
        )

        # 持久化 Agent 回复消息
        if office_store is not None:
            for msg in result.get("messages", []):
                try:
                    office_store.add_chat_message(
                        conversation_id=conversation_id,
                        role=msg.get("role", "agent"),
                        content=msg.get("content", ""),
                        agent_slug=msg.get("agent_slug"),
                        agent_name=msg.get("agent_name"),
                        message_type=msg.get("message_type"),
                        metadata={
                            k: v for k, v in msg.items()
                            if k in ("usage", "movement")
                        },
                    )
                except Exception:
                    logger.warning("Failed to persist agent message")

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


@router.post("/chat/direct")
async def chat_direct(payload: DirectChatRequest) -> ApiEnvelope:
    """一对一私聊：绕过调度员，直接和指定 Agent 对话。"""
    trace_id = make_id("trc")
    conversation_id = payload.conversation_id or make_id("conv")

    try:
        from app.services.agents import run_agent, load_agent_registry, BUILTIN_AGENTS

        # 加载 Agent 定义
        registry = load_agent_registry()
        agent_defn = registry.get(payload.agent_slug)
        if not agent_defn:
            raise HTTPException(status_code=404, detail=f"Agent '{payload.agent_slug}' not found")

        # 读取 per-agent 模型配置
        agent_api_base = None
        agent_api_key = None
        target_model = None
        if office_store is not None:
            try:
                agent_models = office_store.get_agent_model_configs()
                if payload.agent_slug in agent_models:
                    ac = agent_models[payload.agent_slug]
                    target_model = ac.get("model_name") or None
                    agent_api_base = ac.get("api_base") or None
                    agent_api_key = ac.get("api_key") or None
            except Exception:
                pass
        target_model = target_model or agent_defn.get("model_name")

        # 持久化会话和用户消息
        is_new_conv = payload.conversation_id is None
        if is_new_conv and office_store is not None:
            try:
                agent_name = agent_defn.get("display_name", payload.agent_slug)
                office_store.create_conversation(conversation_id, title=f"与{agent_name}的私聊")
            except Exception:
                logger.warning("Failed to create direct conversation")

        if office_store is not None:
            try:
                office_store.add_chat_message(
                    conversation_id=conversation_id,
                    role="user",
                    content=payload.message,
                )
            except Exception:
                logger.warning("Failed to persist user message")

        # 直接调用 Agent（不经过调度员）
        result = await run_agent(
            agent_slug=payload.agent_slug,
            agent_defn=agent_defn,
            user_message=payload.message,
            task_summary=payload.message,
            conversation_history=payload.history or None,
            model=target_model,
            api_base=agent_api_base,
            api_key=agent_api_key,
        )

        # 持久化 Agent 回复
        if office_store is not None:
            for msg in result.get("messages", []):
                try:
                    office_store.add_chat_message(
                        conversation_id=conversation_id,
                        role=msg.get("role", "agent"),
                        content=msg.get("content", ""),
                        agent_slug=msg.get("agent_slug"),
                        agent_name=msg.get("agent_name"),
                        message_type=msg.get("message_type"),
                    )
                except Exception:
                    logger.warning("Failed to persist agent message")

        return _envelope(
            trace_id=trace_id,
            data={
                "conversation_id": conversation_id,
                "messages": result["messages"],
                "agent_movements": [],
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Direct chat failed")
        return _envelope(
            trace_id=trace_id,
            data={
                "conversation_id": conversation_id,
                "messages": [{
                    "role": "system",
                    "agent_slug": "system",
                    "agent_name": "系统",
                    "content": f"Agent 暂时无法响应: {str(e)[:200]}",
                }],
                "agent_movements": [],
            },
            error=str(e)[:200],
        )


# ================================================================
# SSE 流式 Chat API — 实时推送调度和 Agent 响应
# ================================================================

@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest):
    """SSE 流式聊天 — 实时推送调度和 Agent 响应事件。"""
    conversation_id = payload.conversation_id or make_id("conv")

    async def event_generator():
        try:
            from app.services.agents import dispatch_stream

            agent_models: Dict[str, Dict[str, str]] = {}
            try:
                if office_store is not None:
                    agent_models = office_store.get_agent_model_configs()
            except Exception:
                pass

            if payload.conversation_id is None and office_store is not None:
                try:
                    office_store.create_conversation(conversation_id)
                except Exception:
                    logger.warning("Failed to create conversation record")

            if office_store is not None:
                try:
                    office_store.add_chat_message(
                        conversation_id=conversation_id,
                        role="user",
                        content=payload.message,
                    )
                except Exception:
                    logger.warning("Failed to persist user message")

            dispatcher_cfg = agent_models.get("dispatcher", {})
            dispatcher_model = dispatcher_cfg.get("model_name") if dispatcher_cfg else None

            # 先推送 conversation_id
            yield f"event: init\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"

            async for event in dispatch_stream(
                user_message=payload.message,
                conversation_history=payload.history or None,
                dispatcher_model=dispatcher_model,
                agent_models=agent_models,
            ):
                event_type = event["event"]
                event_data = event["data"]

                # 持久化每条消息
                if event_type in ("routing", "process", "message") and office_store is not None:
                    try:
                        office_store.add_chat_message(
                            conversation_id=conversation_id,
                            role=event_data.get("role", "agent"),
                            content=event_data.get("content", ""),
                            agent_slug=event_data.get("agent_slug"),
                            agent_name=event_data.get("agent_name"),
                            message_type=event_data.get("message_type"),
                            metadata={
                                k: v for k, v in event_data.items()
                                if k in ("usage", "movement")
                            },
                        )
                    except Exception:
                        logger.warning("Failed to persist streamed message")

                yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.exception("SSE chat stream failed")
            error_data = {
                "role": "system",
                "agent_slug": "system",
                "agent_name": "系统",
                "content": f"调度员暂时无法响应: {str(e)[:200]}",
            }
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/direct/stream")
async def chat_direct_stream(payload: DirectChatRequest):
    """SSE 流式私聊 — 绕过调度员，直接和指定 Agent 流式对话。"""
    conversation_id = payload.conversation_id or make_id("conv")

    async def event_generator():
        try:
            from app.services.agents import run_agent_stream, load_agent_registry

            registry = load_agent_registry()
            agent_defn = registry.get(payload.agent_slug)
            if not agent_defn:
                yield f"event: error\ndata: {json.dumps({'content': f'Agent {payload.agent_slug} not found'}, ensure_ascii=False)}\n\n"
                return

            agent_api_base = None
            agent_api_key = None
            target_model = None
            if office_store is not None:
                try:
                    agent_models = office_store.get_agent_model_configs()
                    if payload.agent_slug in agent_models:
                        ac = agent_models[payload.agent_slug]
                        target_model = ac.get("model_name") or None
                        agent_api_base = ac.get("api_base") or None
                        agent_api_key = ac.get("api_key") or None
                except Exception:
                    pass
            target_model = target_model or agent_defn.get("model_name")

            if payload.conversation_id is None and office_store is not None:
                try:
                    agent_name = agent_defn.get("display_name", payload.agent_slug)
                    office_store.create_conversation(conversation_id, title=f"与{agent_name}的私聊")
                except Exception:
                    logger.warning("Failed to create direct conversation")

            if office_store is not None:
                try:
                    office_store.add_chat_message(
                        conversation_id=conversation_id,
                        role="user",
                        content=payload.message,
                    )
                except Exception:
                    logger.warning("Failed to persist user message")

            yield f"event: init\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"

            # 检查该 Agent 是否有可用的 Skill — 如果有，优先走 Skill 流程
            from app.services.skills.registry import get_skills_for_agent
            agent_skills = get_skills_for_agent(payload.agent_slug)

            if agent_skills:
                # 有 Skill → 走 SkillEngine（比价专员等）
                from app.services.skills.engine import SkillEngine
                skill = agent_skills[0]  # 取第一个匹配的 Skill
                async for event in SkillEngine.start_skill(
                    skill_name=skill.name,
                    agent_slug=payload.agent_slug,
                    params={"query": payload.message},
                ):
                    event_type = event["event"]
                    event_data = event["data"]
                    yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
            else:
                # 无 Skill → 走普通 LLM 对话
                async for event in run_agent_stream(
                    agent_slug=payload.agent_slug,
                    agent_defn=agent_defn,
                    user_message=payload.message,
                    task_summary=payload.message,
                    conversation_history=payload.history or None,
                    model=target_model,
                    api_base=agent_api_base,
                    api_key=agent_api_key,
                ):
                    event_type = event["event"]
                    event_data = event["data"]

                    if event_type in ("process", "message") and office_store is not None:
                        try:
                            office_store.add_chat_message(
                                conversation_id=conversation_id,
                                role=event_data.get("role", "agent"),
                                content=event_data.get("content", ""),
                                agent_slug=event_data.get("agent_slug"),
                                agent_name=event_data.get("agent_name"),
                                message_type=event_data.get("message_type"),
                            )
                        except Exception:
                            logger.warning("Failed to persist agent message")

                    yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"

            yield f"event: done\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"

        except Exception as e:
            logger.exception("SSE direct chat stream failed")
            error_data = {
                "role": "system",
                "agent_slug": "system",
                "agent_name": "系统",
                "content": f"Agent 暂时无法响应: {str(e)[:200]}",
            }
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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
# Skill 执行 API — 多步骤技能的启动、用户交互、会话管理
# ================================================================

class SkillStartRequest(BaseModel):
    skill_name: str = Field(..., description="Skill 名称，如 cross_platform_compare")
    agent_slug: str = Field(default="shopping_guide", description="触发 Skill 的 Agent")
    params: Dict[str, Any] = Field(default_factory=dict, description="Skill 启动参数")


class SkillRespondRequest(BaseModel):
    user_input: Dict[str, Any] = Field(..., description="用户响应数据，如 {product_ids: [...]}")


@router.post("/skills/start")
async def start_skill_session(payload: SkillStartRequest):
    """启动一个 Skill 会话，返回 SSE 事件流。

    Skill 是多步骤有状态的 Agent 技能。启动后可能暂停等待用户输入，
    前端收到 skill_interact (awaiting_user) 事件后，通过 /skills/{session_id}/respond 提交。
    """
    from app.services.skills.engine import SkillEngine

    async def event_generator():
        try:
            async for event in SkillEngine.start_skill(
                skill_name=payload.skill_name,
                agent_slug=payload.agent_slug,
                params=payload.params,
            ):
                event_type = event["event"]
                event_data = event["data"]
                yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Skill start failed")
            yield f"event: skill_error\ndata: {json.dumps({'error': str(e)[:200]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/skills/sessions/{session_id}/respond")
async def respond_skill_session(session_id: str, payload: SkillRespondRequest):
    """用户响应一个等待中的 Skill 会话，返回 SSE 事件流。"""
    from app.services.skills.engine import SkillEngine

    async def event_generator():
        try:
            async for event in SkillEngine.respond_skill(
                session_id=session_id,
                user_input=payload.user_input,
            ):
                event_type = event["event"]
                event_data = event["data"]
                yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Skill respond failed")
            yield f"event: skill_error\ndata: {json.dumps({'error': str(e)[:200]}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/skills/sessions")
def list_skill_sessions() -> ApiEnvelope:
    """列出所有活跃的 Skill 会话。"""
    from app.services.skills.engine import SkillEngine

    trace_id = make_id("trc")
    sessions = SkillEngine.list_active_sessions()
    return _envelope(trace_id=trace_id, data={"sessions": sessions, "total": len(sessions)})


@router.get("/skills/sessions/{session_id}")
def get_skill_session(session_id: str) -> ApiEnvelope:
    """获取指定 Skill 会话的详情。"""
    from app.services.skills.engine import SkillEngine

    trace_id = make_id("trc")
    session = SkillEngine.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="skill session not found")
    return _envelope(trace_id=trace_id, data={
        "session_id": session.session_id,
        "skill_name": session.skill_name,
        "agent_slug": session.agent_slug,
        "state": session.state,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    })


@router.get("/skills/registry")
def get_skill_registry() -> ApiEnvelope:
    """返回所有已注册的 Skill 及其可用 Agent 信息。"""
    from app.services.skills.registry import list_skills as list_registered_skills

    trace_id = make_id("trc")
    skills = list_registered_skills()
    return _envelope(trace_id=trace_id, data={"skills": skills, "total": len(skills)})


# ================================================================
# Agent 模板 API
# ================================================================

@router.get("/agent-templates")
def get_agent_templates() -> ApiEnvelope:
    """返回所有预设 Agent 模板，供用户创建新 Agent 时选择。"""
    from app.services.agents import BUILTIN_AGENTS

    trace_id = make_id("trc")
    templates = []
    for slug, defn in BUILTIN_AGENTS.items():
        templates.append({
            "slug": slug,
            "display_name": defn.get("display_name", slug),
            "role": defn.get("role", ""),
            "color": defn.get("color", "#cccccc"),
            "room_id": defn.get("room_id", "workspace"),
            "system_prompt": defn.get("system_prompt", ""),
            "tools": defn.get("tools", ""),
        })
    # 也加入调度员作为模板
    templates.insert(0, {
        "slug": "dispatcher",
        "display_name": "调度员",
        "role": "任务调度，理解用户需求并分配给合适的 Agent",
        "color": "#ff6b6b",
        "room_id": "manager",
        "system_prompt": "",
        "tools": "",
    })
    return _envelope(trace_id=trace_id, data={"templates": templates})


# ================================================================
# Agent 注册表 API（前端唯一数据源）
# ================================================================

@router.get("/agent-registry")
def get_agent_registry() -> ApiEnvelope:
    """返回完整 Agent 注册表（含 dispatcher），作为前端所有组件的唯一数据源。

    合并 BUILTIN_AGENTS + DB 自定义配置，返回前端渲染所需的全部字段。
    前端 ChatBox、OfficeScene、AgentStatusBar 均从此接口加载 Agent 列表。
    """
    from app.services.agents import get_full_registry

    trace_id = make_id("trc")
    registry = get_full_registry()

    agents = []
    for slug, defn in registry.items():
        agents.append({
            "slug": slug,
            "display_name": defn.get("display_name", slug),
            "role": defn.get("role", ""),
            "color": defn.get("color", "#cccccc"),
            "room_id": defn.get("room_id", "workspace"),
            "phaser_agent_id": defn.get("phaser_agent_id", ""),
            "is_dispatcher": defn.get("is_dispatcher", False),
        })
    return _envelope(trace_id=trace_id, data={"agents": agents})


# ================================================================
# Agent 配置 API（per-agent 模型/参数配置）
# ================================================================

class AgentConfigPayload(BaseModel):
    # 模型配置
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    api_base: Optional[str] = None
    api_key: Optional[str] = None
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
    from app.services.agents import BUILTIN_AGENTS
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
    if payload.api_base is not None:
        config["api_base"] = payload.api_base
    if payload.api_key is not None:
        config["api_key"] = payload.api_key
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
        "dashscope": bool(app_settings.dashscope_api_key),
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
    "dashscope": "dashscope",
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
    "dashscope": [
        "qwen3.5-plus",
        "qwen-plus",
        "qwen-turbo",
        "qwen-max",
        "qwen-vl-max",
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
    "qwen3.5-plus": "Qwen3.5 Plus",
    "qwen-plus": "Qwen Plus",
    "qwen-turbo": "Qwen Turbo",
    "qwen-max": "Qwen Max",
    "qwen-vl-max": "Qwen VL Max（视觉）",
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
            if info:
                inp_per_1k = float(info.get("input_cost_per_token", 0)) * 1000
                out_per_1k = float(info.get("output_cost_per_token", 0)) * 1000
            else:
                # DashScope 等非 LiteLLM 原生模型，仍然展示（定价为 0）
                inp_per_1k = 0.0
                out_per_1k = 0.0

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


@router.get("/uploads/{file_name}/preview")
def preview_uploaded_file(file_name: str) -> ApiEnvelope:
    """预览已上传文件的 schema 和前几行数据。"""
    trace_id = make_id("trc")
    from app.services.data_engineer import UPLOAD_DIR, parse_file
    file_path = UPLOAD_DIR / file_name
    if not file_path.exists():
        return _envelope(trace_id=trace_id, data={"error": f"文件不存在: {file_name}"})
    result = parse_file(str(file_path))
    return _envelope(trace_id=trace_id, data=result)


@router.get("/user-tables")
def list_user_tables_api() -> ApiEnvelope:
    """列出用户创建的所有数据表。"""
    trace_id = make_id("trc")
    from app.services.data_engineer import list_user_tables
    result = list_user_tables()
    return _envelope(trace_id=trace_id, data=result)


@router.get("/user-tables/{table_name}/data")
def query_user_table_data(
    table_name: str,
    limit: int = Query(50, ge=1, le=500),
) -> ApiEnvelope:
    """查询用户表数据（仅允许 ud_ 前缀表）。"""
    trace_id = make_id("trc")
    from app.services.data_engineer import query_data
    result = query_data(table_name, limit=limit)
    return _envelope(trace_id=trace_id, data=result)


# ================================================================
# Conversation History API
# ================================================================

@router.get("/conversations")
def list_conversations(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ApiEnvelope:
    """列出所有活跃会话（按最近更新排序）。"""
    trace_id = make_id("trc")
    store = _require_store()
    items = store.list_conversations(limit=limit, offset=offset)
    return _envelope(trace_id=trace_id, data={"conversations": items, "total": len(items)})


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> ApiEnvelope:
    """获取单个会话及其所有消息。"""
    trace_id = make_id("trc")
    store = _require_store()
    result = store.get_conversation_messages(conversation_id)
    if result is None:
        return _envelope(trace_id=trace_id, data={}, error="会话不存在")
    return _envelope(trace_id=trace_id, data=result)


class ConversationUpdateRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None


@router.put("/conversations/{conversation_id}")
def update_conversation(conversation_id: str, payload: ConversationUpdateRequest) -> ApiEnvelope:
    """更新会话（标题、状态等）。"""
    trace_id = make_id("trc")
    store = _require_store()
    updates = {}
    if payload.title is not None:
        updates["title"] = payload.title
    if payload.status is not None:
        updates["status"] = payload.status
    result = store.update_conversation(conversation_id, updates)
    if result is None:
        return _envelope(trace_id=trace_id, data={}, error="会话不存在")
    return _envelope(trace_id=trace_id, data=result)


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> ApiEnvelope:
    """归档删除会话。"""
    trace_id = make_id("trc")
    store = _require_store()
    ok = store.delete_conversation(conversation_id)
    return _envelope(trace_id=trace_id, data={"deleted": ok})


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


# ================================================================
# 商品数据接入 API — 接收外部采集系统推送的商品数据
# ================================================================


@router.post("/products/import")
async def products_import(payload: ProductImportRequest) -> ApiEnvelope:
    """批量导入商品数据。

    外部采集系统（爬虫、人工录入、合作方API）按标准格式推送商品数据。
    本接口负责接收、校验、存储，供比价等下游功能消费。

    示例请求体::

        {
          "source": "jd_crawler",
          "batch_id": "batch_20260315_001",
          "products": [
            {
              "product_id": "100012345",
              "platform": "京东",
              "name": "海尔洗衣机 10KG 滚筒",
              "price": 2999.0,
              "url": "https://item.jd.com/100012345.html",
              "images": [{"url": "https://img.jd.com/xxx.jpg", "type": "main"}],
              "specs": [{"name": "容量", "value": "10KG"}]
            }
          ]
        }
    """
    trace_id = make_id("trc")
    store = _require_store()
    try:
        # 将 Pydantic 模型转为 dict 列表
        product_dicts = [item.model_dump() for item in payload.products]
        # 图片和规格需要序列化为 plain dict
        for d in product_dicts:
            d["images"] = [img if isinstance(img, dict) else img.model_dump() for img in (d.get("images") or [])]
            d["specs"] = [sp if isinstance(sp, dict) else sp.model_dump() for sp in (d.get("specs") or [])]

        batch_id = payload.batch_id or make_id("batch")
        results = store.save_products(
            products=product_dicts,
            source=payload.source,
            batch_id=batch_id,
        )
        logger.info(
            "导入商品数据: source=%s, batch_id=%s, count=%d",
            payload.source, batch_id, len(results),
        )
        return _envelope(trace_id=trace_id, data={
            "imported_count": len(results),
            "batch_id": batch_id,
            "products": results,
        })
    except Exception as e:
        logger.exception("商品数据导入失败")
        return _envelope(trace_id=trace_id, data={}, error=str(e)[:200])


@router.get("/products")
def list_products(
    platform: Optional[str] = Query(None, description="按平台筛选"),
    category: Optional[str] = Query(None, description="按类目筛选"),
    keyword: Optional[str] = Query(None, description="商品名关键词搜索"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ApiEnvelope:
    """查询已导入的商品列表。"""
    trace_id = make_id("trc")
    store = _require_store()
    products = store.list_products(
        platform=platform, category=category, keyword=keyword,
        limit=limit, offset=offset,
    )
    total = store.count_products(platform=platform, category=category, keyword=keyword)
    return _envelope(trace_id=trace_id, data={
        "products": products,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.get("/products/schema")
def products_import_schema() -> ApiEnvelope:
    """返回商品导入接口的 JSON Schema，方便外部系统对接。"""
    from app.models import ProductImportRequest

    trace_id = make_id("trc")
    return _envelope(trace_id=trace_id, data={
        "schema": ProductImportRequest.model_json_schema(),
    })


# ================================================================
# 浏览器采集器 API — 用户参与式数据采集（暂停使用，代码保留）
# 如需重新启用，取消下方注释并恢复前端入口即可
# ================================================================

# class CollectorOpenRequest(BaseModel):
#     start_url: str = "https://www.jd.com"


# @router.post("/collector/open")
# async def collector_open(payload: CollectorOpenRequest) -> ApiEnvelope:
#     """启动可见浏览器窗口，用户可手动登录电商平台。"""
#     trace_id = make_id("trc")
#     try:
#         from app.services.collector import get_or_create_collector
#         collector = await get_or_create_collector()
#         await collector.open_browser(start_url=payload.start_url)
#         return _envelope(trace_id=trace_id, data=collector.get_status())
#     except Exception as e:
#         logger.exception("打开采集浏览器失败")
#         return _envelope(trace_id=trace_id, data={}, error=str(e)[:200])

# @router.get("/collector/status")
# def collector_status() -> ApiEnvelope:
#     trace_id = make_id("trc")
#     from app.services.collector import get_collector_status
#     return _envelope(trace_id=trace_id, data=get_collector_status())

# @router.post("/collector/close")
# async def collector_close() -> ApiEnvelope:
#     trace_id = make_id("trc")
#     from app.services.collector import close_collector
#     await close_collector()
#     return _envelope(trace_id=trace_id, data={"closed": True})

# @router.get("/collector/products")
# async def collector_products() -> ApiEnvelope:
#     trace_id = make_id("trc")
#     from app.services.collector import get_or_create_collector
#     try:
#         collector = await get_or_create_collector()
#         return _envelope(trace_id=trace_id, data={"products": collector.products, "count": len(collector.products)})
#     except Exception as e:
#         return _envelope(trace_id=trace_id, data={"products": [], "count": 0}, error=str(e)[:200])

# @router.get("/collector/events")
# async def collector_events():
#     from app.services.collector import get_or_create_collector
#     collector = await get_or_create_collector()
#     async def event_generator():
#         try:
#             while collector.status not in ("closed", "idle"):
#                 try:
#                     event = await asyncio.wait_for(collector.event_queue.get(), timeout=30.0)
#                     yield f"event: collector\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
#                 except asyncio.TimeoutError:
#                     yield f"event: heartbeat\ndata: {json.dumps({'status': collector.status})}\n\n"
#         except asyncio.CancelledError:
#             pass
#     return StreamingResponse(event_generator(), media_type="text/event-stream",
#         headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


# @router.get("/collector/logs")
# def collector_logs(limit: int = Query(default=200, ge=1, le=1000)) -> ApiEnvelope:
#     trace_id = make_id("trc")
#     from app.services.collector.log_store import get_logs
#     logs = get_logs(limit=limit)
#     return _envelope(trace_id=trace_id, data={"logs": logs, "count": len(logs)})

# @router.delete("/collector/logs")
# def collector_logs_clear() -> ApiEnvelope:
#     trace_id = make_id("trc")
#     from app.services.collector.log_store import clear_logs
#     count = clear_logs()
#     return _envelope(trace_id=trace_id, data={"deleted": count})
