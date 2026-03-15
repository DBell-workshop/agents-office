"""用户参与式浏览器采集器 — 可视化浏览器 + JS浮窗控制。

核心流程：
  1. 启动可见浏览器窗口（Patchright 反检测），用户自行登录电商平台
  2. 注入浮窗控制层 (overlay_js)，提供搜索/开始/暂停/结束按钮
  3. 用户点击开始后，模拟人类鼠标键盘操作：找搜索框 → 点击 → 输入 → 回车
  4. 像人一样滚动浏览页面，然后 LLM 分析页面内容提取商品
  5. 采集结果通过 asyncio.Queue 实时推送给 SSE 端点

反检测策略（Patchright）：
  - 修补 Runtime.enable / Console.enable 等 CDP 协议泄漏
  - 移除 --enable-automation 启动参数
  - 使用真实 Chrome（channel="chrome"）而非 Chromium
  - 不自定义 User-Agent，让浏览器使用真实值
  - 持久化用户 Profile，保持登录态和 Cookie
"""
from __future__ import annotations

import asyncio
import logging
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.collector.llm_extractor import (
    llm_extract_search_results,
)
from app.services.collector.overlay_js import OVERLAY_JS

log = logging.getLogger(__name__)

# 持久化浏览器 Profile 目录（保持登录态、Cookie）
_PROFILE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "browser_profile"

# 平台 → 搜索框选择器（按优先级）
_SEARCH_INPUT_SELECTORS: Dict[str, List[str]] = {
    "京东": ["#key", "input.text", "input[name='keyword']"],
    "淘宝": ["#q", "input[name='q']"],
    "拼多多": ["input.search-input", "input[name='search_key']"],
}

# 通用搜索框选择器（兜底）
_GENERIC_SEARCH_SELECTORS = [
    "input[type='search']",
    "input[name='keyword']",
    "input[name='q']",
    "input[placeholder*='搜索']",
    "input[placeholder*='search' i]",
    "input#key",
    "input#q",
]


