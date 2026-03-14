"""数据工程师 Agent 的核心服务 — 文件解析、Schema 推断、SQL 执行。

提供给 data_engineer Agent 的 Function Calling 工具：
- analyze_uploaded_file: 解析已上传的文件，返回列名/类型/预览
- create_table_from_file: 根据解析结果自动建表并导入数据
- execute_sql: 执行任意 SQL（支持 DDL）
- list_user_tables: 列出用户创建的所有表
- query_data: 查询表数据（SELECT only，带 limit 保护）
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

log = logging.getLogger(__name__)

# 用户上传文件存储目录
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 用户数据表前缀，与系统表隔离
USER_TABLE_PREFIX = "ud_"

# 最大预览行数
MAX_PREVIEW_ROWS = 10
# 查询结果最大行数
MAX_QUERY_ROWS = 200


def _get_engine():
    """获取 SQLAlchemy engine（复用项目现有连接）。"""
    from app.config import settings
    if not settings.database_url_sync:
        return None
    from sqlalchemy import create_engine
    return create_engine(settings.database_url_sync)


def _safe_table_name(raw: str) -> str:
    """将文件名转成安全的表名。"""
    name = Path(raw).stem.lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name or name[0].isdigit():
        name = "t_" + name
    return USER_TABLE_PREFIX + name[:50]


def _pd_dtype_to_sql(dtype_str: str) -> str:
    """Pandas dtype → PostgreSQL 类型。"""
    s = str(dtype_str).lower()
    if "int" in s:
        return "BIGINT"
    if "float" in s:
        return "DOUBLE PRECISION"
    if "bool" in s:
        return "BOOLEAN"
    if "datetime" in s:
        return "TIMESTAMPTZ"
    return "TEXT"


def _safe_col_name(col: str) -> str:
    """列名安全化。"""
    name = re.sub(r"[^a-zA-Z0-9_]", "_", str(col).strip()).lower()
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        name = "col"
    if name[0].isdigit():
        name = "c_" + name
    return name[:63]


# ============================================================
# 文件解析
# ============================================================

def parse_file(file_path: str) -> Dict[str, Any]:
    """解析 CSV/Excel 文件，返回 schema + 预览数据。"""
    p = Path(file_path)
    if not p.exists():
        return {"error": f"文件不存在: {file_path}"}

    ext = p.suffix.lower()
    try:
        if ext == ".csv":
            df = pd.read_csv(p, nrows=1000)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(p, nrows=1000)
        else:
            return {"error": f"不支持的文件格式: {ext}，目前支持 .csv, .xlsx, .xls"}
    except Exception as e:
        return {"error": f"文件解析失败: {str(e)[:200]}"}

    columns = []
    for col in df.columns:
        safe_name = _safe_col_name(col)
        sql_type = _pd_dtype_to_sql(df[col].dtype)
        null_count = int(df[col].isna().sum())
        unique_count = int(df[col].nunique())
        sample_values = df[col].dropna().head(3).tolist()
        columns.append({
            "original_name": str(col),
            "safe_name": safe_name,
            "pandas_dtype": str(df[col].dtype),
            "sql_type": sql_type,
            "null_count": null_count,
            "unique_count": unique_count,
            "sample_values": [str(v) for v in sample_values],
        })

    preview = df.head(MAX_PREVIEW_ROWS).fillna("").to_dict(orient="records")
    suggested_table = _safe_table_name(p.name)

    return {
        "file_name": p.name,
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "suggested_table_name": suggested_table,
        "columns": columns,
        "preview": preview,
    }


# ============================================================
# 建表 + 导入
# ============================================================

def create_table_from_file(
    file_path: str,
    table_name: Optional[str] = None,
    column_mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """根据文件自动建表并导入全部数据。

    Args:
        file_path: 已上传的文件路径
        table_name: 自定义表名（不含 ud_ 前缀会自动补）
        column_mapping: 列重命名映射 {原始列名: 新列名}
    """
    engine = _get_engine()
    if engine is None:
        return {"error": "数据库未配置，请设置 DATABASE_URL_SYNC"}

    p = Path(file_path)
    ext = p.suffix.lower()

    try:
        if ext == ".csv":
            df = pd.read_csv(p)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(p)
        else:
            return {"error": f"不支持的文件格式: {ext}"}
    except Exception as e:
        return {"error": f"文件读取失败: {str(e)[:200]}"}

    # 安全化列名
    safe_columns = {}
    for col in df.columns:
        if column_mapping and str(col) in column_mapping:
            safe_columns[col] = _safe_col_name(column_mapping[str(col)])
        else:
            safe_columns[col] = _safe_col_name(col)
    df.rename(columns=safe_columns, inplace=True)

    # 确定表名
    if table_name:
        if not table_name.startswith(USER_TABLE_PREFIX):
            table_name = USER_TABLE_PREFIX + table_name
        table_name = re.sub(r"[^a-z0-9_]", "_", table_name.lower())[:63]
    else:
        table_name = _safe_table_name(p.name)

    try:
        df.to_sql(table_name, engine, if_exists="replace", index=False)
        row_count = len(df)
        return {
            "table_name": table_name,
            "rows_imported": row_count,
            "columns": list(df.columns),
            "message": f"成功创建表 {table_name}，导入 {row_count} 行数据",
        }
    except Exception as e:
        return {"error": f"建表/导入失败: {str(e)[:300]}"}


# ============================================================
# SQL 执行（支持 DDL）
# ============================================================

def execute_sql(sql: str) -> Dict[str, Any]:
    """执行 SQL 语句，支持 SELECT / DDL / DML。

    安全边界：
    - 禁止 DROP DATABASE / DROP SCHEMA
    - 禁止操作系统表（非 ud_ 前缀的 DROP/ALTER/DELETE/TRUNCATE）
    """
    engine = _get_engine()
    if engine is None:
        return {"error": "数据库未配置，请设置 DATABASE_URL_SYNC"}

    sql_stripped = sql.strip().rstrip(";")
    sql_upper = sql_stripped.upper()

    # 安全检查
    if "DROP DATABASE" in sql_upper or "DROP SCHEMA" in sql_upper:
        return {"error": "禁止执行 DROP DATABASE / DROP SCHEMA 操作"}

    # 检查是否操作系统表（非用户表）
    dangerous_ops = ["DROP TABLE", "ALTER TABLE", "DELETE FROM", "TRUNCATE"]
    for op in dangerous_ops:
        if op in sql_upper:
            # 提取表名检查是否是用户表
            match = re.search(rf"{op}\s+(?:IF\s+EXISTS\s+)?(\w+)", sql_upper)
            if match:
                target_table = match.group(1).lower()
                if not target_table.startswith(USER_TABLE_PREFIX):
                    return {"error": f"禁止对系统表 {target_table} 执行 {op} 操作。只允许操作 {USER_TABLE_PREFIX}* 前缀的用户表。"}

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql_stripped))

            if result.returns_rows:
                rows = result.fetchmany(MAX_QUERY_ROWS)
                columns = list(result.keys())
                data = [dict(zip(columns, row)) for row in rows]
                total = len(data)
                return {
                    "type": "query",
                    "columns": columns,
                    "rows": data,
                    "row_count": total,
                    "truncated": total >= MAX_QUERY_ROWS,
                }
            else:
                conn.commit()
                return {
                    "type": "execute",
                    "rowcount": result.rowcount,
                    "message": f"执行成功，影响 {result.rowcount} 行",
                }
    except Exception as e:
        return {"error": f"SQL 执行失败: {str(e)[:300]}"}


# ============================================================
# 查表和查数据
# ============================================================

def list_user_tables() -> Dict[str, Any]:
    """列出所有用户创建的表（ud_ 前缀）。"""
    engine = _get_engine()
    if engine is None:
        return {"error": "数据库未配置"}

    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name LIKE 'ud_%' "
                "ORDER BY table_name"
            ))
            tables = []
            for (name,) in result:
                # 获取每个表的行数
                count_result = conn.execute(text(f'SELECT COUNT(*) FROM "{name}"'))
                row_count = count_result.scalar()
                # 获取列信息
                col_result = conn.execute(text(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    f"WHERE table_name = '{name}' ORDER BY ordinal_position"
                ))
                columns = [{"name": r[0], "type": r[1]} for r in col_result]
                tables.append({
                    "table_name": name,
                    "row_count": row_count,
                    "columns": columns,
                })
            return {"tables": tables, "total": len(tables)}
    except Exception as e:
        return {"error": f"查询失败: {str(e)[:200]}"}


def query_data(table_name: str, limit: int = 50, where: Optional[str] = None) -> Dict[str, Any]:
    """查询用户表数据（仅允许 ud_ 前缀表）。"""
    if not table_name.startswith(USER_TABLE_PREFIX):
        return {"error": f"只允许查询 {USER_TABLE_PREFIX}* 前缀的用户表"}

    safe_limit = min(max(1, limit), MAX_QUERY_ROWS)
    sql = f'SELECT * FROM "{table_name}"'
    if where:
        # 基本注入防护：不允许分号
        if ";" in where:
            return {"error": "WHERE 条件不允许包含分号"}
        sql += f" WHERE {where}"
    sql += f" LIMIT {safe_limit}"

    return execute_sql(sql)


# ============================================================
# 文件上传列表
# ============================================================

def list_uploaded_files() -> List[Dict[str, Any]]:
    """列出所有已上传的文件。"""
    files = []
    for f in sorted(UPLOAD_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in (".csv", ".xlsx", ".xls"):
            files.append({
                "file_name": f.name,
                "file_path": str(f),
                "size_bytes": f.stat().st_size,
                "extension": f.suffix.lower(),
            })
    return files


# ============================================================
# 数据清洗
# ============================================================

def clean_data(
    file_path: str,
    rules: Dict[str, Any],
) -> Dict[str, Any]:
    """按规则清洗数据文件，保存为新文件。

    Args:
        file_path: 原始文件路径
        rules: 清洗规则，支持以下字段：
            - fill_na: dict  列名 → 填充值  （如 {"price": 0, "color": "未知"}）
            - drop_na_columns: list  这些列有空值则删除整行
            - drop_duplicates: bool  是否去重
            - rename_columns: dict  列重命名映射 {旧名: 新名}
            - unify_values: dict  值统一映射 {列名: {旧值: 新值, ...}}

    Returns:
        {"cleaned_file_path": ..., "original_rows": N, "cleaned_rows": N, "changes": [...]}
    """
    p = Path(file_path)
    if not p.exists():
        return {"error": f"文件不存在: {file_path}"}

    ext = p.suffix.lower()
    try:
        if ext == ".csv":
            df = pd.read_csv(p)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(p)
        else:
            return {"error": f"不支持的文件格式: {ext}"}
    except Exception as e:
        return {"error": f"文件读取失败: {str(e)[:200]}"}

    original_rows = len(df)
    changes: List[str] = []

    # 1. 值统一（在填充空值之前做，这样新填充的值不会被替换）
    unify = rules.get("unify_values", {})
    for col, mapping in unify.items():
        if col in df.columns:
            df[col] = df[col].replace(mapping)
            changes.append(f"列 {col}：统一了 {len(mapping)} 种值")

    # 2. 填充空值
    fill_na = rules.get("fill_na", {})
    for col, value in fill_na.items():
        if col in df.columns:
            null_count = int(df[col].isna().sum())
            if null_count > 0:
                df[col] = df[col].fillna(value)
                changes.append(f"列 {col}：填充了 {null_count} 个空值为 {value!r}")

    # 3. 删除指定列有空值的行
    drop_cols = rules.get("drop_na_columns", [])
    for col in drop_cols:
        if col in df.columns:
            before = len(df)
            df = df.dropna(subset=[col])
            dropped = before - len(df)
            if dropped > 0:
                changes.append(f"列 {col}：删除了 {dropped} 行空值行")

    # 4. 去重
    if rules.get("drop_duplicates", False):
        before = len(df)
        df = df.drop_duplicates()
        dropped = before - len(df)
        if dropped > 0:
            changes.append(f"去重：删除了 {dropped} 行重复数据")

    # 5. 列重命名
    rename = rules.get("rename_columns", {})
    if rename:
        df = df.rename(columns=rename)
        changes.append(f"重命名了 {len(rename)} 列")

    # 保存清洗后的文件
    cleaned_name = p.stem + "_cleaned" + p.suffix
    cleaned_path = UPLOAD_DIR / cleaned_name
    if ext == ".csv":
        df.to_csv(cleaned_path, index=False)
    else:
        df.to_excel(cleaned_path, index=False)

    if not changes:
        changes.append("数据质量良好，无需修改")

    return {
        "cleaned_file_path": str(cleaned_path),
        "original_rows": original_rows,
        "cleaned_rows": len(df),
        "rows_removed": original_rows - len(df),
        "changes": changes,
    }


# ============================================================
# 外部数据库连接测试
# ============================================================

def test_db_connection(
    db_type: str,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
) -> Dict[str, Any]:
    """测试外部数据库连接，成功则返回表列表。

    Args:
        db_type: 数据库类型（postgresql / mysql / sqlite）
        host: 主机地址
        port: 端口号
        database: 数据库名
        username: 用户名
        password: 密码
    """
    from sqlalchemy import create_engine, text

    # 构建连接字符串
    db_type_lower = db_type.lower().strip()
    driver_map = {
        "postgresql": "postgresql",
        "postgres": "postgresql",
        "mysql": "mysql+pymysql",
        "mariadb": "mysql+pymysql",
        "sqlite": "sqlite",
    }
    driver = driver_map.get(db_type_lower)
    if not driver:
        return {"error": f"不支持的数据库类型: {db_type}，目前支持: postgresql, mysql, sqlite"}

    if driver == "sqlite":
        url = f"sqlite:///{database}"
    else:
        url = f"{driver}://{username}:{password}@{host}:{port}/{database}"

    try:
        engine = create_engine(url, connect_args={"connect_timeout": 5} if "sqlite" not in driver else {})
        with engine.connect() as conn:
            # 测试连接
            conn.execute(text("SELECT 1"))

            # 获取表列表
            if "postgresql" in driver:
                result = conn.execute(text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name"
                ))
            elif "mysql" in driver:
                result = conn.execute(text("SHOW TABLES"))
            else:
                result = conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ))

            tables = [row[0] for row in result]

        engine.dispose()
        return {
            "status": "connected",
            "db_type": db_type_lower,
            "host": host,
            "database": database,
            "tables": tables,
            "table_count": len(tables),
            "message": f"连接成功！发现 {len(tables)} 张表。",
        }
    except Exception as e:
        return {"error": f"连接失败: {str(e)[:300]}"}
