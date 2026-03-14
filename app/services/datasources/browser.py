"""浏览器采集数据源 — LLM 驱动的通用网页商品信息提取。

核心思想：
  - Playwright 控制浏览器，模拟人类浏览行为
  - LLM 负责"看"页面内容并提取结构化商品数据
  - 不包含任何网站特定的 DOM/CSS 选择器，完全通用
  - 平台配置（搜索URL模板等）通过 YAML 管理，代码零耦合
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import yaml

from app.services.datasources.base import ProductDataSource

log = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "platform_configs.yaml"

# User-Agent 池，随机轮换
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


# ============================================================
# LLM 提取 Prompt（通用，不含任何网站特定逻辑）
# ============================================================

_EXTRACT_SEARCH_RESULTS_PROMPT = """\
你是一位网页内容分析专家。以下是一个电商平台搜索结果页面的文本内容。
请从中提取商品列表信息。

## 平台信息
- 平台名称: {platform}
- 搜索关键词: {query}
{hints_section}

## 页面内容

{page_content}

## 提取要求

从页面中提取最多 {max_products} 个与搜索关键词最相关的商品，每个商品包含以下字段（尽可能提取，缺失的字段留空）：

请严格返回 JSON 数组格式（不要包含 markdown 代码块标记）：
[
  {{
    "name": "商品完整名称",
    "brand": "品牌名（从商品名称或店铺信息推断）",
    "price": 价格数值（当前售价，数字类型），
    "original_price": 原价数值（划线价，没有则与 price 相同），
    "promotions": ["促销信息1", "促销信息2"],
    "rating": 评分数值（0-5，没有则 null），
    "review_count": 评价数量（整数，没有则 0），
    "url": "商品详情页链接（如果页面中能找到）",
    "image_url": "商品图片链接（如果能找到）",
    "specs": {{"规格名1": "值1", "规格名2": "值2"}}
  }}
]

如果页面内容不包含商品信息（例如验证码页面、登录页面），请返回空数组 []。"""


_EXTRACT_PRODUCT_DETAIL_PROMPT = """\
你是一位网页内容分析专家。以下是一个电商商品详情页面的文本内容。
请从中提取该商品的详细信息。

## 页面内容

{page_content}

## 提取要求

请提取该商品的完整信息，严格返回 JSON 格式（不要包含 markdown 代码块标记）：
{{
  "name": "商品完整名称",
  "brand": "品牌名",
  "price": 当前售价（数字类型），
  "original_price": 原价/划线价（数字类型，没有则与 price 相同），
  "promotions": ["促销活动1", "促销活动2"],
  "rating": 评分（0-5，没有则 null），
  "review_count": 评价数量（整数，没有则 0），
  "url": "当前页面URL",
  "image_url": "商品主图链接",
  "specs": {{"规格名1": "值1", "规格名2": "值2"}},
  "platform": "判断这是哪个电商平台（京东/淘宝/拼多多/其他）",
  "shop_name": "店铺名称（如果能找到）"
}}