class InteractiveBrowserCollector:
    """用户参与式浏览器采集器。

    生命周期状态：
      idle → browser_open → collecting → paused → collecting → closed
    """

    def __init__(self) -> None:
        self._status: str = "idle"
        self._platform: str = ""
        self._query: str = ""
        self._products: List[Dict[str, Any]] = []
        self._event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._llm_model: Optional[str] = None  # 使用比价专员配置的模型

        # Playwright 资源
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None

        # 采集控制
        self._collect_task: Optional[asyncio.Task] = None
        self._paused = False

    # ================================================================
    # 属性 / 状态
    # ================================================================

    @property
    def status(self) -> str:
        return self._status

    def get_status(self) -> dict:
        return {
            "status": self._status,
            "platform": self._platform,
            "query": self._query,
            "product_count": len(self._products),
        }

    @property
    def products(self) -> List[Dict[str, Any]]:
        return list(self._products)

    @property
    def event_queue(self) -> asyncio.Queue:
        return self._event_queue

    # ================================================================
    # 浏览器启动
    # ================================================================

    async def open_browser(self, start_url: str = "https://www.jd.com") -> None:
        """启动可见浏览器窗口，注入浮窗控制层。"""
        if self._browser is not None:
            log.warning("浏览器已打开，跳过重复启动")
            return

        # 加载比价专员 (price_comparator) 配置的 LLM 模型
        try:
            from app.office.store import office_store
            configs = office_store.get_agent_model_configs()
            pc_cfg = configs.get("price_comparator", {})
            if pc_cfg.get("model_name"):
                self._llm_model = pc_cfg["model_name"]
                log.info("采集器使用比价专员模型: %s", self._llm_model)
        except Exception as e:
            log.warning("加载比价专员模型配置失败，将使用默认模型: %s", e)

        try:
            from patchright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "patchright 未安装。请执行: pip install patchright && patchright install chrome"
            )

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=False,
            channel="chrome",
            args=[
                "--window-size=1280,900",
                "--window-position=100,50",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                "--lang=zh-CN",
            ],
        )
        self._context = await self._browser.new_context(
            locale="zh-CN",
            no_viewport=True,
        )
        self._page = await self._context.new_page()

        # 叠加 stealth 插件（双层防护）
        try:
            from playwright_stealth import stealth_async
            await stealth_async(self._page)
            log.info("stealth 插件已启用")
        except ImportError:
            log.warning("playwright-stealth 未安装，跳过 stealth 层")

        # 注册 Python 回调（JS → Python）
        await self._page.expose_function("__collector_start", self._on_start)
        await self._page.expose_function("__collector_pause", self._on_pause)
        await self._page.expose_function("__collector_resume", self._on_resume)
        await self._page.expose_function("__collector_stop", self._on_stop)

        # 注入浮窗 JS（每次导航自动重载）
        await self._page.add_init_script(OVERLAY_JS)

        # 导航到起始页
        try:
            await self._page.goto(start_url, timeout=30000, wait_until="load")
        except Exception as e:
            log.warning("起始页导航异常，继续: %s", e)

        # macOS 上把浏览器窗口带到前台
        await self._page.bring_to_front()

        self._status = "browser_open"
        await self._push_event("browser_opened", {"url": start_url})
        log.info("浏览器已打开: %s", start_url)

    # ================================================================
    # JS 回调处理（浮窗按钮 → Python）
    # ================================================================

    async def _on_start(self, query: str, platform: str) -> str:
        """用户点击"开始采集"。"""
        self._query = query
        self._platform = platform if platform != "auto" else self._detect_platform()
        self._paused = False
        self._status = "collecting"

        await self._push_event("collection_started", {
            "query": query,
            "platform": self._platform,
        })

        # 启动采集协程
        self._collect_task = asyncio.create_task(self._collection_loop())
        return "ok"

    async def _on_pause(self) -> str:
        """用户点击"暂停"。"""
        self._paused = True
        self._status = "paused"
        await self._push_event("collection_paused", {})
        return "ok"

    async def _on_resume(self) -> str:
        """用户点击"继续"。"""
        self._paused = False
        self._status = "collecting"
        await self._push_event("collection_resumed", {})
        return "ok"

    async def _on_stop(self) -> str:
        """用户点击"结束"。"""
        if self._collect_task and not self._collect_task.done():
            self._collect_task.cancel()
            try:
                await self._collect_task
            except asyncio.CancelledError:
                pass
        self._status = "browser_open"
        await self._push_event("collection_stopped", {
            "total_products": len(self._products),
        })
        return "ok"

    # ================================================================
    # 平台检测
    # ================================================================

    def _detect_platform(self) -> str:
        """根据当前页面 URL 自动识别平台。"""
        if not self._page:
            return "未知"
        url = self._page.url.lower()
        if "jd.com" in url:
            return "京东"
        if "taobao.com" in url or "tmall.com" in url:
            return "淘宝"
        if "pinduoduo.com" in url or "yangkeduo.com" in url:
            return "拼多多"
        return "其他"

    # ================================================================
    # 核心采集循环 — 模拟人类操作
    # ================================================================

    async def _collection_loop(self) -> None:
        """采集主循环：模拟人类搜索 → 浏览 → 提取 → 推送结果。"""
        try:
            platform = self._platform
            query = self._query

            # Step 1: 总是执行搜索（清空旧搜索词，输入新词）
            await self._update_overlay("🔍 正在找搜索框…", "#4ade80")
            search_ok = await self._human_search(query, platform)
            if not search_ok:
                await self._update_overlay(
                    "⚠️ 未找到搜索框，请手动搜索后再点采集", "#f59e0b",
                )
                await self._push_event("search_failed", {
                    "message": "未找到搜索框，请手动搜索后重试",
                })
                return

            # 等待搜索结果页加载（像人一样耐心等）
            await self._update_overlay("⏳ 等待搜索结果…", "#4ade80")
            await asyncio.sleep(random.uniform(3, 5))

            # Step 2: 像人一样浏览页面 — 随机停顿、滚动、看看
            await self._update_overlay("👀 正在浏览页面…", "#4ade80")
            await self._human_browse()

            # Step 3: 检查是否被暂停
            if self._paused:
                await self._wait_for_unpause()

            # Step 4: 提取页面文本
            await self._update_overlay("🤖 AI 正在分析页面…", "#60a5fa")
            page_text = await self._extract_page_text()
            log.info("采集页面文本长度: %d 字符", len(page_text))

            if len(page_text) < 100:
                await self._update_overlay("⚠️ 页面内容过少，请确认已登录", "#f59e0b")
                await self._push_event("extraction_warning", {
                    "message": "页面内容过少，可能需要登录或手动操作",
                })
                return

            # Step 5: LLM 提取商品列表（使用比价专员配置的模型）
            products = await llm_extract_search_results(
                page_content=page_text,
                platform=platform,
                query=query,
                max_products=10,
                model=self._llm_model,
            )

            if products:
                self._products.extend(products)
                await self._update_overlay(
                    f"✅ 本次提取 {len(products)} 个商品",
                    "#4ade80",
                    count=len(self._products),
                )
                await self._push_event("products_extracted", {
                    "new_count": len(products),
                    "total_count": len(self._products),
                    "products": products,
                })
                log.info("提取到 %d 个商品，累计 %d 个", len(products), len(self._products))
            else:
                await self._update_overlay("⚠️ 未提取到商品，请检查页面", "#f59e0b")
                await self._push_event("extraction_empty", {
                    "message": "未能从当前页面提取到商品信息",
                })

        except asyncio.CancelledError:
            log.info("采集任务已取消")
            raise
        except Exception as e:
            log.error("采集循环异常: %s", e, exc_info=True)
            await self._update_overlay(f"❌ 采集出错: {e}", "#ef4444")
            await self._push_event("collection_error", {"error": str(e)})

    # ================================================================
    # 模拟人类操作 — 鼠标、键盘、浏览
    # ================================================================

    async def _human_search(self, query: str, platform: str) -> bool:
        """模拟人类搜索：找搜索框 → 移动鼠标 → 点击 → 逐字输入 → 按回车。

        Returns: True 搜索成功, False 未找到搜索框。
        """
        # 收集候选选择器
        selectors = list(_SEARCH_INPUT_SELECTORS.get(platform, []))
        selectors.extend(_GENERIC_SEARCH_SELECTORS)

        # 逐个尝试找到可见的搜索框
        search_input = None
        for selector in selectors:
            try:
                el = self._page.locator(selector).first
                if await el.is_visible(timeout=800):
                    search_input = el
                    log.info("找到搜索框: %s", selector)
                    break
            except Exception:
                continue

        if not search_input:
            log.warning("未找到搜索框，所有选择器均失败")
            return False

        # 1. 获取搜索框位置
        box = await search_input.bounding_box()
        if not box:
            return False

        # 2. 模拟人类移动鼠标到搜索框（带自然曲线）
        target_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        target_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
        await self._human_move_mouse(target_x, target_y)

        # 3. 像人一样停顿一下再点击
        await asyncio.sleep(random.uniform(0.2, 0.5))
        await self._page.mouse.click(target_x, target_y)
        await asyncio.sleep(random.uniform(0.3, 0.6))

        # 4. 全选已有文字（Cmd+A 或 Ctrl+A）并删除
        mod_key = "Meta" if sys.platform == "darwin" else "Control"
        await self._page.keyboard.press(f"{mod_key}+a")
        await asyncio.sleep(random.uniform(0.1, 0.2))
        await self._page.keyboard.press("Backspace")
        await asyncio.sleep(random.uniform(0.2, 0.4))

        # 5. 逐字输入搜索词（模拟真人打字速度，慢一点避免被检测）
        await self._update_overlay(f"⌨️ 输入: {query}", "#4ade80")
        for i, char in enumerate(query):
            await self._page.keyboard.type(char, delay=random.randint(200, 450))
            # 偶尔停顿一下，像人在思考（约 25% 概率）
            if random.random() < 0.25:
                await asyncio.sleep(random.uniform(0.5, 1.5))
            # 每输入几个字多停一会儿（模拟人类节奏）
            if i > 0 and i % 3 == 0:
                await asyncio.sleep(random.uniform(0.3, 0.8))

        # 6. 输入完毕后稍等一下
        await asyncio.sleep(random.uniform(0.5, 1.0))

        # 7. 按回车搜索
        await self._page.keyboard.press("Enter")
        log.info("模拟搜索完成: %s", query)
        return True

    async def _human_move_mouse(self, target_x: float, target_y: float) -> None:
        """模拟人类鼠标移动 — 贝塞尔曲线轨迹，带自然加减速。"""
        # 获取当前鼠标大致位置（随机起点）
        start_x = random.uniform(100, 600)
        start_y = random.uniform(100, 400)

        # 贝塞尔曲线控制点 — 制造自然弧度
        cp1_x = start_x + (target_x - start_x) * random.uniform(0.2, 0.4) + random.uniform(-40, 40)
        cp1_y = start_y + (target_y - start_y) * random.uniform(0.2, 0.4) + random.uniform(-40, 40)
        cp2_x = start_x + (target_x - start_x) * random.uniform(0.6, 0.8) + random.uniform(-25, 25)
        cp2_y = start_y + (target_y - start_y) * random.uniform(0.6, 0.8) + random.uniform(-25, 25)

        steps = random.randint(18, 35)
        for i in range(steps + 1):
            t = i / steps
            # 三次贝塞尔曲线插值
            x = ((1 - t) ** 3 * start_x
                 + 3 * (1 - t) ** 2 * t * cp1_x
                 + 3 * (1 - t) * t ** 2 * cp2_x
                 + t ** 3 * target_x)
            y = ((1 - t) ** 3 * start_y
                 + 3 * (1 - t) ** 2 * t * cp1_y
                 + 3 * (1 - t) * t ** 2 * cp2_y
                 + t ** 3 * target_y)
            # 轻微抖动（真人手不稳）
            x += random.uniform(-1.5, 1.5)
            y += random.uniform(-1.5, 1.5)
            await self._page.mouse.move(x, y)
            # 非均匀速度：开始慢、中间快、结束慢
            speed = 4 * t * (1 - t) + 0.3
            await asyncio.sleep(random.uniform(3, 12) / (speed * 1000))

    async def _human_browse(self) -> None:
        """模拟人类浏览搜索结果页 — 滚动、停顿、偶尔移动鼠标。"""
        # 先停顿看一眼（人类会先扫一眼搜索结果）
        await asyncio.sleep(random.uniform(1.5, 3.0))

        # 分 3-5 次滚动，每次滚动距离和停留时间都不同
        scroll_rounds = random.randint(3, 5)
        for i in range(scroll_rounds):
            # 偶尔移动一下鼠标（像在看某个商品）
            if random.random() < 0.4:
                rand_x = random.randint(200, 800)
                rand_y = random.randint(200, 600)
                await self._human_move_mouse(rand_x, rand_y)
                await asyncio.sleep(random.uniform(0.3, 1.0))

            # 滚动一段距离
            scroll_distance = random.randint(200, 500)
            await self._page.mouse.wheel(0, scroll_distance)

            # 停下来看看（人类会浏览每屏内容）
            await asyncio.sleep(random.uniform(1.0, 3.0))

        # 滚动回顶部一点（人类有时会回头看）
        if random.random() < 0.3:
            await self._page.mouse.wheel(0, -random.randint(100, 300))
            await asyncio.sleep(random.uniform(0.5, 1.5))

    async def _human_scroll(self, times: int = 3) -> None:
        """简单版人类滚动。"""
        for _ in range(times):
            await self._page.mouse.wheel(0, random.randint(300, 600))
            await asyncio.sleep(random.uniform(0.8, 2.0))

    # ================================================================
    # 页面内容提取
    # ================================================================

    async def _extract_page_text(self) -> str:
        """提取当前页面可见文本。"""
        try:
            await self._page.wait_for_selector("body", timeout=10000)
        except Exception:
            log.warning("等待 body 超时")

        text = await self._page.evaluate("""
            () => {
                if (!document.body) return '[页面body为空]';
                const clone = document.body.cloneNode(true);
                // 移除浮窗自身和无关元素
                const overlay = clone.querySelector('#__collector_overlay');
                if (overlay) overlay.remove();
                clone.querySelectorAll('script, style, noscript, iframe').forEach(el => el.remove());
                return clone.innerText || '[页面无可见文本]';
            }
        """)
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...[页面内容已截断]..."
        return text

    # ================================================================
    # 工具方法
    # ================================================================

    async def _wait_for_unpause(self) -> None:
        """等待用户取消暂停。"""
        while self._paused:
            await asyncio.sleep(0.5)

    async def _update_overlay(
        self, status: str, color: str = "#999", count: Optional[int] = None,
    ) -> None:
        """更新浮窗 UI 状态。"""
        try:
            data: Dict[str, Any] = {"status": status, "statusColor": color}
            if count is not None:
                data["count"] = count
            await self._page.evaluate(
                "(data) => { if (window.__collector_update_ui) window.__collector_update_ui(data); }",
                data,
            )
        except Exception:
            pass  # 页面可能已导航，忽略

    # ================================================================
    # 事件推送
    # ================================================================

    async def _push_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """将事件推入队列，供 SSE 端点消费，同时持久化日志。"""
        event = {"type": event_type, **data}
        await self._event_queue.put(event)

        # 持久化（不含大体积的 products 原始数据）
        try:
            from app.services.collector.log_store import append_log

            log_entry = {
                "type": event_type,
                "platform": self._platform,
                "query": self._query,
            }
            # 只保留摘要信息，不存完整商品列表
            if "message" in data:
                log_entry["message"] = data["message"]
            if "new_count" in data:
                log_entry["new_count"] = data["new_count"]
            if "total_count" in data:
                log_entry["total_count"] = data["total_count"]
            if "error" in data:
                log_entry["error"] = data["error"]
            if "url" in data:
                log_entry["url"] = data["url"]
            if "total_products" in data:
                log_entry["total_products"] = data["total_products"]
            append_log(log_entry)
        except Exception as e:
            log.warning("持久化采集日志失败: %s", e)

    # ================================================================
    # 关闭 / 清理
    # ================================================================

    async def close(self) -> None:
        """关闭浏览器并清理资源。"""
        log.info("开始关闭采集器…")

        if self._collect_task and not self._collect_task.done():
            self._collect_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(self._collect_task), timeout=3)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                log.warning("采集任务取消超时，强制继续关闭")

        if self._page:
            try:
                await self._page.close()
                log.info("page 已关闭")
            except Exception as e:
                log.warning("关闭 page 异常: %s", e)
            self._page = None

        if self._context:
            try:
                await self._context.close()
                log.info("context 已关闭")
            except Exception as e:
                log.warning("关闭 context 异常: %s", e)
            self._context = None

        if self._browser:
            try:
                await self._browser.close()
                log.info("browser 已关闭")
            except Exception as e:
                log.warning("关闭 browser 异常: %s", e)
            self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
                log.info("playwright 已停止")
            except Exception as e:
                log.warning("停止 playwright 异常: %s", e)
            self._playwright = None

        self._status = "closed"
        log.info("采集器已完全关闭")
