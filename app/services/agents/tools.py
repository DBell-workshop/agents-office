"""Agent 工具定义 — 各类 Agent 可用的 Function Calling 工具 Schema。"""
from __future__ import annotations

from typing import Any, Dict, List


# ============================================================
# 商品搜索工具（导购员、理货员共享）
# ============================================================
PRODUCT_TOOLS: List[Dict[str, Any]] = [
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
# 数据工程师专属工具
# ============================================================
DATA_ENGINEER_TOOLS: List[Dict[str, Any]] = [
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
# 数据分析师专属工具
# ============================================================
DATA_ANALYST_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "query_office_costs",
            "description": "查询 AgentsOffice 的 LLM 调用成本数据。可按 Agent、按模型、或查看总览",
            "parameters": {
                "type": "object",
                "properties": {
                    "view": {
                        "type": "string",
                        "enum": ["by_agent", "by_model", "summary"],
                        "description": "查看维度：by_agent=按Agent汇总，by_model=按模型汇总，summary=今日/本周/本月总览",
                    },
                    "start": {
                        "type": "string",
                        "description": "起始时间（ISO格式，如 2025-01-01），可选",
                    },
                    "end": {
                        "type": "string",
                        "description": "结束时间（ISO格式），可选",
                    },
                },
                "required": ["view"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_agent_stats",
            "description": "查询各 Agent 的工作状态统计：总调用次数、总 token 用量、平均响应时间等",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "搜索商品数据库用于数据分析，支持关键词、品类、品牌、价格范围",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词"},
                    "category": {
                        "type": "string",
                        "enum": ["电视", "冰箱", "厨房电器", "空调", "洗衣机", "扫地机器人", "热水器"],
                        "description": "商品品类",
                    },
                    "brand": {"type": "string", "description": "品牌名称"},
                    "min_price": {"type": "number", "description": "最低价格 (USD)"},
                    "max_price": {"type": "number", "description": "最高价格 (USD)"},
                    "limit": {"type": "integer", "description": "返回数量上限，默认 10"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_category_stats",
            "description": "获取各品类的商品数量和价格范围统计",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "执行自定义 SQL 查询进行深度数据分析。可查询商品表、用户表等。禁止操作系统表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "要执行的 SQL 语句"},
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_user_tables",
            "description": "列出所有可查询的用户数据表",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_data",
            "description": "查询用户表中的数据，支持 WHERE 条件",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "表名"},
                    "limit": {"type": "integer", "description": "返回行数上限，默认 50"},
                    "where": {"type": "string", "description": "WHERE 条件"},
                },
                "required": ["table_name"],
            },
        },
    },
]


# ============================================================
# 平面设计师专属工具
# ============================================================
DESIGNER_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "调用 AI 图像生成模型生成图片。需提供详细的英文描述。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "图片描述（英文，尽量详细描述构图、风格、色调、元素）",
                    },
                    "size": {
                        "type": "string",
                        "enum": ["1024x1024", "1792x1024", "1024x1792"],
                        "description": "图片尺寸：1024x1024（方图）、1792x1024（横幅）、1024x1792（海报）",
                    },
                    "style": {
                        "type": "string",
                        "enum": ["vivid", "natural"],
                        "description": "风格：vivid=鲜艳夸张，natural=自然写实",
                    },
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "搜索商品信息（用于商品海报、宣传素材等设计场景）",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词"},
                    "category": {
                        "type": "string",
                        "enum": ["电视", "冰箱", "厨房电器", "空调", "洗衣机", "扫地机器人", "热水器"],
                    },
                    "brand": {"type": "string"},
                    "limit": {"type": "integer", "description": "返回数量上限"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_detail",
            "description": "获取单个商品详情（用于商品详情海报等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "商品 ID"},
                },
                "required": ["product_id"],
            },
        },
    },
]


