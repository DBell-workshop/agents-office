"""数据大屏服务 — 模板管理、ECharts 配置生成、数据刷新。"""
from __future__ import annotations

import copy
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models import make_id

log = logging.getLogger(__name__)


# ============================================================
# 电商大屏模板库
# ============================================================

DASHBOARD_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "618": {
        "name": "618年中大促作战大屏",
        "description": "618大促核心指标实时监控：GMV、订单量、转化率、流量、渠道分布",
        "layout": {
            "columns": 3,
            "rows": 3,
            "theme": "dark",
            "title": "618 年中大促 · 实时作战大屏",
        },
        "charts": [
            {
                "id": "gmv_realtime",
                "title": "实时 GMV（万元）",
                "position": {"col": 0, "row": 0, "colSpan": 2, "rowSpan": 1},
                "chart_type": "line",
                "echarts_option": {
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "category", "data": ["00:00", "02:00", "04:00", "06:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]},
                    "yAxis": {"type": "value", "name": "GMV（万元）"},
                    "series": [
                        {"name": "今日", "type": "line", "smooth": True, "data": [], "itemStyle": {"color": "#00d4ff"}},
                        {"name": "昨日", "type": "line", "smooth": True, "data": [], "lineStyle": {"type": "dashed"}, "itemStyle": {"color": "#666"}},
                    ],
                },
                "data_query": {
                    "sql": "SELECT date_trunc('hour', created_at) AS hour, SUM(amount)/10000 AS gmv FROM orders WHERE created_at >= CURRENT_DATE GROUP BY hour ORDER BY hour",
                    "refresh_interval": 60,
                },
            },
            {
                "id": "gmv_total",
                "title": "GMV 目标达成",
                "position": {"col": 2, "row": 0, "colSpan": 1, "rowSpan": 1},
                "chart_type": "gauge",
                "echarts_option": {
                    "series": [{
                        "type": "gauge",
                        "startAngle": 200,
                        "endAngle": -20,
                        "min": 0,
                        "max": 100,
                        "detail": {"formatter": "{value}%", "fontSize": 24, "color": "#00d4ff"},
                        "data": [{"value": 0, "name": "达成率"}],
                        "axisLine": {"lineStyle": {"width": 20, "color": [[0.3, "#fd666d"], [0.7, "#37a2da"], [1, "#67e0e3"]]}},
                    }],
                },
                "data_query": {
                    "sql": "SELECT ROUND(SUM(amount) / 1000000 * 100, 1) AS rate FROM orders WHERE created_at >= CURRENT_DATE",
                    "refresh_interval": 60,
                },
            },
            {
                "id": "order_count",
                "title": "订单量趋势",
                "position": {"col": 0, "row": 1, "colSpan": 1, "rowSpan": 1},
                "chart_type": "bar",
                "echarts_option": {
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "category", "data": []},
                    "yAxis": {"type": "value", "name": "订单数"},
                    "series": [{"name": "订单量", "type": "bar", "data": [], "itemStyle": {"color": "#37a2da"}}],
                },
                "data_query": {
                    "sql": "SELECT date_trunc('hour', created_at) AS hour, COUNT(*) AS cnt FROM orders WHERE created_at >= CURRENT_DATE GROUP BY hour ORDER BY hour",
                    "refresh_interval": 120,
                },
            },
            {
                "id": "conversion_funnel",
                "title": "转化漏斗",
                "position": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1},
                "chart_type": "funnel",
                "echarts_option": {
                    "tooltip": {"trigger": "item", "formatter": "{b}: {c}"},
                    "series": [{
                        "type": "funnel",
                        "left": "10%",
                        "width": "80%",
                        "label": {"show": True, "position": "inside"},
                        "data": [
                            {"value": 0, "name": "浏览"},
                            {"value": 0, "name": "加购"},
                            {"value": 0, "name": "下单"},
                            {"value": 0, "name": "支付"},
                        ],
                    }],
                },
                "data_query": {
                    "sql": "SELECT 'manual' AS source",
                    "refresh_interval": 300,
                },
            },
            {
                "id": "channel_pie",
                "title": "渠道订单占比",
                "position": {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1},
                "chart_type": "pie",
                "echarts_option": {
                    "tooltip": {"trigger": "item"},
                    "series": [{
                        "type": "pie",
                        "radius": ["40%", "70%"],
                        "label": {"show": True, "formatter": "{b}\n{d}%"},
                        "data": [],
                    }],
                },
                "data_query": {
                    "sql": "SELECT channel, COUNT(*) AS cnt FROM orders WHERE created_at >= CURRENT_DATE GROUP BY channel",
                    "refresh_interval": 300,
                },
            },
            {
                "id": "kpi_cards",
                "title": "核心指标卡片",
                "position": {"col": 0, "row": 2, "colSpan": 3, "rowSpan": 1},
                "chart_type": "kpi_cards",
                "kpi_items": [
                    {"label": "总 GMV", "unit": "万元", "sql": "SELECT SUM(amount)/10000 FROM orders WHERE created_at >= CURRENT_DATE", "format": ",.1f"},
                    {"label": "订单数", "unit": "单", "sql": "SELECT COUNT(*) FROM orders WHERE created_at >= CURRENT_DATE", "format": ",d"},
                    {"label": "客单价", "unit": "元", "sql": "SELECT AVG(amount) FROM orders WHERE created_at >= CURRENT_DATE", "format": ",.0f"},
                    {"label": "支付转化率", "unit": "%", "sql": "SELECT ROUND(COUNT(CASE WHEN status='paid' THEN 1 END)::numeric/NULLIF(COUNT(*),0)*100, 1) FROM orders WHERE created_at >= CURRENT_DATE", "format": ".1f"},
                    {"label": "退货率", "unit": "%", "sql": "SELECT ROUND(COUNT(CASE WHEN status='returned' THEN 1 END)::numeric/NULLIF(COUNT(*),0)*100, 1) FROM orders WHERE created_at >= CURRENT_DATE", "format": ".1f"},
                    {"label": "UV", "unit": "人", "sql": "SELECT COUNT(DISTINCT user_id) FROM page_views WHERE created_at >= CURRENT_DATE", "format": ",d"},
                ],
                "data_query": {"refresh_interval": 60},
            },
        ],
        "refresh_config": {
            "mode": "realtime",
            "default_interval": 60,
            "description": "实时模式：核心指标每60秒刷新，漏斗每5分钟刷新",
        },
    },
    "double11": {
        "name": "双十一狂欢大屏",
        "description": "双十一全链路监控：预售/正式/返场三阶段对比，GMV冲刺目标",
        "layout": {
            "columns": 4,
            "rows": 3,
            "theme": "dark",
            "title": "双十一狂欢节 · 实时作战大屏",
        },
        "charts": [
            {
                "id": "gmv_race",
                "title": "GMV 冲刺（亿元）",
                "position": {"col": 0, "row": 0, "colSpan": 3, "rowSpan": 1},
                "chart_type": "line",
                "echarts_option": {
                    "tooltip": {"trigger": "axis"},
                    "legend": {"data": ["预售期", "正式期", "返场期"], "textStyle": {"color": "#ccc"}},
                    "xAxis": {"type": "category", "data": []},
                    "yAxis": {"type": "value", "name": "GMV（亿元）"},
                    "series": [
                        {"name": "预售期", "type": "line", "smooth": True, "data": [], "areaStyle": {"opacity": 0.2}, "itemStyle": {"color": "#ffd666"}},
                        {"name": "正式期", "type": "line", "smooth": True, "data": [], "areaStyle": {"opacity": 0.2}, "itemStyle": {"color": "#ff4d4f"}},
                        {"name": "返场期", "type": "line", "smooth": True, "data": [], "areaStyle": {"opacity": 0.2}, "itemStyle": {"color": "#36cfc9"}},
                    ],
                },
                "data_query": {
                    "sql": "SELECT phase, date_trunc('hour', created_at) AS hour, SUM(amount)/100000000 AS gmv FROM orders WHERE event='double11' GROUP BY phase, hour ORDER BY hour",
                    "refresh_interval": 60,
                },
            },
            {
                "id": "gmv_target_gauge",
                "title": "目标达成",
                "position": {"col": 3, "row": 0, "colSpan": 1, "rowSpan": 1},
                "chart_type": "gauge",
                "echarts_option": {
                    "series": [{
                        "type": "gauge",
                        "startAngle": 200,
                        "endAngle": -20,
                        "min": 0,
                        "max": 100,
                        "detail": {"formatter": "{value}%", "fontSize": 28, "color": "#ff4d4f"},
                        "data": [{"value": 0, "name": "目标达成率"}],
                        "axisLine": {"lineStyle": {"width": 20, "color": [[0.3, "#fd666d"], [0.7, "#ffd666"], [1, "#67e0e3"]]}},
                    }],
                },
                "data_query": {"sql": "SELECT 0 AS rate", "refresh_interval": 60},
            },
            {
                "id": "category_rank",
                "title": "品类销售排行",
                "position": {"col": 0, "row": 1, "colSpan": 2, "rowSpan": 1},
                "chart_type": "bar",
                "echarts_option": {
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "value"},
                    "yAxis": {"type": "category", "data": []},
                    "series": [{"type": "bar", "data": [], "itemStyle": {"color": "#ff4d4f"}}],
                },
                "data_query": {
                    "sql": "SELECT category, SUM(amount) AS total FROM orders WHERE event='double11' GROUP BY category ORDER BY total DESC LIMIT 10",
                    "refresh_interval": 120,
                },
            },
            {
                "id": "realtime_orders",
                "title": "实时订单流水",
                "position": {"col": 2, "row": 1, "colSpan": 2, "rowSpan": 1},
                "chart_type": "line",
                "echarts_option": {
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "category", "data": []},
                    "yAxis": {"type": "value", "name": "订单/分钟"},
                    "series": [{"name": "订单量", "type": "line", "smooth": True, "data": [], "areaStyle": {"opacity": 0.3}, "itemStyle": {"color": "#36cfc9"}}],
                },
                "data_query": {
                    "sql": "SELECT date_trunc('minute', created_at) AS minute, COUNT(*) FROM orders WHERE created_at >= NOW() - INTERVAL '1 hour' GROUP BY minute ORDER BY minute",
                    "refresh_interval": 30,
                },
            },
            {
                "id": "kpi_cards_11",
                "title": "核心指标",
                "position": {"col": 0, "row": 2, "colSpan": 4, "rowSpan": 1},
                "chart_type": "kpi_cards",
                "kpi_items": [
                    {"label": "总 GMV", "unit": "亿元", "sql": "SELECT SUM(amount)/100000000 FROM orders WHERE event='double11'", "format": ",.2f"},
                    {"label": "总订单", "unit": "万单", "sql": "SELECT COUNT(*)/10000 FROM orders WHERE event='double11'", "format": ",.1f"},
                    {"label": "客单价", "unit": "元", "sql": "SELECT AVG(amount) FROM orders WHERE event='double11'", "format": ",.0f"},
                    {"label": "支付转化", "unit": "%", "sql": "SELECT 0", "format": ".1f"},
                    {"label": "UV", "unit": "万人", "sql": "SELECT 0", "format": ",.1f"},
                    {"label": "人均消费", "unit": "元", "sql": "SELECT 0", "format": ",.0f"},
                ],
                "data_query": {"refresh_interval": 60},
            },
        ],
        "refresh_config": {
            "mode": "realtime",
            "default_interval": 60,
            "description": "实时模式：GMV和订单每60秒刷新，排行每2分钟刷新",
        },
    },
    "daily": {
        "name": "日常运营监控大屏",
        "description": "电商日常运营核心指标：销售趋势、库存预警、退货率、渠道分析",
        "layout": {
            "columns": 3,
            "rows": 3,
            "theme": "dark",
            "title": "电商运营 · 每日数据看板",
        },
        "charts": [
            {
                "id": "sales_7d",
                "title": "近7日销售趋势",
                "position": {"col": 0, "row": 0, "colSpan": 2, "rowSpan": 1},
                "chart_type": "line",
                "echarts_option": {
                    "tooltip": {"trigger": "axis"},
                    "legend": {"data": ["GMV", "订单量"]},
                    "xAxis": {"type": "category", "data": []},
                    "yAxis": [
                        {"type": "value", "name": "GMV（万元）"},
                        {"type": "value", "name": "订单数"},
                    ],
                    "series": [
                        {"name": "GMV", "type": "line", "smooth": True, "data": [], "itemStyle": {"color": "#5470c6"}},
                        {"name": "订单量", "type": "bar", "yAxisIndex": 1, "data": [], "itemStyle": {"color": "#91cc75"}},
                    ],
                },
                "data_query": {
                    "sql": "SELECT DATE(created_at) AS day, SUM(amount)/10000 AS gmv, COUNT(*) AS orders FROM orders WHERE created_at >= CURRENT_DATE - 7 GROUP BY day ORDER BY day",
                    "refresh_interval": 3600,
                },
            },
            {
                "id": "return_rate",
                "title": "退货率趋势",
                "position": {"col": 2, "row": 0, "colSpan": 1, "rowSpan": 1},
                "chart_type": "line",
                "echarts_option": {
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "category", "data": []},
                    "yAxis": {"type": "value", "name": "%", "max": 20},
                    "series": [{"name": "退货率", "type": "line", "smooth": True, "data": [], "markLine": {"data": [{"yAxis": 5, "name": "预警线"}]}, "itemStyle": {"color": "#ee6666"}}],
                },
                "data_query": {
                    "sql": "SELECT DATE(created_at) AS day, ROUND(COUNT(CASE WHEN status='returned' THEN 1 END)::numeric/NULLIF(COUNT(*),0)*100, 1) FROM orders WHERE created_at >= CURRENT_DATE - 7 GROUP BY day ORDER BY day",
                    "refresh_interval": 3600,
                },
            },
            {
                "id": "category_sales",
                "title": "品类销售分布",
                "position": {"col": 0, "row": 1, "colSpan": 1, "rowSpan": 1},
                "chart_type": "pie",
                "echarts_option": {
                    "tooltip": {"trigger": "item"},
                    "series": [{
                        "type": "pie",
                        "radius": ["40%", "70%"],
                        "label": {"show": True, "formatter": "{b}\n{d}%"},
                        "data": [],
                    }],
                },
                "data_query": {
                    "sql": "SELECT category AS name, SUM(amount) AS value FROM orders WHERE created_at >= CURRENT_DATE - 7 GROUP BY category ORDER BY value DESC",
                    "refresh_interval": 3600,
                },
            },
            {
                "id": "channel_compare",
                "title": "渠道对比",
                "position": {"col": 1, "row": 1, "colSpan": 1, "rowSpan": 1},
                "chart_type": "radar",
                "echarts_option": {
                    "tooltip": {},
                    "radar": {"indicator": [
                        {"name": "GMV", "max": 100},
                        {"name": "订单量", "max": 100},
                        {"name": "转化率", "max": 100},
                        {"name": "客单价", "max": 100},
                        {"name": "复购率", "max": 100},
                    ]},
                    "series": [{"type": "radar", "data": []}],
                },
                "data_query": {
                    "sql": "SELECT 'manual' AS source",
                    "refresh_interval": 3600,
                },
            },
            {
                "id": "top_products",
                "title": "热销商品 TOP10",
                "position": {"col": 2, "row": 1, "colSpan": 1, "rowSpan": 1},
                "chart_type": "bar",
                "echarts_option": {
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "value"},
                    "yAxis": {"type": "category", "data": []},
                    "series": [{"type": "bar", "data": [], "itemStyle": {"color": "#5470c6"}}],
                },
                "data_query": {
                    "sql": "SELECT product_name, SUM(amount) AS total FROM order_items WHERE created_at >= CURRENT_DATE - 7 GROUP BY product_name ORDER BY total DESC LIMIT 10",
                    "refresh_interval": 3600,
                },
            },
            {
                "id": "kpi_daily",
                "title": "今日指标",
                "position": {"col": 0, "row": 2, "colSpan": 3, "rowSpan": 1},
                "chart_type": "kpi_cards",
                "kpi_items": [
                    {"label": "今日 GMV", "unit": "万元", "sql": "SELECT SUM(amount)/10000 FROM orders WHERE created_at >= CURRENT_DATE", "format": ",.1f"},
                    {"label": "今日订单", "unit": "单", "sql": "SELECT COUNT(*) FROM orders WHERE created_at >= CURRENT_DATE", "format": ",d"},
                    {"label": "客单价", "unit": "元", "sql": "SELECT AVG(amount) FROM orders WHERE created_at >= CURRENT_DATE", "format": ",.0f"},
                    {"label": "UV", "unit": "人", "sql": "SELECT 0", "format": ",d"},
                    {"label": "退货率", "unit": "%", "sql": "SELECT 0", "format": ".1f"},
                ],
                "data_query": {"refresh_interval": 3600},
            },
        ],
        "refresh_config": {
            "mode": "t_plus_1",
            "default_interval": 3600,
            "description": "T+1模式：每小时刷新一次，适合日常运营监控",
        },
    },
}


