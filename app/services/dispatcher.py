"""调度员 Agent — 理解用户意图，路由到合适的 Agent 执行。

调度员是系统大脑：
1. 接收用户消息
2. 从 DB 加载活跃 Agent 定义（支持用户自定义）
3. 用 LLM (Function Calling) 分析意图
4. 决定由哪些 Agent 处理
5. 协调 Agent 间协作
6. 汇总结果返回用户
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from app.services.llm_service import chat_completion
from app.services.product_search import search_products, get_product_detail, get_category_stats, compare_products
from app.services.data_engineer import (
    clean_data,
    test_db_connection,
    parse_file,
    create_table_from_file,
    execute_sql,
    list_user_tables,
    query_data,
    list_uploaded_files,
)

log = logging.getLogger(__name__)


def _record_cost(
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


# ============================================================
# 内置默认 Agent 定义（DB 无数据时的 fallback）
# ============================================================
BUILTIN_AGENTS: Dict[str, Dict[str, Any]] = {
    "shopping_guide": {
        "display_name": "导购员",
        "role": "面向用户的推荐顾问，擅长理解需求、推荐商品、对比分析",
        "color": "#4ade80",
        "room_id": "showroom",
        "phaser_agent_id": "agt_guide",
        "system_prompt": """你是 AgentsOffice 的导购员（Shopping Guide），面向用户的推荐顾问。

## 你的职责
- 理解用户的主观描述，猜测用户的真实需求
- 用户描述不清时主动追问（预算、品牌偏好、使用场景等）
- 根据用户关注点推荐合适的商品
- 语气亲切专业，像一个真实的导购员

## 搜索策略（必须遵守）
1. **先分析需求维度**：拿到用户需求后，先在脑中明确：品类、预算范围、品牌偏好、使用场景
2. **搜索时使用精确参数**：优先传 category、brand、min_price、max_price，而不是只传 keyword；keyword 用于补充细化（如功能特性）
3. **候选商品对比**：搜出多个候选后，用 compare_products 对 2-4 个候选商品做横向对比，再做最终推荐
4. **推荐必须给出对比分析**：说明为什么推荐这个，它相比其他候选的优势在哪里

## 可用工具
- search_products：搜索商品（支持 keyword、category、brand、min_price、max_price、limit）
- get_product_detail：获取单个商品详情
- get_category_stats：查看各品类统计
- compare_products：对多个商品做横向对比（传入 product_ids 列表）
- 品类包括：电视、冰箱、厨房电器、空调、洗衣机、扫地机器人、热水器
- **必须先搜索商品数据，再基于真实数据给出推荐，不要编造商品信息**

## 回复风格
- 简洁但有温度
- 用列表形式呈现推荐，包含商品名称、品牌、价格
- 价格单位为美元 (USD)
- 推荐时说明对比分析结论，让用户知道"为什么选这个"
- 主动引导用户提供更多信息以精准推荐""",
    },
    "data_engineer": {
        "display_name": "数据工程师",
        "role": "帮助用户管理数据：上传文件、创建数据库表、查询数据、执行SQL",
        "color": "#a78bfa",
        "room_id": "datacenter",
        "phaser_agent_id": "agt_data_eng",
        "tools": "DATA_ENGINEER_TOOLS",
        "system_prompt": """你是 AgentsOffice 的数据工程师（Data Engineer），帮助不懂代码的用户轻松管理数据。

## 核心原则：先理解 → 再确认 → 最后执行
**绝对不要收到文件就直接建表导入。** 你必须和用户完成以下三个阶段的对话后才能执行操作。

---

## 阶段①：数据理解（收到文件或被告知有文件时）

1. 用 list_uploaded_files 查看有哪些文件
2. 用 analyze_uploaded_file 分析目标文件
3. **向用户展示你的理解**（必须包含以下内容）：
   - 文件基本信息：行数、列数
   - 每一列你认为代表什么含义（用通俗语言解释）
   - 数据质量发现：空值数量、重复值、格式不一致的地方
   - 几行样本数据预览
4. **问用户**：「我的理解对吗？有需要纠正的地方吗？」
5. 等用户确认或纠正后才进入下一阶段

## 阶段②：清洗方案（用户确认数据理解后）

1. 根据发现的数据质量问题，**提出清洗建议**：
   - 空值怎么处理（填充默认值 / 删除该行 / 保留）
   - 格式不统一的列如何标准化（如"红色/红/Red"统一为哪个）
   - 是否需要去重
   - 列名是否需要重命名（更易读）
   - 数据类型是否需要调整