# ============================================================
# 数据产品经理（大屏）专属工具
# ============================================================
DASHBOARD_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_dashboard_templates",
            "description": "列出所有可用的电商大屏模板（如 618、双十一、日常运营）。用户说想做大屏时，先调用此工具展示可选模板。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_dashboard",
            "description": "基于模板创建一个新的数据大屏。创建后返回大屏ID和访问链接。",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_key": {
                        "type": "string",
                        "enum": ["618", "double11", "daily"],
                        "description": "模板类型：618=年中大促，double11=双十一，daily=日常运营",
                    },
                    "name": {
                        "type": "string",
                        "description": "自定义大屏名称（可选，不填则使用模板默认名称）",
                    },
                },
                "required": ["template_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dashboards",
            "description": "列出用户已创建的所有数据大屏",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dashboard_detail",
            "description": "获取指定大屏的完整配置信息，包括图表列表和数据源",
            "parameters": {
                "type": "object",
                "properties": {
                    "dashboard_id": {
                        "type": "string",
                        "description": "大屏 ID",
                    },
                },
                "required": ["dashboard_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_chart_to_dashboard",
            "description": "向已有大屏添加一个自定义图表。支持 line/bar/pie/gauge/funnel/radar 类型。",
            "parameters": {
                "type": "object",
                "properties": {
                    "dashboard_id": {
                        "type": "string",
                        "description": "目标大屏 ID",
                    },
                    "chart_type": {
                        "type": "string",
                        "enum": ["line", "bar", "pie", "gauge", "funnel", "radar"],
                        "description": "图表类型",
                    },
                    "title": {
                        "type": "string",
                        "description": "图表标题",
                    },
                    "sql": {
                        "type": "string",
                        "description": "数据查询 SQL",
                    },
                    "refresh_interval": {
                        "type": "integer",
                        "description": "刷新间隔（秒），默认300",
                    },
                },
                "required": ["dashboard_id", "chart_type", "title", "sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refresh_dashboard",
            "description": "刷新大屏数据 — 执行各图表的查询获取最新数据",
            "parameters": {
                "type": "object",
                "properties": {
                    "dashboard_id": {
                        "type": "string",
                        "description": "要刷新的大屏 ID",
                    },
                },
                "required": ["dashboard_id"],
            },
        },
    },
    # 数据产品经理也需要查询数据来设计指标
    {
        "type": "function",
        "function": {
            "name": "list_user_tables",
            "description": "列出所有可用的数据表，了解有哪些数据可以用于大屏展示",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "执行 SQL 查询，用于验证数据是否可用、预览数据样例",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "要执行的 SQL 语句"},
                },
                "required": ["sql"],
            },
        },
    },
]


TOOLS_MAP: Dict[str, Dict[str, Any]] = {
    "PRODUCT_TOOLS": {
        "key": "PRODUCT_TOOLS",
        "name": "商品搜索",
        "description": "搜索和对比商品数据库",
        "icon": "🛒",
        "tools": PRODUCT_TOOLS,
    },
    "DATA_ENGINEER_TOOLS": {
        "key": "DATA_ENGINEER_TOOLS",
        "name": "数据工程",
        "description": "连接数据源、建表、清洗数据、执行SQL",
        "icon": "🔧",
        "tools": DATA_ENGINEER_TOOLS,
    },
    "DATA_ANALYST_TOOLS": {
        "key": "DATA_ANALYST_TOOLS",
        "name": "数据分析",
        "description": "成本查询、Agent统计、数据分析",
        "icon": "📊",
        "tools": DATA_ANALYST_TOOLS,
    },
    "DASHBOARD_TOOLS": {
        "key": "DASHBOARD_TOOLS",
        "name": "数据大屏",
        "description": "创建和管理可视化数据大屏",
        "icon": "📺",
        "tools": DASHBOARD_TOOLS,
    },
    "DESIGNER_TOOLS": {
        "key": "DESIGNER_TOOLS",
        "name": "图片生成",
        "description": "AI 生成营销图片和设计素材",
        "icon": "🎨",
        "tools": DESIGNER_TOOLS,
    },
}


def get_skill_packs_catalog() -> List[Dict[str, Any]]:
    """返回所有可用的技能包列表（不含工具 schema，仅摘要）。"""
    return [
        {"key": v["key"], "name": v["name"], "description": v["description"], "icon": v["icon"], "tool_count": len(v["tools"])}
        for v in TOOLS_MAP.values()
    ]


def get_tools_by_key(tools_key) -> List[Dict[str, Any]]:
    """根据 tools_key 返回工具列表。支持单个字符串或多个 key 的列表。"""
    if isinstance(tools_key, list):
        return get_tools_by_keys(tools_key)
    entry = TOOLS_MAP.get(tools_key)
    if entry:
        return entry["tools"]
    return TOOLS_MAP["PRODUCT_TOOLS"]["tools"]


def get_tools_by_keys(keys: List[str]) -> List[Dict[str, Any]]:
    """合并多个技能包的工具列表，自动去重（按 function.name）。"""
    seen_names: set = set()
    merged: List[Dict[str, Any]] = []
    for key in keys:
        entry = TOOLS_MAP.get(key)
        if not entry:
            continue
        for tool in entry["tools"]:
            name = tool.get("function", {}).get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                merged.append(tool)
    return merged if merged else TOOLS_MAP["PRODUCT_TOOLS"]["tools"]
