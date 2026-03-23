"""
seed_mock_data.py — 向 PostgreSQL 写入电商模拟数据，供数据大屏展示使用。

用法：
    python scripts/seed_mock_data.py

依赖环境变量：
    DATABASE_URL_SYNC  — PostgreSQL 同步连接串，例如
                         postgresql://user:pass@localhost:5432/dbname

可重复执行：脚本先 DROP TABLE IF EXISTS，再重建并插入数据。
"""
from __future__ import annotations

import random
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Tuple

# 将项目根目录加入 sys.path，使 app.config 可以正常导入
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

from app.config import settings


# ============================================================
# 数据常量
# ============================================================

CHANNELS: List[Tuple[str, float]] = [
    ("京东", 0.30),
    ("淘宝", 0.25),
    ("拼多多", 0.20),
    ("抖音", 0.15),
    ("自营官网", 0.10),
]

STATUSES: List[Tuple[str, float]] = [
    ("paid", 0.70),
    ("pending", 0.15),
    ("returned", 0.10),
    ("cancelled", 0.05),
]

# 品类 → (权重, 最低金额, 最高金额, 商品列表)
CATEGORIES = {
    "数码": (
        0.15, 1000, 3000,
        ["苹果iPhone 15", "华为Mate 60", "小米14 Pro", "索尼WH-1000XM5",
         "iPad Air第6代", "MacBook Air M3", "戴尔XPS 15", "DJI Mini 4"],
    ),
    "服饰": (
        0.25, 80, 800,
        ["优衣库羊绒外套", "Levi's 501牛仔裤", "耐克Air Max运动鞋",
         "阿迪达斯卫衣", "波司登羽绒服", "ZARA碎花连衣裙",
         "H&M棉质T恤", "无印良品亚麻衬衫"],
    ),
    "美妆": (
        0.20, 100, 800,
        ["兰蔻小黑瓶精华", "SK-II神仙水", "雅诗兰黛粉底液",
         "花西子苗族印象礼盒", "完美日记眼影盘",
         "科颜氏高保湿面霜", "赫莲娜绿宝瓶", "娇兰帝皇蜂姿面霜"],
    ),
    "食品": (
        0.15, 30, 200,
        ["三只松鼠坚果礼盒", "良品铺子肉脯", "旺旺雪饼大礼包",
         "伊利金典纯牛奶", "农夫山泉矿泉水", "元气森林气泡水",
         "百草味每日坚果", "稻香村老婆饼"],
    ),
    "家居": (
        0.15, 150, 2000,
        ["宜家BILLY书柜", "美的空气净化器", "小米扫地机器人",
         "九阳电饭煲", "苏泊尔炒锅套装", "公牛插线板5位",
         "飞利浦LED台灯", "北欧实木茶几"],
    ),
    "母婴": (
        0.10, 80, 600,
        ["爱特福奶粉3段", "帮宝适纸尿裤L码", "贝亲奶瓶PPSU",
         "好奇铂金纸尿裤", "美赞臣蓝臻奶粉", "飞鹤星飞帆奶粉"],
    ),
}

# 双十一大促阶段（模拟历史数据用，不影响今日数据）
DOUBLE11_PHASES = ["预售期", "正式期", "返场期"]


# ============================================================
# 工具函数
# ============================================================

def _weighted_choice(pairs: List[Tuple[str, float]]) -> str:
    """按权重随机抽取一个字符串值。"""
    labels = [p[0] for p in pairs]
    weights = [p[1] for p in pairs]
    return random.choices(labels, weights=weights, k=1)[0]


def _random_category() -> Tuple[str, float, str]:
    """返回 (品类名, 金额, 商品名)。"""
    cat_names = list(CATEGORIES.keys())
    cat_weights = [CATEGORIES[c][0] for c in cat_names]
    cat = random.choices(cat_names, weights=cat_weights, k=1)[0]
    _, lo, hi, products = CATEGORIES[cat]
    amount = round(random.uniform(lo, hi), 2)
    product = random.choice(products)
    return cat, amount, product


def _gen_uid() -> str:
    return "u" + uuid.uuid4().hex[:12]


