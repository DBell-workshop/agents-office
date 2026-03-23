"""Agent 注册表 — 从 DB 加载自定义配置，与内置默认合并。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.agents.definitions import BUILTIN_AGENTS, DISPATCHER_DEFINITION

log = logging.getLogger(__name__)


def load_agent_registry() -> Dict[str, Dict[str, Any]]:
    """从 DB 加载活跃 Agent 定义，与内置默认合并。

    优先级：DB 自定义 > 内置默认。
    DB 中 active=True 的 agent 会覆盖内置默认。
    DB 中新增的 agent（不在内置列表中）也会被加入。
    """
    # 以内置默认为基础
    registry: Dict[str, Dict[str, Any]] = {}
    for slug, defn in BUILTIN_AGENTS.items():
        registry[slug] = {**defn, "slug": slug}

    # 从 DB 加载自定义配置
    try:
        from app.office.store import office_store
        if office_store is not None:
            db_agents = office_store.get_active_agent_definitions()
            for agent in db_agents:
                slug = agent["slug"]
                if slug == "dispatcher":
                    continue  # 调度员不作为可分配目标

                if slug in registry:
                    # DB 配置覆盖内置默认（仅覆盖非空字段）
                    for field in ("system_prompt", "display_name", "role", "color",
                                  "room_id", "phaser_agent_id", "model_name"):
                        if agent.get(field):
                            registry[slug][field] = agent[field]
                    # 技能包：skill_packs 覆盖旧 tools 字段
                    if agent.get("skill_packs"):
                        registry[slug]["tools"] = agent["skill_packs"]
                    elif agent.get("tools"):
                        registry[slug]["tools"] = agent["tools"]
                else:
                    # 用户自定义的全新 Agent
                    if not agent.get("system_prompt"):
                        continue  # 没有提示词的 agent 无法工作
                    # 技能包：优先 skill_packs，回退 tools
                    tools_val = agent.get("skill_packs") or agent.get("tools", "")
                    registry[slug] = {
                        "slug": slug,
                        "display_name": agent.get("display_name", slug),
                        "role": agent.get("role", ""),
                        "system_prompt": agent["system_prompt"],
                        "color": agent.get("color", "#cccccc"),
                        "room_id": agent.get("room_id", "workspace"),
                        "phaser_agent_id": agent.get("phaser_agent_id", ""),
                        "model_name": agent.get("model_name", ""),
                        "tools": tools_val,
                    }
    except Exception as e:
        log.warning("从 DB 加载 Agent 定义失败，使用内置默认: %s", e)

    return registry


def get_full_registry() -> Dict[str, Dict[str, Any]]:
    """返回完整注册表（含 dispatcher + 所有活跃自定义 Agent），供前端 API 使用。

    与 load_agent_registry() 不同，此函数包含所有活跃 Agent（即使没有 system_prompt），
    因为前端需要在状态栏和地图上显示它们。
    """
    registry = load_agent_registry()

    # 补充：加载所有活跃的自定义 Agent（包括尚未设置 system_prompt 的）
    try:
        from app.office.store import office_store
        if office_store is not None:
            db_agents = office_store.get_active_agent_definitions()
            for agent in db_agents:
                slug = agent["slug"]
                if slug == "dispatcher" or slug in registry:
                    continue
                registry[slug] = {
                    "slug": slug,
                    "display_name": agent.get("display_name", slug),
                    "role": agent.get("role", ""),
                    "system_prompt": agent.get("system_prompt", ""),
                    "color": agent.get("color", "#cccccc"),
                    "room_id": agent.get("room_id", "workspace"),
                    "phaser_agent_id": agent.get("phaser_agent_id", ""),
                    "model_name": agent.get("model_name", ""),
                }
    except Exception:
        pass

    # 加入调度员
    full = {"dispatcher": {**DISPATCHER_DEFINITION, "slug": "dispatcher"}}
    full.update(registry)
    return full


def build_dispatcher_prompt(registry: Dict[str, Dict[str, Any]]) -> str:
    """根据当前活跃 Agent 注册表动态构建调度员系统提示词。"""
    agent_descriptions = []
    for i, (slug, defn) in enumerate(registry.items(), 1):
        name = defn.get("display_name", slug)
        role = defn.get("role", "")
        agent_descriptions.append(
            f"{i}. **{name} ({slug})** — {role}"
        )

    agents_section = "\n".join(agent_descriptions)

    # 动态加载可用 Skill 列表
    skills_section = ""
    try:
        from app.services.skills.registry import list_skills as list_registered_skills
        skills = list_registered_skills()
        if skills:
            skill_lines = []
            for s in skills:
                agents_str = "、".join(s.get("agent_slugs", []))
                skill_lines.append(
                    f"- **{s['display_name']}** (`{s['name']}`) — {s['description']}（关联 Agent: {agents_str}）"
                )
            skills_section = "\n## 可用 Skill（高级能力）\n\n" + "\n".join(skill_lines) + "\n"
    except Exception:
        pass

    return f"""你是 AgentsOffice 的调度员（Dispatcher），负责理解用户需求并分配给合适的 Agent。

## 可用 Agent

{agents_section}
{skills_section}
## 你的工作规则

- 分析用户的意图，决定交给谁处理
- 根据每个 Agent 的职责描述选择最合适的 Agent
- 当用户需求明确匹配某个 Skill 的能力时（如比价、跨平台对比），优先调用 trigger_skill
- 如果需要多个 Agent 协作 → 说明协作方式
- 如果用户在闲聊/打招呼 → 你直接回复，不需要分配

## 输出格式

- 需要触发 Skill → 调用 trigger_skill
- 需要分配给 Agent → 调用 assign_task
- 闲聊 → 直接回复文字"""


def build_dispatcher_tools(registry: Dict[str, Dict[str, Any]]) -> List[Dict]:
    """根据当前活跃 Agent 注册表动态构建调度员工具定义。"""
    agent_slugs = list(registry.keys())

    tools: List[Dict] = [
        {
            "type": "function",
            "function": {
                "name": "assign_task",
                "description": "将用户任务分配给指定 Agent 执行",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_slug": {
                            "type": "string",
                            "enum": agent_slugs,
                            "description": "目标 Agent 标识",
                        },
                        "task_summary": {
                            "type": "string",
                            "description": "简要说明分配给 Agent 的任务内容",
                        },
                        "needs_collaboration": {
                            "type": "boolean",
                            "description": "是否需要多 Agent 协作",
                        },
                    },
                    "required": ["agent_slug", "task_summary"],
                },
            },
        },
    ]

    # 动态添加 Skill 触发工具
    try:
        from app.services.skills.registry import list_skills as list_registered_skills
        skills = list_registered_skills()
        if skills:
            skill_names = [s["name"] for s in skills]
            tools.append({
                "type": "function",
                "function": {
                    "name": "trigger_skill",
                    "description": (
                        "当用户需求明确匹配某个 Skill 的高级能力时调用（如跨平台比价、"
                        "商品对比等）。Skill 是多步骤交互流程，会引导用户完成操作。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_name": {
                                "type": "string",
                                "enum": skill_names,
                                "description": "要触发的 Skill 标识",
                            },
                            "query": {
                                "type": "string",
                                "description": "从用户消息中提取的核心搜索关键词（去除意图词，保留商品名/品类）",
                            },
                        },
                        "required": ["skill_name", "query"],
                    },
                },
            })
    except Exception:
        pass

    return tools
