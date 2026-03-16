"""agents 包 — 拆分自原 dispatcher.py 的 Agent 系统。

公开 API：
- dispatch()            — 调度入口
- run_agent()           — 单 Agent 执行
- load_agent_registry() — 加载合并后的注册表
- get_full_registry()   — 含 dispatcher 的完整注册表
- BUILTIN_AGENTS        — 内置 Agent 定义
"""
from app.services.agents.definitions import BUILTIN_AGENTS, DISPATCHER_DEFINITION
from app.services.agents.dispatcher import dispatch, dispatch_stream
from app.services.agents.registry import (
    build_dispatcher_prompt,
    build_dispatcher_tools,
    get_full_registry,
    load_agent_registry,
)
from app.services.agents.runner import record_cost, run_agent, run_agent_stream
from app.services.agents.tools import (
    DATA_ANALYST_TOOLS,
    DATA_ENGINEER_TOOLS,
    get_tools_by_key,
)
PRODUCT_TOOLS = []   # placeholder for generic version
DESIGNER_TOOLS = []  # placeholder for generic version
from app.services.agents.tool_executors import execute_tool

__all__ = [
    "BUILTIN_AGENTS",
    "DISPATCHER_DEFINITION",
    "DATA_ANALYST_TOOLS",
    "DATA_ENGINEER_TOOLS",
    "DESIGNER_TOOLS",
    "PRODUCT_TOOLS",
    "build_dispatcher_prompt",
    "build_dispatcher_tools",
    "dispatch",
    "dispatch_stream",
    "execute_tool",
    "get_full_registry",
    "get_tools_by_key",
    "load_agent_registry",
    "record_cost",
    "run_agent",
    "run_agent_stream",
]
