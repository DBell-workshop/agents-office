"""Mock 数据源 — 提供多品类模拟商品数据，用于开发和演示。"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from app.services.datasources.base import ProductDataSource


# ============================================================
# Mock 商品数据库（按品类组织）
# ============================================================

_MOCK_CATALOG: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    # ---------- 小厨宝 ----------
    "小厨宝": {
        "京东": [
            {
                "product_id": "jd_10001",
                "name": "美的小厨宝 5L 速热即热式电热水器",
                "brand": "美的",
                "price": 399.0,
                "original_price": 499.0,
                "promotions": ["满300减50", "新用户券"],
                "rating": 4.8,
                "review_count": 12500,
                "platform": "京东",
                "url": "https://item.jd.com/mock_10001.html",
                "image_url": "",
                "specs": {"容量": "5L", "功率": "1500W", "安装方式": "上出水"},
            },
            {
                "product_id": "jd_10002",
                "name": "海尔小厨宝 6.6L 家用厨房电热水器",
                "brand": "海尔",
                "price": 459.0,
                "original_price": 599.0,
                "promotions": ["跨店满减"],
                "rating": 4.7,
                "review_count": 8900,
                "platform": "京东",
                "url": "https://item.jd.com/mock_10002.html",
                "image_url": "",
                "specs": {"容量": "6.6L", "功率": "1500W", "安装方式": "上出水/下出水"},
            },
            {
                "product_id": "jd_10003",
                "name": "史密斯小厨宝 5L 出水断电安全型",
                "brand": "A.O.Smith",
                "price": 699.0,
                "original_price": 799.0,
                "promotions": ["以旧换新补贴最高300"],
                "rating": 4.9,
                "review_count": 6700,
                "platform": "京东",
                "url": "https://item.jd.com/mock_10003.html",
                "image_url": "",
                "specs": {"容量": "5L", "功率": "1500W", "安全特性": "出水断电"},
            },
        ],
        "淘宝": [
            {
                "product_id": "tb_20001",
                "name": "美的小厨宝 5升即热储水式厨房热水器",
                "brand": "美的",
                "price": 379.0,
                "original_price": 479.0,
                "promotions": ["淘金币抵扣", "店铺券满200减20"],
                "rating": 4.7,
                "review_count": 35000,
                "platform": "淘宝",
                "url": "https://item.taobao.com/mock_20001.html",
                "image_url": "",
                "specs": {"容量": "5L", "功率": "1500W", "安装方式": "上出水"},
            },
            {
                "product_id": "tb_20002",
                "name": "海尔6.6升小厨宝家用速热电热水器",
                "brand": "海尔",
                "price": 439.0,
                "original_price": 569.0,
                "promotions": ["88VIP 95折"],
                "rating": 4.6,
                "review_count": 21000,
                "platform": "淘宝",
                "url": "https://item.taobao.com/mock_20002.html",
                "image_url": "",
                "specs": {"容量": "6.6L", "功率": "1500W", "安装方式": "上出水"},
            },
        ],
        "拼多多": [
            {
                "product_id": "pdd_30001",
                "name": "美的5L小厨宝速热式厨房电热水器",
                "brand": "美的",
                "price": 349.0,
                "original_price": 399.0,
                "promotions": ["百亿补贴"],
                "rating": 4.5,
                "review_count": 50000,
                "platform": "拼多多",
                "url": "https://mobile.yangkeduo.com/mock_30001.html",
                "image_url": "",
                "specs": {"容量": "5L", "功率": "1500W", "安装方式": "上出水"},
            },
            {
                "product_id": "pdd_30002",
                "name": "海尔6.6L小厨宝即热式厨房电热水器",
                "brand": "海尔",
                "price": 419.0,
                "original_price": 529.0,
                "promotions": ["百亿补贴", "多人团再减10"],
                "rating": 4.5,
                "review_count": 28000,
                "platform": "拼多多",
                "url": "https://mobile.yangkeduo.com/mock_30002.html",
                "image_url": "",
                "specs": {"容量": "6.6L", "功率": "1500W", "安装方式": "上出水"},
            },
        ],
    },
    # ---------- 无线耳机 ----------
    "无线耳机": {
        "京东": [
            {
                "product_id": "jd_40001",
                "name": "Apple AirPods Pro 2 (USB-C) 主动降噪无线耳机",
                "brand": "Apple",
                "price": 1599.0,
                "original_price": 1899.0,
                "promotions": ["满1500减100", "PLUS 会员价"],
                "rating": 4.9,
                "review_count": 85000,
                "platform": "京东",
                "url": "https://item.jd.com/mock_40001.html",
                "image_url": "",
                "specs": {"降噪": "主动降噪", "续航": "6h (单次)", "接口": "USB-C", "防水": "IPX4"},
            },
            {
                "product_id": "jd_40002",
                "name": "索尼 WF-1000XM5 真无线降噪耳机",
                "brand": "Sony",
                "price": 1499.0,
                "original_price": 1999.0,
                "promotions": ["限时秒杀"],
                "rating": 4.8,
                "review_count": 32000,
                "platform": "京东",
                "url": "https://item.jd.com/mock_40002.html",
                "image_url": "",
                "specs": {"降噪": "主动降噪", "续航": "8h (单次)", "接口": "USB-C", "防水": "IPX4"},
            },
        ],
        "淘宝": [
            {
                "product_id": "tb_50001",
                "name": "Apple AirPods Pro 2 无线蓝牙降噪耳机 USB-C充电",
                "brand": "Apple",
                "price": 1549.0,
                "original_price": 1899.0,
                "promotions": ["88VIP 立减50", "花呗3期免息"],
                "rating": 4.9,
                "review_count": 120000,
                "platform": "淘宝",
                "url": "https://item.taobao.com/mock_50001.html",
                "image_url": "",
                "specs": {"降噪": "主动降噪", "续航": "6h (单次)", "接口": "USB-C", "防水": "IPX4"},
            },
            {
                "product_id": "tb_50002",
                "name": "华为 FreeBuds Pro 3 真无线入耳式降噪耳机",
                "brand": "华为",
                "price": 999.0,
                "original_price": 1199.0,
                "promotions": ["店铺券满800减80"],
                "rating": 4.7,
                "review_count": 45000,
                "platform": "淘宝",
                "url": "https://item.taobao.com/mock_50002.html",
                "image_url": "",
                "specs": {"降噪": "主动降噪", "续航": "6.5h (单次)", "接口": "USB-C", "防水": "IP54"},
            },
        ],
        "拼多多": [
            {
                "product_id": "pdd_60001",
                "name": "Apple AirPods Pro 2代 USB-C 主动降噪蓝牙耳机",
                "brand": "Apple",
                "price": 1479.0,
                "original_price": 1899.0,
                "promotions": ["百亿补贴"],
                "rating": 4.7,
                "review_count": 200000,
                "platform": "拼多多",
                "url": "https://mobile.yangkeduo.com/mock_60001.html",
                "image_url": "",
                "specs": {"降噪": "主动降噪", "续航": "6h (单次)", "接口": "USB-C", "防水": "IPX4"},
            },
        ],
    },
    # ---------- 机械键盘 ----------
    "机械键盘": {
        "京东": [
            {
                "product_id": "jd_70001",
                "name": "IQUNIX F97 露营主题 三模机械键盘 TTC快银轴",
                "brand": "IQUNIX",
                "price": 1099.0,
                "original_price": 1299.0,
                "promotions": ["跨店满减"],
                "rating": 4.8,
                "review_count": 5600,
                "platform": "京东",
                "url": "https://item.jd.com/mock_70001.html",
                "image_url": "",
                "specs": {"轴体": "TTC快银轴", "配列": "97键", "连接": "三模", "背光": "RGB"},
            },
            {
                "product_id": "jd_70002",
                "name": "Leopold FC660M 静电容机械键盘 Cherry红轴",
                "brand": "Leopold",
                "price": 899.0,
                "original_price": 999.0,
                "promotions": [],
                "rating": 4.9,
                "review_count": 3200,
                "platform": "京东",
                "url": "https://item.jd.com/mock_70002.html",
                "image_url": "",
                "specs": {"轴体": "Cherry红轴", "配列": "66键", "连接": "有线", "背光": "无"},
            },
        ],
        "淘宝": [
            {
                "product_id": "tb_80001",
                "name": "IQUNIX F97 露营 无线蓝牙三模RGB机械键盘",
                "brand": "IQUNIX",
                "price": 1049.0,
                "original_price": 1299.0,
                "promotions": ["官方旗舰店 满1000减60"],
                "rating": 4.8,
                "review_count": 8900,
                "platform": "淘宝",
                "url": "https://item.taobao.com/mock_80001.html",
                "image_url": "",
                "specs": {"轴体": "TTC快银轴", "配列": "97键", "连接": "三模", "背光": "RGB"},
            },
        ],
        "拼多多": [
            {
                "product_id": "pdd_90001",
                "name": "IQUNIX F97露营主题三模机械键盘 TTC快银轴",
                "brand": "IQUNIX",
                "price": 989.0,
                "original_price": 1299.0,
                "promotions": ["百亿补贴"],
                "rating": 4.6,
                "review_count": 15000,
                "platform": "拼多多",
                "url": "https://mobile.yangkeduo.com/mock_90001.html",
                "image_url": "",
                "specs": {"轴体": "TTC快银轴", "配列": "97键", "连接": "三模", "背光": "RGB"},
            },
        ],
    },
}


class MockDataSource(ProductDataSource):
    """Mock 数据源：基于关键词模糊匹配本地商品目录。"""

    async def search(
        self,
        query: str,
        platforms: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        # 模拟网络延迟
        await asyncio.sleep(0.3)

        # 关键词模糊匹配品类和商品
        results: Dict[str, List[Dict[str, Any]]] = {}
        query_lower = query.lower()

        for category, platform_products in _MOCK_CATALOG.items():
            # 品类名匹配 或 品类下商品名/品牌匹配
            category_match = query_lower in category.lower()

            for platform, products in platform_products.items():
                if platforms and platform not in platforms:
                    continue

                matched = []
                for p in products:
                    if category_match:
                        matched.append(p)
                    elif (
                        query_lower in p["name"].lower()
                        or query_lower in p["brand"].lower()
                    ):
                        matched.append(p)

                if matched:
                    if platform not in results:
                        results[platform] = []
                    results[platform].extend(matched)

        # 如果没有匹配，返回第一个品类的全部数据作为演示
        if not results:
            first_category = next(iter(_MOCK_CATALOG.values()))
            for platform, products in first_category.items():
                if platforms and platform not in platforms:
                    continue
                results[platform] = list(products)

        return results
