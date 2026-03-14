"""
Best Buy 开放数据集导入脚本

从 bestbuy_products.json 中筛选 7 大家电品类商品，
映射字段后批量导入 PostgreSQL products 表。

数据源: https://github.com/BestBuyAPIs/open-data-set
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
DB_URL = "postgresql://ecom_dev:ecom_dev_pass@localhost:5432/ecom_ai_lab"
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "bestbuy_products.json"
BATCH_SIZE = 500

# ---------------------------------------------------------------------------
# 品类映射规则
# 关键词 -> 中文品类名
# 匹配优先级：先精确匹配，再宽泛匹配
# ---------------------------------------------------------------------------
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    # (中文品类名, [英文关键词列表 - 全部小写])
    ("冰箱", [
        "refrigerator", "fridge", "freezer", "mini fridge",
        "wine cooler", "beverage cooler", "ice maker",
    ]),
    ("电视", [
        "television", " tv ", "tv,", "tv.", '"tv"',
        "smart tv", "led tv", "oled tv", "qled tv", "lcd tv",
        "4k tv", "8k tv", "hdtv", "flat-screen",
    ]),
    ("洗衣机", [
        "washing machine", "clothes washer", "clothes dryer",
        "laundry", "front load washer", "top load washer",
        "washer/dryer", "washer & dryer",
    ]),
    ("空调", [
        "air conditioner", "air conditioning", "a/c unit",
        "portable ac", "window ac", "mini split",
        "central air", "hvac", "dehumidifier",
    ]),
    ("厨房电器", [
        "dishwasher", "water purifier", "water filter",
        "oven", "microwave", "cooktop", "stove",
        "garbage disposal", "range hood", "hood fan",
        "gas range", "electric range", "kitchen range",
        "convection oven", "wall oven", "toaster oven",
    ]),
    ("扫地机器人", [
        "robot vacuum", "roomba", "robotic vacuum", "roborock",
        "robot cleaner", "auto vacuum",
    ]),
    ("热水器", [
        "water heater", "tankless water", "hot water",
        "boiler", "instant water heater",
    ]),
]

# 为电视品类单独处理的精确模式，避免误匹配含 "tv" 子串的其他词
_TV_EXACT_RE = re.compile(
    r"""
    (?:^|[\s"'\-/,.(])   # 前面是开头或分隔符
    tv
    (?:$|[\s"'\-/,.)])    # 后面是结尾或分隔符
    """,
    re.IGNORECASE | re.VERBOSE,
)


def classify_product(product: dict) -> str | None:
    """
    根据商品名称和分类路径判断是否属于 7 大家电品类。

    返回中文品类名，若不匹配则返回 None。
    """
    # 拼接可搜索的文本
    name = (product.get("name") or "").lower()
    # Best Buy 数据中品类可能在 categoryPath, category, class, subclass 等字段
    category_parts = []
    cat_path = product.get("categoryPath")
    if isinstance(cat_path, list):
        for item in cat_path:
            if isinstance(item, dict):
                category_parts.append((item.get("name") or "").lower())
            elif isinstance(item, str):
                category_parts.append(item.lower())
    elif isinstance(cat_path, str):
        category_parts.append(cat_path.lower())

    for field in ("category", "class", "subclass", "department"):
        val = product.get(field)
        if isinstance(val, str):
            category_parts.append(val.lower())

    search_text = f" {name} " + " ".join(category_parts)
    cat_text = " ".join(category_parts)

    # 只匹配真正的家电品类，通过品类路径中的关键词验证
    appliance_cat_keywords = [
        "appliance", "refrigerat", "freezer", "washer", "dryer", "laundry",
        "dishwasher", "oven", "range", "cooktop", "microwave",
        "air conditioner", "hvac", "vacuum", "water heater", "television",
        "tv", "home theater",
    ]
    is_appliance_category = any(k in cat_text for k in appliance_cat_keywords)

    for zh_category, keywords in CATEGORY_RULES:
        for kw in keywords:
            # 特殊处理 "tv" 这种短关键词，用正则精确匹配
            if kw.strip() == "tv":
                if _TV_EXACT_RE.search(name) or any(
                    _TV_EXACT_RE.search(cp) for cp in category_parts
                ):
                    return zh_category
                continue

            if kw in search_text:
                # 需要品类路径验证的关键词（容易误匹配）
                if not is_appliance_category and kw in (
                    "oven", "stove", "cooktop",
                ):
                    continue
                return zh_category

    return None


def extract_attributes(product: dict) -> dict:
    """
    从原始数据中提取有意义的规格参数。
    Best Buy 数据实际字段: sku, name, type, price, upc, category,
    shipping, description, manufacturer, model, url, image
    """
    attrs: dict = {}

    # 价格
    price = product.get("price")
    if price is not None and price != "":
        attrs["price"] = price
    shipping = product.get("shipping")
    if shipping is not None and shipping != "":
        attrs["shipping_cost"] = shipping

    # 商品描述
    desc = product.get("description")
    if desc:
        attrs["description"] = desc

    # 制造商和型号
    manufacturer = product.get("manufacturer")
    if manufacturer:
        attrs["manufacturer"] = manufacturer
    model = product.get("model")
    if model:
        attrs["model_number"] = model

    # UPC
    upc = product.get("upc")
    if upc:
        attrs["upc"] = upc

    # 商品类型
    prod_type = product.get("type")
    if prod_type:
        attrs["product_type"] = prod_type

    # 图片
    image = product.get("image")
    if image:
        attrs["image_url"] = image

    # 品类路径（保留结构化数据供语义分析用）
    cat_path = product.get("category")
    if isinstance(cat_path, list) and cat_path:
        attrs["category_path"] = [
            item.get("name") if isinstance(item, dict) else item
            for item in cat_path
        ]

    return attrs


def build_record(product: dict, zh_category: str) -> dict:
    """
    将原始 Best Buy 商品数据映射为 products 表记录。
    """
    sku = str(product.get("sku", ""))
    product_id = f"bb_{sku}"
    name = product.get("name") or "Unknown"
    brand = product.get("manufacturer") or product.get("brand") or None

    # 商品 URL
    source_url = product.get("url")
    if source_url and not source_url.startswith("http"):
        source_url = f"https://www.bestbuy.com{source_url}"

    attributes = extract_attributes(product)
    now = datetime.now(timezone.utc)

    return {
        "product_id": product_id,
        "sku": sku,
        "name": name,
        "category": zh_category,
        "brand": brand,
        "attributes": json.dumps(attributes, ensure_ascii=False),
        "source_platform": "bestbuy",
        "source_url": source_url,
        "raw_data": json.dumps(product, ensure_ascii=False, default=str),
        "created_at": now,
        "updated_at": now,
    }


def main() -> None:
    # ------------------------------------------------------------------
    # 1. 加载数据
    # ------------------------------------------------------------------
    if not DATA_FILE.exists():
        print(f"[ERROR] 数据文件不存在: {DATA_FILE}")
        print("请先运行以下命令下载数据:")
        print(f"  curl -L -o {DATA_FILE} "
              "https://github.com/BestBuyAPIs/open-data-set/raw/master/products.json")
        sys.exit(1)

    print(f"[INFO] 正在加载数据文件: {DATA_FILE}")
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw_products = json.load(f)

    total_count = len(raw_products)
    print(f"[INFO] 总商品数: {total_count:,}")

    # ------------------------------------------------------------------
    # 2. 筛选家电品类
    # ------------------------------------------------------------------
    print("[INFO] 正在筛选 7 大家电品类...")
    records: list[dict] = []
    category_counts: dict[str, int] = {}

    for product in raw_products:
        zh_cat = classify_product(product)
        if zh_cat is None:
            continue
        record = build_record(product, zh_cat)
        records.append(record)
        category_counts[zh_cat] = category_counts.get(zh_cat, 0) + 1

    print(f"[INFO] 筛选出家电商品: {len(records):,} 条")
    print()
    print("=" * 50)
    print("品类分布:")
    print("=" * 50)
    for cat in ["冰箱", "电视", "洗衣机", "空调", "厨房电器", "扫地机器人", "热水器"]:
        count = category_counts.get(cat, 0)
        bar = "#" * min(count // 10, 50)
        print(f"  {cat:8s} | {count:>6,} 条 | {bar}")
    print("=" * 50)
    print(f"  {'合计':8s} | {len(records):>6,} 条")
    print()

    if len(records) == 0:
        print("[WARN] 未筛选到任何家电品类商品！")
        print("[WARN] 请检查数据文件格式或调整关键词匹配规则。")
        sys.exit(0)

    if len(records) < 100:
        print(f"[WARN] 家电品类商品数量较少 ({len(records)} 条)，"
              "后续可考虑补充 Amazon 等其他数据源。")
        print()

    # ------------------------------------------------------------------
    # 3. 批量导入 PostgreSQL
    # ------------------------------------------------------------------
    print(f"[INFO] 正在连接数据库: {DB_URL.split('@')[1]}")
    engine = create_engine(DB_URL, echo=False)

    upsert_sql = text("""
        INSERT INTO products (
            product_id, sku, name, category, brand,
            attributes, source_platform, source_url,
            raw_data, created_at, updated_at
        )
        VALUES (
            :product_id, :sku, :name, :category, :brand,
            CAST(:attributes AS jsonb), :source_platform, :source_url,
            CAST(:raw_data AS jsonb), :created_at, :updated_at
        )
        ON CONFLICT (product_id) DO NOTHING
    """)

    inserted = 0
    skipped = 0

    with engine.begin() as conn:
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i : i + BATCH_SIZE]
            result = conn.execute(upsert_sql, batch)
            batch_inserted = result.rowcount
            inserted += batch_inserted
            skipped += len(batch) - batch_inserted
            progress = min(i + BATCH_SIZE, len(records))
            print(f"  [BATCH] {progress:>6,}/{len(records):,} "
                  f"(本批插入 {batch_inserted}, 跳过 {len(batch) - batch_inserted})")

    print()
    print(f"[INFO] 导入完成: 插入 {inserted:,} 条, 跳过(已存在) {skipped:,} 条")

    # ------------------------------------------------------------------
    # 4. 验证查询
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("数据库验证")
    print("=" * 60)

    with engine.connect() as conn:
        # 各品类数量
        result = conn.execute(text("""
            SELECT category, COUNT(*) as cnt
            FROM products
            WHERE source_platform = 'bestbuy'
            GROUP BY category
            ORDER BY cnt DESC
        """))
        rows = result.fetchall()
        print()
        print("数据库中 Best Buy 各品类数量:")
        total_db = 0
        for row in rows:
            print(f"  {row[0]:12s} | {row[1]:>6,} 条")
            total_db += row[1]
        print(f"  {'合计':12s} | {total_db:>6,} 条")

        # 样例数据
        print()
        print("-" * 60)
        print("样例数据 (每品类 1 条):")
        print("-" * 60)

        for row in rows:
            cat = row[0]
            sample = conn.execute(text("""
                SELECT product_id, name, brand, category,
                       attributes->>'regular_price' as price,
                       attributes->>'customer_rating' as rating
                FROM products
                WHERE source_platform = 'bestbuy' AND category = :cat
                LIMIT 1
            """), {"cat": cat}).fetchone()
            if sample:
                print(f"\n  [{cat}]")
                print(f"    ID:    {sample[0]}")
                print(f"    名称:  {sample[1]}")
                print(f"    品牌:  {sample[2]}")
                print(f"    价格:  ${sample[4]}" if sample[4] else f"    价格:  N/A")
                print(f"    评分:  {sample[5]}" if sample[5] else f"    评分:  N/A")

    print()
    print("[DONE] Best Buy 数据导入完成!")
    engine.dispose()


if __name__ == "__main__":
    main()