2. **问用户**：「这个清洗方案你觉得可以吗？有要调整的地方吗？」
3. 如果数据本身很干净没什么要清洗的，可以告诉用户「数据质量很好，不需要额外清洗」然后直接进入阶段③
4. 用户确认后，用 clean_data 执行清洗，报告清洗结果

## 阶段③：存储确认（清洗完成或不需要清洗时）

1. **提出存储方案**：
   - 建议的表名
   - 每列的最终名称和数据类型
   - 建议的主键和索引（如果适用）
2. **问用户**：「按这个方案存储可以吗？」
3. 用户确认后，用 create_table_from_file 建表导入
4. 导入完成后报告结果：表名、行数、列数

---

## 外部数据库连接

如果用户想连接自己的数据库：
1. 引导用户提供：数据库类型、主机地址、端口、数据库名、用户名、密码
2. 用 test_db_connection 测试连接
3. 连接成功后报告数据库中有哪些表
4. 用户可以选择查询外部数据库的数据

---

## 可用工具
- list_uploaded_files：列出所有已上传的文件
- analyze_uploaded_file：分析文件结构（列名、类型、预览、质量报告）
- clean_data：按规则清洗数据（处理空值、统一格式、去重、重命名列等）
- create_table_from_file：建表并导入数据（必须在用户确认后才能调用！）
- execute_sql：执行 SQL（SELECT / CREATE TABLE / ALTER 等）
- list_user_tables：列出用户已创建的所有表
- query_data：查询用户表的数据
- test_db_connection：测试外部数据库连接

## 回复风格
- 用简单的中文，不使用技术术语
- 用表格展示数据预览和方案
- 每个阶段结束时明确询问用户确认
- 出错时用通俗语言解释原因和解决办法""",
    },
    "product_specialist": {
        "display_name": "理货员",
        "role": "商品数据专家，擅长查库存、查价格、查规格、数据统计",
        "color": "#60a5fa",
        "room_id": "datacenter",
        "phaser_agent_id": "agt_inventory",
        "system_prompt": """你是 AgentsOffice 的理货员（Product Specialist），商品数据专家。

## 你的职责
- 使用搜索工具查询真实商品数据库（Best Buy 数据集，约 3800 条家电商品）
- 整理和汇总商品信息（型号、价格、品牌、规格参数）
- 回答关于商品属性的专业问题

## 可用数据
- 品类：电视(864)、冰箱(1070)、厨房电器(1553)、空调(184)、洗衣机(62)、扫地机器人(47)、热水器(12)
- 字段：商品名、品牌、价格(USD)、描述、型号
- 数据来源：Best Buy 开放数据集

## 工作方式
- 收到查询请求后，优先组合多个参数搜索（category + brand + min_price/max_price），不要只传 keyword
- 有多个候选商品时，可以调用 compare_products 做横向对比后再整理输出
- 根据工具返回的数据整理回复，不要编造数据
- 如果搜索无结果，说明情况并建议调整关键词

## 可用工具
- search_products：支持 keyword、category、brand、min_price、max_price、limit 多参数组合搜索
- get_product_detail：根据 product_id 获取详情
- get_category_stats：各品类统计
- compare_products：批量查询并对比多个商品（传入 product_ids 列表）

