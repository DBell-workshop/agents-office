"""商品数据源抽象接口。

所有数据源（mock、浏览器采集、API）实现此接口，比价 Skill 通过接口获取数据。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ProductDataSource(ABC):
    """商品数据源抽象基类。"""

    @abstractmethod
    async def search(
        self,
        query: str,
        platforms: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """在多平台搜索商品。

        Args:
            query: 搜索关键词，如 "小厨宝"、"iPhone 16"
            platforms: 限定平台列表，None 表示搜索所有支持的平台

        Returns:
            按平台分组的商品列表::

                {
                    "京东": [
                        {
                            "product_id": "jd_10001",
                            "name": "美的小厨宝 5L ...",
                            "brand": "美的",
                            "price": 399.0,
                            "original_price": 499.0,
                            "promotions": ["满300减50"],
                            "rating": 4.8,
                            "review_count": 12500,
                            "platform": "京东",
                            "url": "https://...",
                            "image_url": "",
                            "specs": {"容量": "5L", "功率": "1500W"},
                        },
                        ...
                    ],
                    "淘宝": [...],
                }
        """
        ...

    async def fetch_product(self, url: str) -> Optional[Dict[str, Any]]:
        """从指定 URL 提取单个商品的结构化信息。

        这是给运营直接使用的核心场景：粘贴一个商品链接，返回结构化数据。
        默认返回 None（子类可选实现）。

        Args:
            url: 商品详情页 URL

        Returns:
            商品信息 dict（与 search 返回的商品结构一致），或 None 表示不支持。
        """
        return None
