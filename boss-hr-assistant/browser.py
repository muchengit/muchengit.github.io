"""浏览器管理 — 通过 CDP 连接已登录的 Chrome 浏览器.

基于 boss-zhipin-mcp 项目的 browser.py 改造，
适配 Windows 环境和 HR 聊天场景。
"""
import json
import os
import asyncio
import random
import logging
import subprocess
import platform

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import (
    COOKIES_DIR, COOKIES_FILE,
    MIN_DELAY, MAX_DELAY, BOSS_BASE_URL, BOSS_CHAT_URL
)

log = logging.getLogger("boss-hr-browser")

# CDP 连接配置
CDP_URL = os.getenv("BOSS_CDP_URL", "http://localhost:9222")
CDP_DETECT_PORTS = [9222, 9229, 19222]


class BossBrowser:
    """通过 CDP 连接已登录的 Chrome，操作 Boss 直聘."""

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def launch(self):
        """连接 Chrome，支持多种策略自动回退."""
        self._playwright = await async_playwright().start()

        # 策略1: 尝试配置的 CDP URL
        if await self._try_cdp_connect(CDP_URL):
            log.info(f"已通过 CDP 连接: {CDP_URL}")
            return

        # 策略2: 自动检测常见端口
        for port in CDP_DETECT_PORTS:
            url = f"http://localhost:{port}"
            if url == CDP_URL:
                continue
            if await self._try_cdp_connect(url):
                log.info(f"自动检测到 Chrome 端口: {port}")
                return

        # 策略3: 启动系统 Chrome 并连接
        log.info("未检测到运行中的 Chrome，正在启动系统 Chrome")
        launched_port = await self._launch_system_chrome()
        if launched_port:
            cdp_url = f"http://localhost:{launched_port}"
            if await self._try_cdp_connect(cdp_url):
                log.info(f"已连接到系统 Chrome 端口: {launched_port}")
                return

        # 策略4: 回退到独立 Chromium
        log.info("系统 Chrome 启动失败，回退到独立 Chromium")
        await self._launch_new_browser()

    async def _launch_system_chrome(self) -> int | None:
        """启动系统 Chrome 并开启调试端口."""
        port = 9222
        system = platform.system()

        if system == "Darwin":
            chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        elif system == "Linux":
            chrome_path = "google-chrome"
        else:
            # Windows — 尝试多个常见路径
            possible_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            ]
            chrome_path = None
            for p in possible_paths:
                if os.path.exists(p):
                    chrome_path = p
                    break

        if not chrome_path:
            log.warning("未找到 Chrome 浏览器")
            return None

        # 使用独立的用户数据目录
        profile_dir = os.path.join(os.path.dirname(__file__), "chrome-profile")

        try:
            subprocess.Popen(
                [chrome_path, f"--remote-debugging-port={port}",
                 f"--user-data-dir={profile_dir}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # 等待 Chrome 启动
            import urllib.request
            for _ in range(15):
                await asyncio.sleep(1)
                try:
                    urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
                    return port
                except Exception:
                    continue
        except FileNotFoundError:
            log.warning(f"Chrome 未找到: {chrome_path}")
        except Exception as e:
            log.warning(f"启动 Chrome 失败: {e}")
        return None

    async def _try_cdp_connect(self, url: str) -> bool:
        """尝试通过 CDP 连接 Chrome."""
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(
                url, timeout=5000
            )
            contexts = self._browser.contexts
            if contexts:
                self._context = contexts[0]
                pages = self._context.pages
                self._page = pages[0] if pages else await self._context.new_page()
            else:
                self._context = await self._browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    locale="zh-CN",
                )
                self._page = await self._context.new_page()
            return True
        except Exception:
            return False

    async def _launch_new_browser(self):
        """回退方案: 启动独立 Chromium."""
        self._browser = await self._playwright.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        await self._load_cookies()
        self._page = await self._context.new_page()

    async def close(self):
        """断开连接（不关闭用户的 Chrome）."""
        if self._context:
            await self._save_cookies()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._context = None
        self._page = None

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("浏览器未启动，请先调用 launch()")
        return self._page

    @property
    def is_alive(self) -> bool:
        """检查浏览器是否仍然连接."""
        try:
            return self._browser is not None and self._browser.is_connected()
        except Exception:
            return False

    async def _load_cookies(self):
        """从文件加载 Cookie."""
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, "r") as f:
                cookies = json.load(f)
            await self._context.add_cookies(cookies)

    async def _save_cookies(self):
        """保存 Cookie 到文件."""
        os.makedirs(COOKIES_DIR, exist_ok=True)
        try:
            cookies = await self._context.cookies()
            with open(COOKIES_FILE, "w") as f:
                json.dump(cookies, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    async def is_logged_in(self) -> bool:
        """检查是否已登录 Boss 直聘."""
        try:
            current_url = self.page.url
            if "zhipin.com" in current_url:
                return await self._check_current_page_logged_in()
        except Exception:
            pass
        await self.page.goto(BOSS_BASE_URL, wait_until="networkidle")
        await asyncio.sleep(3)
        return await self._check_current_page_logged_in()

    async def _check_current_page_logged_in(self) -> bool:
        """从当前页面检查登录状态（不导航离开）."""
        current_url = self.page.url
        if "login" in current_url or "/web/user" in current_url or "bticket" in current_url:
            body_class = await self.page.evaluate("document.body.className || ''")
            if "login" in body_class:
                return False
        if "/web/boss/" in current_url or "/web/chat/" in current_url:
            return True
        try:
            logged_in = await self.page.query_selector(
                ".user-nav, .btn-post-job, .nav-figure, .menu-list"
            )
            return logged_in is not None
        except Exception:
            return False

    async def check_and_screenshot_verification(self) -> dict | None:
        """检查是否有安全验证弹窗."""
        try:
            has_verify = await self.page.evaluate("""() => {
                const text = document.body.innerText || '';
                const selectors = [
                    '.verify-wrap', '.captcha', '.slider-verify',
                    '[class*="verify"]', '[class*="captcha"]',
                    '.boss-popup__wrapper'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.offsetWidth > 0) return true;
                }
                return text.includes('安全验证') || text.includes('滑动验证')
                    || text.includes('请完成验证');
            }""")
            if has_verify:
                screenshot_path = os.path.join(
                    os.path.dirname(__file__), "screenshot_verification.png"
                )
                await self.page.screenshot(path=screenshot_path)
                return {
                    "needs_verification": True,
                    "screenshot": screenshot_path,
                    "message": "检测到安全验证，请在浏览器中手动完成验证后告知",
                }
        except Exception:
            pass
        return None

    async def login(self) -> dict:
        """导航到登录页，等待用户手动登录."""
        await self.page.goto(
            f"{BOSS_BASE_URL}/web/user/?ka=header-login",
            wait_until="domcontentloaded"
        )
        for _ in range(90):
            await asyncio.sleep(2)
            if await self._check_current_page_logged_in():
                await self._save_cookies()
                return {"status": "success", "message": "登录成功，Cookie 已保存"}
        return {"status": "timeout", "message": "登录超时（3分钟），请在浏览器中完成登录后重试"}

    async def random_delay(self):
        """随机延迟，模拟人类操作."""
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        await asyncio.sleep(delay)
