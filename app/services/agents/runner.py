"""Agent 运行器 — 执行单个 Agent 的 LLM 调用循环。"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.services.llm_service import async_chat_completion
from app.services.agents.tools import get_tools_by_key
from app.services.agents.tool_executors import execute_tool

log = logging.getLogger(__name__)

_PROCESS_MESSAGES = {
    "DATA_ENGINEER_TOOLS": "正在处理数据…",
    "DATA_ANALYST_TOOLS": "正在分析数据…",
    "DESIGNER_TOOLS": "正在设计中…",
    "DASHBOARD_TOOLS": "正在配置数据大屏…",
}


def _get_process_message(agent_name: str, tools_key) -> str:
    """根据 tools_key（字符串或列表）生成 process 消息。"""
    if isinstance(tools_key, list):
        # 多技能包：取第一个有匹配的
        for k in tools_key:
            if k in _PROCESS_MESSAGES:
                return f"{agent_name}{_PROCESS_MESSAGES[k]}"
        return f"{agent_name}正在工作中…"
    return f"{agent_name}{_PROCESS_MESSAGES.get(tools_key, '前往数据仓库查询商品信息…')}"


def record_cost(
    agent_slug: str,
    trace_id: str,
    model_name: str,
    usage: Dict[str, int],
    duration_ms: Optional[int] = None,
) -> None:
    """将 LLM 调用的 token 用量持久化到数据库（静默失败，不阻塞主流程）。"""
    try:
        from app.office.store import office_store
        if office_store is None:
            return
        office_store.record_cost(
            agent_slug=agent_slug,
            trace_id=trace_id,
            model_name=model_name,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            duration_ms=duration_ms,
        )
    except Exception as e:
        log.warning("成本记录写入失败: %s", e)


async def run_agent(
    agent_slug: str,
    agent_defn: Dict[str, Any],
    user_message: str,
    task_summary: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    model: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """执行单个 Agent 的 LLM 调用（异步）。支持 Function Calling 和协作可视化。"""
    agent_name = agent_defn.get("display_name", agent_slug)
    agent_id = agent_defn.get("phaser_agent_id", "")
    home_room = agent_defn.get("room_id", "workspace")
    system_prompt = agent_defn.get("system_prompt", "你是一个 AI 助手。")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"[调度员分配的任务] {task_summary}\n\n[用户原始消息] {user_message}"},
    ]
    if conversation_history:
        recent = conversation_history[-6:]
        messages = [messages[0]] + recent + [messages[-1]]

    # 根据 Agent 类型选择工具集
    tools_key = agent_defn.get("tools", "")
    tools = get_tools_by_key(tools_key)

    # 工具执行循环（最多 3 轮，防止无限调用）
    final_content = ""
    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    process_messages: List[Dict[str, Any]] = []
    used_tools = False
    total_found = 0

    from app.models import make_id

    trace_id = make_id("trc")
    agent_result: Dict[str, Any] = {}

    for _round in range(4):
        t0 = time.monotonic()
        agent_result = await async_chat_completion(
            messages=messages,
            model=model,
            temperature=0.7,
            tools=tools,
            api_base=api_base,
            api_key=api_key,
        )
        round_ms = int((time.monotonic() - t0) * 1000)

        for k in total_usage:
            total_usage[k] += agent_result["usage"].get(k, 0)

        record_cost(
            agent_slug=agent_slug,
            trace_id=trace_id,
            model_name=agent_result.get("model", model or "unknown"),
            usage=agent_result["usage"],
            duration_ms=round_ms,
        )

        tool_calls = agent_result.get("tool_calls")

        if not tool_calls:
            final_content = agent_result["content"]
            break

        if not used_tools:
            used_tools = True
            process_msg = _get_process_message(agent_name, tools_key)
            process_messages.append({
                "role": "process",
                "agent_slug": agent_slug,
                "agent_name": agent_name,
                "content": process_msg,
                "message_type": "process",
                "movement": {"agent_id": agent_id, "room_id": "datacenter"},
            })

        messages.append({
            "role": "assistant",
            "content": agent_result["content"] or "",
            "tool_calls": tool_calls,
        })

        for tc in tool_calls:
            func = tc.get("function", {})
            func_name = func.get("name", "")
            func_args = json.loads(func.get("arguments", "{}"))
            tool_call_id = tc.get("id", "")

            tool_result = execute_tool(tools_key, func_name, func_args)
            if isinstance(tool_result, list):
                total_found += len(tool_result)
            elif isinstance(tool_result, dict) and tool_result.get("rows"):
                total_found += len(tool_result["rows"])

            log.info("%s调用工具: %s(%s)", agent_name, func_name, json.dumps(func_args, ensure_ascii=False)[:100])

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(tool_result, ensure_ascii=False),
            })
    else:
        final_content = agent_result.get("content", "抱歉，查询过程出现问题。")

    if used_tools and total_found > 0:
        process_messages.append({
            "role": "process",
            "agent_slug": agent_slug,
            "agent_name": agent_name,
            "content": f"数据库查询完毕，共找到 {total_found} 条相关商品",
            "message_type": "process",
            "movement": None,
        })

    result_messages = list(process_messages)
    result_messages.append({
        "role": "agent",
        "agent_slug": agent_slug,
        "agent_name": agent_name,
        "content": final_content,
        "usage": total_usage,
        "message_type": "response",
        "movement": {"agent_id": agent_id, "room_id": home_room} if used_tools else None,
    })

    return {"messages": result_messages}


async def run_agent_stream(
    agent_slug: str,
    agent_defn: Dict[str, Any],
    user_message: str,
    task_summary: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    model: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """SSE 版 Agent 执行：yield 事件 dict，每个阶段实时推送。"""
    agent_name = agent_defn.get("display_name", agent_slug)
    agent_id = agent_defn.get("phaser_agent_id", "")
    home_room = agent_defn.get("room_id", "workspace")
    system_prompt = agent_defn.get("system_prompt", "你是一个 AI 助手。")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"[调度员分配的任务] {task_summary}\n\n[用户原始消息] {user_message}"},
    ]
    if conversation_history:
        recent = conversation_history[-6:]
        messages = [messages[0]] + recent + [messages[-1]]

    tools_key = agent_defn.get("tools", "")
    tools = get_tools_by_key(tools_key)

    total_usage: Dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    used_tools = False
    total_found = 0

    from app.models import make_id

    trace_id = make_id("trc")
    agent_result: Dict[str, Any] = {}

    for _round in range(4):
        t0 = time.monotonic()
        agent_result = await async_chat_completion(
            messages=messages,
            model=model,
            temperature=0.7,
            tools=tools,
            api_base=api_base,
            api_key=api_key,
        )
        round_ms = int((time.monotonic() - t0) * 1000)

        for k in total_usage:
            total_usage[k] += agent_result["usage"].get(k, 0)

        record_cost(
            agent_slug=agent_slug,
            trace_id=trace_id,
            model_name=agent_result.get("model", model or "unknown"),
            usage=agent_result["usage"],
            duration_ms=round_ms,
        )

        tool_calls = agent_result.get("tool_calls")

        if not tool_calls:
            break

        # 首次使用工具 → 推送 process 事件
        if not used_tools:
            used_tools = True
            process_msg = _get_process_message(agent_name, tools_key)
            yield {
                "event": "process",
                "data": {
                    "role": "process",
                    "agent_slug": agent_slug,
                    "agent_name": agent_name,
                    "content": process_msg,
                    "message_type": "process",
                    "movement": {"agent_id": agent_id, "room_id": "datacenter"},
                },
            }

        messages.append({
            "role": "assistant",
            "content": agent_result["content"] or "",
            "tool_calls": tool_calls,
        })

        for tc in tool_calls:
            func = tc.get("function", {})
            func_name = func.get("name", "")
            func_args = json.loads(func.get("arguments", "{}"))
            tool_call_id = tc.get("id", "")

            tool_result = execute_tool(tools_key, func_name, func_args)
            if isinstance(tool_result, list):
                total_found += len(tool_result)
            elif isinstance(tool_result, dict) and tool_result.get("rows"):
                total_found += len(tool_result["rows"])

            log.info("%s调用工具: %s(%s)", agent_name, func_name, json.dumps(func_args, ensure_ascii=False)[:100])

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(tool_result, ensure_ascii=False),
            })
    else:
        agent_result = {"content": agent_result.get("content", "抱歉，查询过程出现问题。")}

    final_content = agent_result.get("content", "")

    if used_tools and total_found > 0:
        yield {
            "event": "process",
            "data": {
                "role": "process",
                "agent_slug": agent_slug,
                "agent_name": agent_name,
                "content": f"数据库查询完毕，共找到 {total_found} 条相关商品",
                "message_type": "process",
                "movement": None,
            },
        }

    yield {
        "event": "message",
        "data": {
            "role": "agent",
            "agent_slug": agent_slug,
            "agent_name": agent_name,
            "content": final_content,
            "usage": total_usage,
            "message_type": "response",
            "movement": {"agent_id": agent_id, "room_id": home_room} if used_tools else None,
        },
    }
