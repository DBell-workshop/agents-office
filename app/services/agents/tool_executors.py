"""Agent 工具执行器 — 各类工具的运行时实现。"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.services.product_search import (
    compare_products,
    get_category_stats,
    get_product_detail,
    search_products,
)
from app.services.data_engineer import (
    clean_data,
    create_table_from_file,
    execute_sql,
    list_uploaded_files,
    list_user_tables,
    parse_file,
    query_data,
    test_db_connection,
)

log = logging.getLogger(__name__)


def execute_product_tool(func_name: str, args: Dict[str, Any]) -> Any:
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


def execute_data_tool(func_name: str, args: Dict[str, Any]) -> Any:
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


def execute_analyst_tool(func_name: str, args: Dict[str, Any]) -> Any:
    """执行数据分析师工具。"""
    try:
        if func_name == "query_office_costs":
            from datetime import datetime
            from app.office.store import office_store
            if office_store is None:
                return {"error": "数据库未初始化"}
            view = args.get("view", "summary")
            start_str = args.get("start")
            end_str = args.get("end")
            start = datetime.fromisoformat(start_str) if start_str else None
            end = datetime.fromisoformat(end_str) if end_str else None
            if view == "by_agent":
                return office_store.costs_by_agent(start=start, end=end)
            elif view == "by_model":
                return office_store.costs_by_model(start=start, end=end)
            else:
                return office_store.cost_summary()
        elif func_name == "query_agent_stats":
            from app.office.store import office_store
            if office_store is None:
                return {"error": "数据库未初始化"}
            return office_store.costs_by_agent()
        elif func_name == "search_products":
            return search_products(
                keyword=args.get("keyword"),
                category=args.get("category"),
                brand=args.get("brand"),
                min_price=args.get("min_price"),
                max_price=args.get("max_price"),
                limit=args.get("limit", 10),
            )
        elif func_name == "get_category_stats":
            return get_category_stats()
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
        else:
            return {"error": f"未知工具: {func_name}"}
    except Exception as e:
        log.error("分析工具执行失败: %s — %s", func_name, e)
        return {"error": str(e)}


def execute_designer_tool(func_name: str, args: Dict[str, Any]) -> Any:
    """执行平面设计师工具。"""
    try:
        if func_name == "generate_image":
            return generate_image(
                prompt=args["prompt"],
                size=args.get("size", "1024x1024"),
                style=args.get("style", "vivid"),
            )
        elif func_name == "search_products":
            return search_products(
                keyword=args.get("keyword"),
                category=args.get("category"),
                brand=args.get("brand"),
                limit=args.get("limit", 5),
            )
        elif func_name == "get_product_detail":
            result = get_product_detail(args["product_id"])
            return result or {"error": "商品不存在"}
        else:
            return {"error": f"未知工具: {func_name}"}
    except Exception as e:
        log.error("设计工具执行失败: %s — %s", func_name, e)
        return {"error": str(e)}


def generate_image(prompt: str, size: str = "1024x1024", style: str = "vivid") -> Dict[str, Any]:
    """调用 OpenAI DALL-E 生成图片。"""
    try:
        import openai
        from app.config import settings

        if not settings.openai_api_key:
            return {
                "error": "OpenAI API Key 未配置，无法生成图片。请在 .env 中设置 OPENAI_API_KEY。",
                "fallback": "design_description",
                "prompt_used": prompt,
            }

        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            style=style,
            n=1,
        )
        image_url = response.data[0].url
        revised_prompt = response.data[0].revised_prompt

        return {
            "image_url": image_url,
            "revised_prompt": revised_prompt,
            "size": size,
            "style": style,
        }
    except Exception as e:
        return {
            "error": f"图片生成失败: {str(e)}",
            "fallback": "design_description",
            "prompt_used": prompt,
        }


def execute_dashboard_tool(func_name: str, args: Dict[str, Any]) -> Any:
    """执行数据产品经理（大屏）工具。"""
    try:
        from app.services.dashboard import (
            list_templates,
            create_dashboard_from_template,
            list_dashboards,
            get_dashboard,
            update_dashboard,
            refresh_dashboard_data,
            generate_custom_chart,
        )

        if func_name == "list_dashboard_templates":
            return list_templates()
        elif func_name == "create_dashboard":
            result = create_dashboard_from_template(
                template_key=args["template_key"],
                name=args.get("name"),
            )
            if "error" not in result:
                result["access_url"] = f"/dashboard/{result['dashboard_id']}"
                result["message"] = f"大屏「{result['name']}」创建成功！"
            return result
        elif func_name == "list_dashboards":
            dashboards = list_dashboards()
            return {
                "count": len(dashboards),
                "dashboards": [
                    {
                        "dashboard_id": d["dashboard_id"],
                        "name": d["name"],
                        "template_key": d.get("template_key"),
                        "status": d["status"],
                        "access_url": f"/dashboard/{d['dashboard_id']}",
                        "created_at": d.get("created_at"),
                    }
                    for d in dashboards
                ],
            }
        elif func_name == "get_dashboard_detail":
            result = get_dashboard(args["dashboard_id"])
            if result is None:
                return {"error": f"大屏 {args['dashboard_id']} 不存在"}
            return result
        elif func_name == "add_chart_to_dashboard":
            dashboard = get_dashboard(args["dashboard_id"])
            if dashboard is None:
                return {"error": f"大屏 {args['dashboard_id']} 不存在"}
            new_chart = generate_custom_chart(
                chart_type=args["chart_type"],
                title=args["title"],
                sql=args["sql"],
                refresh_interval=args.get("refresh_interval", 300),
            )
            charts = dashboard.get("charts", [])
            charts.append(new_chart)
            updated = update_dashboard(args["dashboard_id"], {"charts": charts})
            if updated:
                return {"message": f"图表「{args['title']}」已添加到大屏", "chart": new_chart}
            return {"error": "更新大屏失败"}
        elif func_name == "refresh_dashboard":
            return refresh_dashboard_data(args["dashboard_id"])
        elif func_name == "list_user_tables":
            return list_user_tables()
        elif func_name == "execute_sql":
            return execute_sql(args["sql"])
        else:
            return {"error": f"未知工具: {func_name}"}
    except Exception as e:
        log.error("大屏工具执行失败: %s — %s", func_name, e)
        return {"error": str(e)}


# 工具名 → 执行器 的映射（用于多技能包合并时按 func_name 路由）
_TOOL_NAME_TO_EXECUTOR = {
    # PRODUCT_TOOLS
    "search_products": execute_product_tool,
    "get_product_detail": execute_product_tool,
    "get_category_stats": execute_product_tool,
    "compare_products": execute_product_tool,
    # DATA_ENGINEER_TOOLS
    "analyze_uploaded_file": execute_data_tool,
    "create_table_from_file": execute_data_tool,
    "clean_data": execute_data_tool,
    "test_db_connection": execute_data_tool,
    # DATA_ANALYST_TOOLS
    "query_office_costs": execute_analyst_tool,
    "query_agent_stats": execute_analyst_tool,
    # DASHBOARD_TOOLS
    "list_dashboard_templates": execute_dashboard_tool,
    "create_dashboard": execute_dashboard_tool,
    "list_dashboards": execute_dashboard_tool,
    "get_dashboard_detail": execute_dashboard_tool,
    "add_chart_to_dashboard": execute_dashboard_tool,
    "refresh_dashboard": execute_dashboard_tool,
    # DESIGNER_TOOLS
    "generate_image": execute_designer_tool,
    # 共享工具 — 多个执行器都能处理，优先用 data_tool
    "execute_sql": execute_data_tool,
    "list_user_tables": execute_data_tool,
    "query_data": execute_data_tool,
    "list_uploaded_files": execute_data_tool,
}


def execute_tool(tools_key, func_name: str, args: Dict[str, Any]) -> Any:
    """根据 tools_key 路由到对应的工具执行器。支持单个字符串或多个 key 的列表。"""
    # 多技能包模式：按 func_name 查找执行器
    if isinstance(tools_key, list):
        executor = _TOOL_NAME_TO_EXECUTOR.get(func_name)
        if executor:
            return executor(func_name, args)
        log.warning("多技能包模式下未找到工具 %s 的执行器", func_name)
        return {"error": f"未知工具: {func_name}"}

    # 单技能包模式：原有逻辑
    if tools_key == "DATA_ENGINEER_TOOLS":
        return execute_data_tool(func_name, args)
    elif tools_key == "DATA_ANALYST_TOOLS":
        return execute_analyst_tool(func_name, args)
    elif tools_key == "DESIGNER_TOOLS":
        return execute_designer_tool(func_name, args)
    elif tools_key == "DASHBOARD_TOOLS":
        return execute_dashboard_tool(func_name, args)
    else:
        return execute_product_tool(func_name, args)