def _gen_oid() -> str:
    return "o" + uuid.uuid4().hex[:18]


def _today_timestamps(count: int) -> List[datetime]:
    """
    生成今天从 00:00 到当前时刻的时间戳列表。
    早高峰(10-12)和晚高峰(20-22)密度提高 3 倍。
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    total_seconds = int((now - today_start).total_seconds())
    if total_seconds <= 0:
        total_seconds = 3600

    # 生成带权重的秒数列表
    seconds_list: List[int] = []
    # 先生成 count * 3 个候选值，再按权重筛选到 count 个
    candidates = random.choices(range(total_seconds), k=count * 4)
    for s in candidates:
        hour = (s // 3600)
        # 高峰时段提高权重：接受概率
        if 10 <= hour < 12 or 20 <= hour < 22:
            accept = 0.9
        elif 0 <= hour < 6:
            accept = 0.2
        else:
            accept = 0.5
        if random.random() < accept:
            seconds_list.append(s)
        if len(seconds_list) >= count:
            break

    # 如果不够就补齐（均匀）
    while len(seconds_list) < count:
        seconds_list.append(random.randint(0, total_seconds - 1))

    seconds_list = seconds_list[:count]
    return [today_start + timedelta(seconds=s) for s in seconds_list]


def _historical_timestamps(day_offset: int, count: int) -> List[datetime]:
    """生成指定日期（今天 - day_offset）的随机时间戳。"""
    base = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=day_offset)
    total_seconds = 86400
    return [base + timedelta(seconds=random.randint(0, total_seconds - 1))
            for _ in range(count)]


# ============================================================
# DDL
# ============================================================

DDL_ORDERS = """
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;

CREATE TABLE orders (
    id          SERIAL PRIMARY KEY,
    order_id    VARCHAR(32) UNIQUE NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL,
    amount      NUMERIC(12,2) NOT NULL,
    status      VARCHAR(20)   NOT NULL,
    channel     VARCHAR(30)   NOT NULL,
    category    VARCHAR(30)   NOT NULL,
    user_id     VARCHAR(32)   NOT NULL,
    product_name VARCHAR(100) NOT NULL,
    event       VARCHAR(30)   NULL,
    phase       VARCHAR(20)   NULL
);

CREATE INDEX idx_orders_created_at ON orders (created_at);
CREATE INDEX idx_orders_event      ON orders (event);
CREATE INDEX idx_orders_channel    ON orders (channel);
CREATE INDEX idx_orders_status     ON orders (status);
"""

DDL_PAGE_VIEWS = """
DROP TABLE IF EXISTS page_views CASCADE;

CREATE TABLE page_views (
    id         SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    user_id    VARCHAR(32) NOT NULL,
    page_url   VARCHAR(200) NOT NULL
);