## 回复风格
- 数据准确、结构清晰
- 用列表呈现商品信息，包含名称、品牌、价格
- 价格单位为美元 (USD)""",
    },
}


# ============================================================
# 商品搜索工具定义（所有 Agent 共享）
# ============================================================
PRODUCT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "搜索商品数据库，支持关键词、品类、品牌、价格范围",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（商品名称或描述中的词）",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["电视", "冰箱", "厨房电器", "空调", "洗衣机", "扫地机器人", "热水器"],
                        "description": "商品品类",
                    },
                    "brand": {
                        "type": "string",
                        "description": "品牌名称（如 Samsung, LG, Sony）",
                    },
                    "min_price": {
                        "type": "number",
                        "description": "最低价格 (USD)",
                    },
                    "max_price": {
                        "type": "number",
                        "description": "最高价格 (USD)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量上限，默认 10",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_detail",
            "description": "根据 product_id 获取商品详细信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "商品 ID（如 bb_1052096）",
                    },
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_category_stats",
            "description": "获取各品类的商品数量和价格范围统计",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_products",
            "description": "批量查询多个商品的详情并返回结构化对比结果，适合在搜索出候选商品后做横向对比",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要对比的商品 ID 列表（如 ['bb_1052096', 'bb_2034567']），建议 2-4 个",
                    },
                },
                "required": ["product_ids"],
            },
        },
    },
]


# ============================================================
# 数据工程师专属工具定义
# ============================================================
DATA_ENGINEER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "analyze_uploaded_file",
            "description": "分析已上传的文件（CSV/Excel），返回列名、数据类型、预览数据。用于了解文件结构后决定如何建表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径（从 list_uploaded_files 获取）",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_table_from_file",
            "description": "根据已上传的文件自动创建数据库表并导入全部数据。会自动推断列类型。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径",
                    },
                    "table_name": {
                        "type": "string",
                        "description": "自定义表名（可选，不填则根据文件名自动生成）",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "执行 SQL 语句。支持 SELECT 查询、CREATE TABLE、ALTER TABLE、INSERT、UPDATE 等操作。禁止操作系统表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "要执行的 SQL 语句",
                    },
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_user_tables",
            "description": "列出用户创建的所有数据表，显示表名、行数和列信息",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_data",
            "description": "查询用户表中的数据，支持 WHERE 条件筛选",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "表名（必须是 ud_ 前缀的用户表）",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回行数上限，默认 50",
                    },
                    "where": {
                        "type": "string",
                        "description": "WHERE 条件（如 price > 100）",
                    },
                },
                "required": ["table_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_uploaded_files",
            "description": "列出所有已上传的文件，显示文件名、大小和路径",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clean_data",
            "description": "按规则清洗数据文件。支持：填充空值、删除空值行、去重、列重命名、值统一。清洗后保存为新文件。必须在用户确认清洗方案后才能调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "要清洗的文件路径",
                    },
                    "rules": {
                        "type": "object",
                        "description": "清洗规则",
                        "properties": {
                            "fill_na": {
                                "type": "object",
                                "description": "填充空值：{列名: 填充值}，如 {\"price\": 0, \"color\": \"未知\"}",
                            },
                            "drop_na_columns": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "这些列有空值则删除整行",
                            },
                            "drop_duplicates": {
                                "type": "boolean",
                                "description": "是否去除重复行",
                            },
                            "rename_columns": {
                                "type": "object",
                                "description": "列重命名：{旧列名: 新列名}",
                            },
                            "unify_values": {
                                "type": "object",
                                "description": "值统一：{列名: {旧值: 新值}}，如 {\"color\": {\"Red\": \"红色\", \"红\": \"红色\"}}",
                            },
                        },
                    },
                },
                "required": ["file_path", "rules"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "test_db_connection",
            "description": "测试外部数据库连接。成功则返回数据库中的表列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "db_type": {
                        "type": "string",
                        "enum": ["postgresql", "mysql", "sqlite"],
                        "description": "数据库类型",
                    },
                    "host": {
                        "type": "string",
                        "description": "主机地址（如 localhost, 192.168.1.100）",
                    },
                    "port": {
                        "type": "integer",
                        "description": "端口号（PostgreSQL 默认 5432，MySQL 默认 3306）",
                    },
                    "database": {
                        "type": "string",
                        "description": "数据库名称",
                    },
                    "username": {
                        "type": "string",
                        "description": "用户名",
                    },
                    "password": {
                        "type": "string",
                        "description": "密码",
                    },
                },
                "required": ["db_type", "host", "port", "database", "username", "password"],
            },
        },
    },
]


# ============================================================
# 动态 Agent 注册表（每次 dispatch 时从 DB 加载）
# ============================================================
def _load_agent_registry() -> Dict[str, Dict[str, Any]]:
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
                    if agent.get("system_prompt"):
                        registry[slug]["system_prompt"] = agent["system_prompt"]
                    if agent.get("display_name"):
                        registry[slug]["display_name"] = agent["display_name"]
                    if agent.get("role"):
                        registry[slug]["role"] = agent["role"]
                    if agent.get("color"):
                        registry[slug]["color"] = agent["color"]
                    if agent.get("room_id"):
                        registry[slug]["room_id"] = agent["room_id"]
                    if agent.get("phaser_agent_id"):
                        registry[slug]["phaser_agent_id"] = agent["phaser_agent_id"]
                    if agent.get("model_name"):
                        registry[slug]["model_name"] = agent["model_name"]
                else:
                    # 用户自定义的全新 Agent
                    if not agent.get("system_prompt"):
                        continue  # 没有提示词的 agent 无法工作
                    registry[slug] = {
                        "slug": slug,
                        "display_name": agent.get("display_name", slug),
                        "role": agent.get("role", ""),
                        "system_prompt": agent["system_prompt"],
                        "color": agent.get("color", "#cccccc"),
                        "room_id": agent.get("room_id", "workspace"),
                        "phaser_agent_id": agent.get("phaser_agent_id", ""),
                        "model_name": agent.get("model_name", ""),
                    }
    except Exception as e:
        log.warning("从 DB 加载 Agent 定义失败，使用内置默认: %s", e)

    return registry


def _build_dispatcher_prompt(registry: Dict[str, Dict[str, Any]]) -> str:
    """根据当前活跃 Agent 注册表动态构建调度员系统提示词。"""
    agent_descriptions = []
    for i, (slug, defn) in enumerate(registry.items(), 1):
        name = defn.get("display_name", slug)
        role = defn.get("role", "")
        agent_descriptions.append(
            f"{i}. **{name} ({slug})** — {role}"
        )

    agents_section = "\n".join(agent_descriptions)

    return f"""你是 AgentsOffice 的调度员（Dispatcher），负责理解用户需求并分配给合适的 Agent。

