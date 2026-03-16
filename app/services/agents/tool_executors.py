"""Agent 工具执行器 — 各类工具的运行时实现。"""
from __future__ import annotations

import logging
from typing import Any, Dict

try:
    from app.services.product_search import (
        compare_products,
        get_category_stats,
        get_product_detail,
        search_products,
    )
except ImportError:
    compare_products = get_category_stats = get_product_detail = search_products = None

try:
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
except ImportError:
    clean_data = create_table_from_file = execute_sql = None
    list_uploaded_files = list_user_tables = parse_file = query_data = test_db_connection = None

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


def execute_tool(tools_key: str, func_name: str, args: Dict[str, Any]) -> Any:
    """根据 tools_key 路由到对应的工具执行器。"""
    if tools_key == "DATA_ENGINEER_TOOLS":
        return execute_data_tool(func_name, args)
    elif tools_key == "DATA_ANALYST_TOOLS":
        return execute_analyst_tool(func_name, args)
    elif tools_key == "DESIGNER_TOOLS":
        return execute_designer_tool(func_name, args)
    else:
        return execute_product_tool(func_name, args)