# ============================================================
# Dashboard CRUD 操作
# ============================================================

def list_templates() -> List[Dict[str, Any]]:
    """返回所有可用的大屏模板摘要。"""
    result = []
    for key, tpl in DASHBOARD_TEMPLATES.items():
        result.append({
            "template_key": key,
            "name": tpl["name"],
            "description": tpl["description"],
            "chart_count": len(tpl["charts"]),
            "refresh_mode": tpl["refresh_config"]["mode"],
        })
    return result


def get_template(template_key: str) -> Optional[Dict[str, Any]]:
    """获取指定模板的完整配置。"""
    tpl = DASHBOARD_TEMPLATES.get(template_key)
    if tpl is None:
        return None
    return {"template_key": template_key, **copy.deepcopy(tpl)}


ASPECT_RATIO_LAYOUTS = {
    "16:9": {"columns": 3, "rows": 3},
    "21:9": {"columns": 5, "rows": 2},
    "9:16": {"columns": 1, "rows": 6},
    "4:3": {"columns": 2, "rows": 3},
}


def create_dashboard_from_template(
    template_key: str,
    name: Optional[str] = None,
    data_source_config: Optional[Dict[str, Any]] = None,
    aspect_ratio: Optional[str] = None,
) -> Dict[str, Any]:
    """基于模板创建一个新大屏实例，存入数据库。"""
    tpl = DASHBOARD_TEMPLATES.get(template_key)
    if tpl is None:
        return {"error": f"模板 '{template_key}' 不存在。可用模板：{list(DASHBOARD_TEMPLATES.keys())}"}

    dashboard_id = make_id("dash")
    slug = f"dashboard-{template_key}-{dashboard_id[-6:]}"
    dashboard_name = name or tpl["name"]

    layout = copy.deepcopy(tpl["layout"])
    if aspect_ratio and aspect_ratio in ASPECT_RATIO_LAYOUTS:
        ratio_layout = ASPECT_RATIO_LAYOUTS[aspect_ratio]
        layout["columns"] = ratio_layout["columns"]
        layout["rows"] = ratio_layout["rows"]
        layout["aspect_ratio"] = aspect_ratio

    dashboard = {
        "dashboard_id": dashboard_id,
        "name": dashboard_name,
        "slug": slug,
        "description": tpl["description"],
        "template_key": template_key,
        "layout": layout,
        "charts": copy.deepcopy(tpl["charts"]),
        "data_sources": data_source_config or [],
        "refresh_config": tpl["refresh_config"],
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # 持久化到数据库
    try:
        from app.office.store import office_store
        if office_store is not None:
            _save_dashboard_to_db(office_store, dashboard)
    except Exception as e:
        log.warning("大屏存储失败（内存模式）: %s", e)

    return dashboard


def _save_dashboard_to_db(store: Any, dashboard: Dict[str, Any]) -> None:
    """将大屏配置写入数据库。"""
    from app.db.orm_models import DashboardRow

    with store.SessionFactory() as session:
        row = DashboardRow(
            dashboard_id=dashboard["dashboard_id"],
            name=dashboard["name"],
            slug=dashboard["slug"],
            description=dashboard.get("description"),
            template_key=dashboard.get("template_key"),
            layout=dashboard["layout"],
            charts=dashboard["charts"],
            data_sources=dashboard.get("data_sources", []),
            refresh_config=dashboard.get("refresh_config", {}),
            status=dashboard.get("status", "active"),
            created_by=dashboard.get("created_by"),
        )
        session.add(row)
        session.commit()


def list_dashboards() -> List[Dict[str, Any]]:
    """列出所有已创建的大屏。"""
    try:
        from app.office.store import office_store
        if office_store is None:
            return []
        return _list_dashboards_from_db(office_store)
    except Exception as e:
        log.warning("读取大屏列表失败: %s", e)
        return []


def _list_dashboards_from_db(store: Any) -> List[Dict[str, Any]]:
    from app.db.orm_models import DashboardRow

    with store.SessionFactory() as session:
        rows = session.query(DashboardRow).filter(
            DashboardRow.status != "archived"
        ).order_by(DashboardRow.created_at.desc()).all()
        return [_dashboard_row_to_dict(r) for r in rows]


def get_dashboard(dashboard_id: str) -> Optional[Dict[str, Any]]:
    """获取单个大屏的完整配置。"""
    try:
        from app.office.store import office_store
        if office_store is None:
            return None
        return _get_dashboard_from_db(office_store, dashboard_id)
    except Exception as e:
        log.warning("读取大屏失败: %s", e)
        return None


def _get_dashboard_from_db(store: Any, dashboard_id: str) -> Optional[Dict[str, Any]]:
    from app.db.orm_models import DashboardRow

    with store.SessionFactory() as session:
        row = session.get(DashboardRow, dashboard_id)
        if row is None:
            return None
        return _dashboard_row_to_dict(row)


def update_dashboard(dashboard_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新大屏配置。"""
    try:
        from app.office.store import office_store
        if office_store is None:
            return None
        return _update_dashboard_in_db(office_store, dashboard_id, updates)
    except Exception as e:
        log.warning("更新大屏失败: %s", e)
        return None


def _update_dashboard_in_db(store: Any, dashboard_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    from app.db.orm_models import DashboardRow

    with store.SessionFactory() as session:
        row = session.get(DashboardRow, dashboard_id)
        if row is None:
            return None
        for key in ["name", "description", "layout", "charts", "data_sources", "refresh_config", "status"]:
            if key in updates:
                setattr(row, key, updates[key])
        session.commit()
        session.refresh(row)
        return _dashboard_row_to_dict(row)


def refresh_dashboard_data(dashboard_id: str) -> Dict[str, Any]:
    """刷新大屏数据 — 执行各图表的 data_query 获取最新数据。"""
    dashboard = get_dashboard(dashboard_id)
    if dashboard is None:
        return {"error": f"大屏 {dashboard_id} 不存在"}

    results: Dict[str, Any] = {}
    from app.services.data_engineer import execute_sql

    for chart in dashboard.get("charts", []):
        chart_id = chart.get("id", "unknown")

        # KPI cards: execute each item's SQL individually
        if chart.get("chart_type") == "kpi_cards":
            kpi_results = []
            for item in chart.get("kpi_items", []):
                item_sql = item.get("sql", "")
                if not item_sql or item_sql.strip() in ("SELECT 0", ""):
                    kpi_results.append({"label": item["label"], "value": None})
                    continue
                try:
                    r = execute_sql(item_sql)
                    rows = r.get("rows", []) if isinstance(r, dict) else []
                    val = None
                    if rows:
                        val = list(rows[0].values())[0]
                        if val is not None:
                            val = float(val) if val != int(val) else int(val)
                    kpi_results.append({"label": item["label"], "value": val})
                except Exception:
                    kpi_results.append({"label": item["label"], "value": None})
            results[chart_id] = {"status": "ok", "kpi_values": kpi_results}
            continue

        query = chart.get("data_query", {})
        sql = query.get("sql", "")

        if not sql or sql.strip() == "SELECT 'manual' AS source":
            results[chart_id] = {"status": "skip", "reason": "手动数据或无查询"}
            continue

        try:
            result = execute_sql(sql)
            results[chart_id] = {"status": "ok", "data": result}
        except Exception as e:
            results[chart_id] = {"status": "error", "error": str(e)}

    return {
        "dashboard_id": dashboard_id,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }


def generate_custom_chart(
    chart_type: str,
    title: str,
    sql: str,
    refresh_interval: int = 300,
) -> Dict[str, Any]:
    """根据用户描述生成一个自定义 ECharts 图表配置。"""
    base_options = {
        "line": {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": []},
            "yAxis": {"type": "value"},
            "series": [{"type": "line", "smooth": True, "data": []}],
        },
        "bar": {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": []},
            "yAxis": {"type": "value"},
            "series": [{"type": "bar", "data": []}],
        },
        "pie": {
            "tooltip": {"trigger": "item"},
            "series": [{"type": "pie", "radius": ["40%", "70%"], "data": []}],
        },
        "gauge": {
            "series": [{"type": "gauge", "data": [{"value": 0}]}],
        },
        "funnel": {
            "series": [{"type": "funnel", "data": []}],
        },
        "radar": {
            "radar": {"indicator": []},
            "series": [{"type": "radar", "data": []}],
        },
    }

    echarts_option = copy.deepcopy(base_options.get(chart_type, base_options["line"]))

    return {
        "id": make_id("chart"),
        "title": title,
        "chart_type": chart_type,
        "echarts_option": echarts_option,
        "data_query": {
            "sql": sql,
            "refresh_interval": refresh_interval,
        },
    }


def _dashboard_row_to_dict(row: Any) -> Dict[str, Any]:
    return {
        "dashboard_id": row.dashboard_id,
        "name": row.name,
        "slug": row.slug,
        "description": row.description,
        "template_key": row.template_key,
        "layout": row.layout,
        "charts": row.charts,
        "data_sources": row.data_sources,
        "refresh_config": row.refresh_config,
        "status": row.status,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