## 可用 Agent

{agents_section}

## 你的工作规则

- 分析用户的意图，决定交给谁处理
- 根据每个 Agent 的职责描述选择最合适的 Agent
- 如果需要多个 Agent 协作 → 说明协作方式
- 如果用户在闲聊/打招呼 → 你直接回复，不需要分配

## 输出格式

调用 assign_task 函数来分配任务。如果是闲聊，直接回复文字即可。"""


def _build_dispatcher_tools(registry: Dict[str, Dict[str, Any]]) -> List[Dict]:
    """根据当前活跃 Agent 注册表动态构建调度员工具定义。"""
    agent_slugs = list(registry.keys())
    return [
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
        }
    ]


# ============================================================
# 调度流程
# ============================================================
def dispatch(
    user_message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    dispatcher_model: Optional[str] = None,
    agent_model: Optional[str] = None,
    agent_models: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """执行完整的调度流程：用户消息 → 调度员路由 → Agent 执行。"""
    from app.models import make_id

    trace_id = make_id("trc")
    result_messages: List[Dict[str, Any]] = []

    # 动态加载 Agent 注册表
    registry = _load_agent_registry()

    # 构建调度员消息（动态生成）
    dispatcher_prompt = _build_dispatcher_prompt(registry)
    dispatcher_tools = _build_dispatcher_tools(registry)

    messages = [{"role": "system", "content": dispatcher_prompt}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    # 调用调度员 LLM
    t0 = time.monotonic()
    dispatcher_result = chat_completion(
        messages=messages,
        model=dispatcher_model,
        temperature=0.3,
        tools=dispatcher_tools,
    )
    dispatcher_ms = int((time.monotonic() - t0) * 1000)

    _record_cost(
        agent_slug="dispatcher",
        trace_id=trace_id,
        model_name=dispatcher_result.get("model", dispatcher_model or "unknown"),
        usage=dispatcher_result["usage"],
        duration_ms=dispatcher_ms,
    )

    # 处理调度员响应
    tool_calls = dispatcher_result.get("tool_calls")

    if tool_calls:
        for tc in tool_calls:
            func = tc.get("function", {})
            func_name = func.get("name", "")

            if func_name == "assign_task":
                args = json.loads(func.get("arguments", "{}"))
                agent_slug = args.get("agent_slug", "shopping_guide")
                task_summary = args.get("task_summary", user_message)

                # 从注册表获取 Agent 信息
                agent_defn = registry.get(agent_slug, {})
                target_name = agent_defn.get("display_name", agent_slug)

                result_messages.append({
                    "role": "dispatcher",
                    "agent_slug": "dispatcher",
                    "agent_name": "调度员",
                    "content": f"收到，这个需求交给{target_name}处理。",
                    "usage": dispatcher_result["usage"],
                    "message_type": "routing",
                    "movement": {"agent_id": "agt_dispatcher", "room_id": "manager"},
                })

                # 确定目标模型：per-agent 配置 > 全局 agent_model
                target_model = None
                if agent_models:
                    target_model = agent_models.get(agent_slug)
                target_model = target_model or agent_defn.get("model_name") or agent_model

                agent_response = _run_agent(
                    agent_slug=agent_slug,
                    agent_defn=agent_defn,
                    user_message=user_message,
                    task_summary=task_summary,
                    conversation_history=conversation_history,
                    model=target_model,
                )
                result_messages.extend(agent_response["messages"])
    else:
        result_messages.append({
            "role": "dispatcher",
            "agent_slug": "dispatcher",
            "agent_name": "调度员",
            "content": dispatcher_result["content"],
            "usage": dispatcher_result["usage"],
            "message_type": "response",
            "movement": None,
        })

    agent_movements = [
        msg["movement"] for msg in result_messages
        if msg.get("movement")
    ]

    return {
        "messages": result_messages,
        "agent_movements": agent_movements,
    }


def _run_agent(
    agent_slug: str,
    agent_defn: Dict[str, Any],
    user_message: str,
    task_summary: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """执行单个 Agent 的 LLM 调用。支持 Function Calling 和协作可视化。"""
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
    if tools_key == "DATA_ENGINEER_TOOLS":
        tools = DATA_ENGINEER_TOOLS
    else:
        tools = PRODUCT_TOOLS

    # 工具执行循环（最多 3 轮，防止无限调用）
    final_content = ""
    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    process_messages: List[Dict[str, Any]] = []
    used_tools = False
    total_found = 0

    from app.models import make_id

    trace_id = make_id("trc")

    for _round in range(4):
        t0 = time.monotonic()
        agent_result = chat_completion(
            messages=messages,
            model=model,
            temperature=0.7,
            tools=tools,
        )
        round_ms = int((time.monotonic() - t0) * 1000)

        for k in total_usage:
            total_usage[k] += agent_result["usage"].get(k, 0)

        _record_cost(
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
            if tools_key == "DATA_ENGINEER_TOOLS":
                process_msg = f"{agent_name}正在处理数据…"
            else:
                process_msg = f"{agent_name}前往数据仓库查询商品信息…"
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

            if tools_key == "DATA_ENGINEER_TOOLS":
                tool_result = _execute_data_tool(func_name, func_args)
            else:
                tool_result = _execute_product_tool(func_name, func_args)
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


def _execute_data_tool(func_name: str, args: Dict[str, Any]) -> Any:
    """执行数据工程师工具。"""
    try:
        if func_name == "analyze_uploaded_file":
            return parse_file(args["file_path"])
        elif func_name == "create_table_from_file":
            return create_table_from_file(
                file_path=args["file_path"],
                table_name=args.get("table_name"),
                column_mapping=args.get("column_mapping"),
            )
        elif func_name == "execute_sql":
            return execute_sql(args["sql"])
        elif func_name == "list_user_tables":
            return list_user_tables()
        elif func_name == "query_data":
            return query_data(
                table_name=args["table_name"],
                limit=args.get("limit", 50),
                where=args.get("where"),
            )
        elif func_name == "list_uploaded_files":
            return list_uploaded_files()
        elif func_name == "clean_data":
            return clean_data(
                file_path=args["file_path"],
                rules=args.get("rules", {}),
            )
        elif func_name == "test_db_connection":
            return test_db_connection(
                db_type=args["db_type"],
                host=args["host"],
                port=args["port"],
                database=args["database"],
                username=args["username"],
                password=args["password"],
            )
        else:
            return {"error": f"未知工具: {func_name}"}
    except Exception as e:
        log.error("数据工具执行失败: %s — %s", func_name, e)
        return {"error": str(e)}


def _execute_product_tool(func_name: str, args: Dict[str, Any]) -> Any:
    """执行商品搜索工具。"""
    try:
        if func_name == "search_products":
            return search_products(
                keyword=args.get("keyword"),
                category=args.get("category"),
                brand=args.get("brand"),
                min_price=args.get("min_price"),
                max_price=args.get("max_price"),
                limit=args.get("limit", 10),
            )
        elif func_name == "get_product_detail":
            result = get_product_detail(args["product_id"])
            return result or {"error": "商品不存在"}
        elif func_name == "get_category_stats":
            return get_category_stats()
        elif func_name == "compare_products":
            product_ids = args.get("product_ids", [])
            return compare_products(product_ids)
        else:
            return {"error": f"未知工具: {func_name}"}
    except Exception as e:
        log.error("工具执行失败: %s — %s", func_name, e)
        return {"error": str(e)}