CREATE INDEX idx_pv_created_at ON page_views (created_at);
CREATE INDEX idx_pv_user_id    ON page_views (user_id);
"""

DDL_ORDER_ITEMS = """
CREATE TABLE order_items (
    id           SERIAL PRIMARY KEY,
    order_id     VARCHAR(32) NOT NULL,
    product_name VARCHAR(100) NOT NULL,
    amount       NUMERIC(12,2) NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 1,
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_oi_order_id   ON order_items (order_id);
CREATE INDEX idx_oi_created_at ON order_items (created_at);
"""

PAGE_URLS = [
    "/", "/products", "/products/detail", "/cart", "/checkout",
    "/user/profile", "/search", "/promotions/618", "/promotions/double11",
    "/brand/apple", "/brand/huawei", "/brand/nike",
]


# ============================================================
# 数据生成
# ============================================================

def build_orders_batch(timestamps: List[datetime], user_pool: List[str],
                       event: str = None, phase: str = None) -> List[dict]:
    rows = []
    for ts in timestamps:
        cat, amount, product = _random_category()
        rows.append({
            "order_id": _gen_oid(),
            "created_at": ts,
            "amount": amount,
            "status": _weighted_choice(STATUSES),
            "channel": _weighted_choice(CHANNELS),
            "category": cat,
            "user_id": random.choice(user_pool),
            "product_name": product,
            "event": event,
            "phase": phase,
        })
    return rows


def build_page_views_batch(timestamps: List[datetime],
                           user_pool: List[str]) -> List[dict]:
    rows = []
    for ts in timestamps:
        rows.append({
            "created_at": ts,
            "user_id": random.choice(user_pool),
            "page_url": random.choice(PAGE_URLS),
        })
    return rows


def build_order_items_from_orders(order_rows: List[dict]) -> List[dict]:
    items = []
    for o in order_rows:
        n_items = random.randint(1, 3)
        base_amount = o["amount"]
        for i in range(n_items):
            qty = random.randint(1, 3)
            item_amount = round(base_amount / n_items * random.uniform(0.8, 1.2), 2)
            items.append({
                "order_id": o["order_id"],
                "product_name": o["product_name"] + (f" x{i+1}" if n_items > 1 else ""),
                "amount": item_amount,
                "quantity": qty,
                "created_at": o["created_at"],
            })
    return items


# ============================================================
# 批量插入
# ============================================================

BATCH_SIZE = 500


def insert_orders(conn, rows: List[dict]) -> None:
    if not rows:
        return
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        conn.execute(
            text("""
                INSERT INTO orders
                    (order_id, created_at, amount, status, channel, category,
                     user_id, product_name, event, phase)
                VALUES
                    (:order_id, :created_at, :amount, :status, :channel, :category,
                     :user_id, :product_name, :event, :phase)
                ON CONFLICT (order_id) DO NOTHING
            """),
            batch,
        )


def insert_page_views(conn, rows: List[dict]) -> None:
    if not rows:
        return
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        conn.execute(
            text("""
                INSERT INTO page_views (created_at, user_id, page_url)
                VALUES (:created_at, :user_id, :page_url)
            """),
            batch,
        )


def insert_order_items(conn, rows: List[dict]) -> None:
    if not rows:
        return
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        conn.execute(
            text("""
                INSERT INTO order_items (order_id, product_name, amount, quantity, created_at)
                VALUES (:order_id, :product_name, :amount, :quantity, :created_at)
            """),
            batch,
        )


# ============================================================
# 主逻辑
# ============================================================

def main() -> None:
    db_url = settings.database_url_sync
    if not db_url:
        print("[ERROR] DATABASE_URL_SYNC 未配置，请检查 .env 文件。")
        sys.exit(1)

    print(f"[INFO] 连接数据库：{db_url[:40]}...")
    engine = create_engine(db_url, echo=False)

    with engine.begin() as conn:
        # ---- 建表 ----
        print("[INFO] 重建 orders 表...")
        conn.execute(text(DDL_ORDERS))
        print("[INFO] 重建 page_views 表...")
        conn.execute(text(DDL_PAGE_VIEWS))
        print("[INFO] 重建 order_items 表...")
        conn.execute(text(DDL_ORDER_ITEMS))

        # ---- 生成用户池（约 800 个 UV） ----
        user_pool = [_gen_uid() for _ in range(800)]
        # page_views 额外用户
        extra_users = [_gen_uid() for _ in range(200)]
        pv_user_pool = user_pool + extra_users

        # ====================================================
        # 今日数据（约 2000 条订单 + 5000 条 PV）
        # ====================================================
        print("[INFO] 生成今日订单数据（约 2000 条）...")
        today_ts = _today_timestamps(2000)
        today_orders = build_orders_batch(today_ts, user_pool)
        insert_orders(conn, today_orders)
        print(f"  -> 写入 {len(today_orders)} 条 orders")

        # 今日 order_items
        today_items = build_order_items_from_orders(today_orders)
        insert_order_items(conn, today_items)
        print(f"  -> 写入 {len(today_items)} 条 order_items（今日）")

        # 今日 page_views（约 5000 条）
        print("[INFO] 生成今日 page_views 数据（约 5000 条）...")
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        total_secs = max(int((now - today_start).total_seconds()), 3600)
        pv_ts_today = [
            today_start + timedelta(seconds=random.randint(0, total_secs - 1))
            for _ in range(5000)
        ]
        today_pvs = build_page_views_batch(pv_ts_today, pv_user_pool)
        insert_page_views(conn, today_pvs)
        print(f"  -> 写入 {len(today_pvs)} 条 page_views（今日）")

        # ====================================================
        # 近 7 天历史数据（每天 800~1500 条）
        # ====================================================
        print("[INFO] 生成近 7 天历史订单数据...")
        total_hist_orders = 0
        total_hist_items = 0
        for day_offset in range(1, 8):
            count = random.randint(800, 1500)
            day_ts = _historical_timestamps(day_offset, count)

            # 过去 7 天偶发双十一返场数据（模拟 event 字段有数据）
            if day_offset <= 3:
                # 最近 3 天：30% 概率标记为 double11 返场期
                hist_orders = []
                for ts in day_ts:
                    if random.random() < 0.3:
                        event, phase = "double11", "返场期"
                    else:
                        event, phase = None, None
                    cat, amount, product = _random_category()
                    hist_orders.append({
                        "order_id": _gen_oid(),
                        "created_at": ts,
                        "amount": amount,
                        "status": _weighted_choice(STATUSES),
                        "channel": _weighted_choice(CHANNELS),
                        "category": cat,
                        "user_id": random.choice(user_pool),
                        "product_name": product,
                        "event": event,
                        "phase": phase,
                    })
            else:
                hist_orders = build_orders_batch(day_ts, user_pool)

            insert_orders(conn, hist_orders)
            hist_items = build_order_items_from_orders(hist_orders)
            insert_order_items(conn, hist_items)
            total_hist_orders += len(hist_orders)
            total_hist_items += len(hist_items)
            print(f"  -> 历史第 -{day_offset} 天：{len(hist_orders)} 条 orders")

        print(f"  -> 历史合计：{total_hist_orders} 条 orders, {total_hist_items} 条 order_items")

        # ====================================================
        # 双十一大促历史数据（模拟去年 11 月的 event 数据）
        # ====================================================
        print("[INFO] 生成双十一大促历史数据（约 5000 条）...")
        double11_orders_all: List[dict] = []
        phase_windows = [
            ("预售期", 10),   # 10 天前
            ("正式期", 5),    # 5 天前
            ("返场期", 3),    # 3 天前（已在上方部分插入，这里补充独立 event 数据）
        ]
        for phase_name, offset_base in phase_windows:
            phase_count = random.randint(1200, 2000)
            # 分散在 2 天内
            for d in range(2):
                day_offset = offset_base + d
                ts_list = _historical_timestamps(day_offset, phase_count // 2)
                phase_rows = build_orders_batch(
                    ts_list, user_pool, event="double11", phase=phase_name
                )
                double11_orders_all.extend(phase_rows)

        insert_orders(conn, double11_orders_all)
        d11_items = build_order_items_from_orders(double11_orders_all)
        insert_order_items(conn, d11_items)
        print(f"  -> 双十一：{len(double11_orders_all)} 条 orders, {len(d11_items)} 条 order_items")

    # ---- 统计 ----
    print("\n[INFO] 数据写入完成，统计汇总：")
    with engine.connect() as conn:
        total_orders = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
        total_pvs = conn.execute(text("SELECT COUNT(*) FROM page_views")).scalar()
        total_items = conn.execute(text("SELECT COUNT(*) FROM order_items")).scalar()
        today_cnt = conn.execute(
            text("SELECT COUNT(*) FROM orders WHERE created_at >= CURRENT_DATE")
        ).scalar()
        d11_cnt = conn.execute(
            text("SELECT COUNT(*) FROM orders WHERE event = 'double11'")
        ).scalar()

        print(f"  orders 总计    : {total_orders:,} 条")
        print(f"  orders 今日    : {today_cnt:,} 条")
        print(f"  orders 双十一  : {d11_cnt:,} 条")
        print(f"  page_views 总计: {total_pvs:,} 条")
        print(f"  order_items 总计: {total_items:,} 条")

    print("\n[OK] seed_mock_data.py 执行成功。")


if __name__ == "__main__":
    main()