如果页面内容不是商品页面（例如验证码、登录页），请返回 {{"error": "原因描述"}}。"""


def _load_config() -> Dict[str, Any]:
    """加载平台采集配置。"""
    if not _CONFIG_PATH.exists():
        log.warning("平台配置文件不存在: %s", _CONFIG_PATH)
        return {"platforms": {}, "browser": {}}
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"platforms": {}, "browser": {}}


def _clean_llm_json(content: str) -> str:
    """清理 LLM 返回中可能包含的 markdown 代码块标记。"""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()


def _generate_product_id(platform: str, name: str, url: str) -> str:
    """根据平台+商品名+URL 生成稳定的 product_id。"""
    prefix_map = {"京东": "jd", "淘宝": "tb", "拼多多": "pdd"}
    prefix = prefix_map.get(platform, "web")
    hash_input = f"{platform}:{name}:{url}"
    short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
    return f"{prefix}_{short_hash}"


class BrowserDataSource(ProductDataSource):
    """基于 Playwright + LLM 的通用网页商品采集数据源。

    工作流程：
      1. Playwright 打开页面（搜索页或商品详情页）
      2. 模拟人类行为（等待、滚动、随机延迟）
      3. 提取页面可见文本（或截图）
      4. 将文本/截图发给 LLM，让 LLM "看懂"页面并提取结构化数据
      5. 返回标准化商品信息
    """

    def __init__(self, config_path: Optional[Path] = None):
        self._config = _load_config() if config_path is None else self._load_custom(config_path)
        self._browser = None
        self._context = None

    @staticmethod
    def _load_custom(path: Path) -> Dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {"platforms": {}, "browser": {}}

    @property
    def _browser_config(self) -> Dict[str, Any]:
        return self._config.get("browser", {})

    def _get_enabled_platforms(self) -> Dict[str, Dict[str, Any]]:
        """返回所有启用的平台配置。"""
        platforms = self._config.get("platforms", {})
        return {name: cfg for name, cfg in platforms.items() if cfg.get("enabled", True)}

    # ----------------------------------------------------------------
    # 浏览器生命周期
    # ----------------------------------------------------------------

    async def _ensure_browser(self):
        """懒初始化浏览器实例。"""
        if self._browser is not None:
            return

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "playwright 未安装。请执行: pip install playwright && python -m playwright install chromium"
            )

        self._playwright = await async_playwright().start()
        bcfg = self._browser_config
        self._browser = await self._playwright.chromium.launch(
            headless=bcfg.get("headless", True),
        )
        viewport = bcfg.get("viewport", {})
        self._context = await self._browser.new_context(
            viewport={
                "width": viewport.get("width", 1280),
                "height": viewport.get("height", 800),
            },
            user_agent=random.choice(_USER_AGENTS),
        )

    async def close(self):
        """关闭浏览器资源。"""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if hasattr(self, "_playwright") and self._playwright:
            await self._playwright.stop()
            self._playwright = None

    # ----------------------------------------------------------------
    # 人类行为模拟
    # ----------------------------------------------------------------

    async def _human_delay(self):
        """随机延迟，模拟人类操作节奏。"""
        delay_cfg = self._browser_config.get("delay", {})
        min_delay = delay_cfg.get("min", 2)
        max_delay = delay_cfg.get("max", 5)
        await asyncio.sleep(random.uniform(min_delay, max_delay))

    async def _human_scroll(self, page, times: int = 2):
        """模拟人类滚动页面，触发懒加载。"""
        for _ in range(times):
            scroll_distance = random.randint(300, 600)
            await page.mouse.wheel(0, scroll_distance)
            await asyncio.sleep(random.uniform(0.5, 1.5))

    # ----------------------------------------------------------------
    # 页面内容提取
    # ----------------------------------------------------------------

    async def _extract_page_text(self, page) -> str:
        """提取页面可见文本内容（text 模式）。"""
        # 获取页面主体文本，过滤掉脚本和样式
        text = await page.evaluate("""
            () => {
                // 移除 script 和 style 标签的影响
                const clone = document.body.cloneNode(true);
                clone.querySelectorAll('script, style, noscript, iframe').forEach(el => el.remove());
                return clone.innerText;
            }
        """)
        # 截断过长文本以控制 token 消耗
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...[页面内容已截断]..."
        return text

    async def _extract_page_screenshot(self, page) -> bytes:
        """截取页面截图（screenshot 模式）。"""
        return await page.screenshot(full_page=False)

    # ----------------------------------------------------------------
    # LLM 页面理解
    # ----------------------------------------------------------------

    async def _llm_extract_search_results(
        self,
        page_content: str,
        platform: str,
        query: str,
        hints: str = "",
        max_products: int = 5,
    ) -> List[Dict[str, Any]]:
        """让 LLM 从搜索结果页面文本中提取商品列表。"""
        from app.services.llm_service import async_chat_completion

        hints_section = f"- 平台特征提示: {hints}" if hints else ""
        prompt = _EXTRACT_SEARCH_RESULTS_PROMPT.format(
            platform=platform,
            query=query,
            hints_section=hints_section,
            page_content=page_content,
            max_products=max_products,
        )

        try:
            result = await async_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2048,
            )
            content = _clean_llm_json(result.get("content", ""))
            products = json.loads(content)
            if not isinstance(products, list):
                return []

            # 标准化字段 + 生成 product_id
            for p in products:
                p["platform"] = platform
                if "product_id" not in p or not p["product_id"]:
                    p["product_id"] = _generate_product_id(
                        platform, p.get("name", ""), p.get("url", "")
                    )
                # 确保数值字段类型正确
                for field in ("price", "original_price", "rating"):
                    if field in p and p[field] is not None:
                        try:
                            p[field] = float(p[field])
                        except (ValueError, TypeError):
                            p[field] = 0.0
                if "review_count" in p:
                    try:
                        p["review_count"] = int(p["review_count"])
                    except (ValueError, TypeError):
                        p["review_count"] = 0

            return products

        except (json.JSONDecodeError, Exception) as e:
            log.warning("LLM 提取搜索结果失败 (%s): %s", platform, e)
            return []

    async def _llm_extract_product_detail(
        self, page_content: str
    ) -> Optional[Dict[str, Any]]:
        """让 LLM 从商品详情页面文本中提取结构化信息。"""
        from app.services.llm_service import async_chat_completion

        prompt = _EXTRACT_PRODUCT_DETAIL_PROMPT.format(page_content=page_content)

        try:
            result = await async_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1024,
            )
            content = _clean_llm_json(result.get("content", ""))
            product = json.loads(content)

            if "error" in product:
                log.warning("LLM 判断页面非商品页: %s", product["error"])
                return None

            # 生成 product_id
            platform = product.get("platform", "未知")
            product["product_id"] = _generate_product_id(
                platform, product.get("name", ""), product.get("url", "")
            )
            return product

        except (json.JSONDecodeError, Exception) as e:
            log.warning("LLM 提取商品详情失败: %s", e)
            return None

    # ----------------------------------------------------------------
    # 核心采集方法
    # ----------------------------------------------------------------

    async def _browse_and_extract(
        self,
        url: str,
        platform: str,
        query: str,
        platform_cfg: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """打开搜索页面 → 模拟浏览 → LLM 提取商品列表。"""
        await self._ensure_browser()

        page = await self._context.new_page()
        try:
            timeout = self._browser_config.get("page_timeout", 30) * 1000
            await page.goto(url, timeout=timeout, wait_until="domcontentloaded")

            # 等待页面动态内容加载
            wait_time = platform_cfg.get("page_load_wait", 3)
            await asyncio.sleep(wait_time)

            # 模拟人类滚动
            scroll_times = platform_cfg.get("scroll_times", 2)
            await self._human_scroll(page, scroll_times)

            # 提取页面内容
            page_content = await self._extract_page_text(page)

            max_products = self._browser_config.get("max_products_per_platform", 5)
            hints = platform_cfg.get("hints", "")

            products = await self._llm_extract_search_results(
                page_content=page_content,
                platform=platform,
                query=query,
                hints=hints,
                max_products=max_products,
            )
            return products

        except Exception as e:
            log.error("浏览器采集失败 (%s, %s): %s", platform, url, e)
            return []
        finally:
            await page.close()

    async def _browse_product_page(self, url: str) -> Optional[Dict[str, Any]]:
        """打开商品详情页 → 模拟浏览 → LLM 提取商品信息。"""
        await self._ensure_browser()

        page = await self._context.new_page()
        try:
            timeout = self._browser_config.get("page_timeout", 30) * 1000
            await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            await self._human_scroll(page, 2)

            page_content = await self._extract_page_text(page)
            product = await self._llm_extract_product_detail(page_content)

            if product and not product.get("url"):
                product["url"] = url

            return product

        except Exception as e:
            log.error("商品详情页采集失败 (%s): %s", url, e)
            return None
        finally:
            await page.close()

    # ----------------------------------------------------------------
    # ProductDataSource 接口实现
    # ----------------------------------------------------------------

    async def search(
        self,
        query: str,
        platforms: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """在多个电商平台搜索商品（通过浏览器 + LLM 提取）。"""
        enabled_platforms = self._get_enabled_platforms()

        # 过滤用户指定的平台
        if platforms:
            enabled_platforms = {
                name: cfg
                for name, cfg in enabled_platforms.items()
                if name in platforms
            }

        if not enabled_platforms:
            log.warning("没有可用的采集平台配置")
            return {}

        results: Dict[str, List[Dict[str, Any]]] = {}

        for platform_name, platform_cfg in enabled_platforms.items():
            url_template = platform_cfg.get("search_url_template", "")
            if not url_template:
                continue

            search_url = url_template.format(query=quote_plus(query))
            log.info("浏览器采集: %s → %s", platform_name, search_url)

            products = await self._browse_and_extract(
                url=search_url,
                platform=platform_name,
                query=query,
                platform_cfg=platform_cfg,
            )

            if products:
                results[platform_name] = products

            # 平台间随机延迟
            await self._human_delay()

        return results

    async def fetch_product(self, url: str) -> Optional[Dict[str, Any]]:
        """从指定 URL 提取单个商品信息（运营直接粘贴链接的场景）。"""
        log.info("浏览器采集商品详情: %s", url)
        return await self._browse_product_page(url)
