"""
ZUGZWANG - Browser Automation Base
Playwright-based browser controller with retry logic, rate limiting,
user-agent rotation, and anti-detection measures.
"""

from __future__ import annotations
import asyncio
import random
import time
from typing import Optional, AsyncGenerator
from urllib.parse import urlparse

import sys
from ..core.config import config_manager, get_screenshots_dir
from ..core.logger import get_logger
from ..core.models import AppSettings, SourceType

logger = get_logger(__name__)

# Import guard - Playwright may not be installed in dev environment
try:
    from playwright.async_api import (
        async_playwright,
        Browser,
        BrowserContext,
        Page,
        TimeoutError as PlaywrightTimeout,
        Error as PlaywrightError,
    )
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Browser automation will be unavailable.")


class BrowserError(Exception):
    """Raised when browser automation encounters an unrecoverable error."""


class RateLimiter:
    """Token-bucket style rate limiter for polite scraping."""

    def __init__(self, min_delay: float = 1.5, max_delay: float = 4.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            # If the last request was already scheduled in the future, base our delay on that
            base_time = max(now, self._last_request)
            delay = random.uniform(self.min_delay, self.max_delay)
            self._last_request = base_time + delay
            sleep_time = self._last_request - now
            
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)


class BrowserSession:
    """
    Managed Playwright browser session.
    Encapsulates browser lifecycle with anti-detection, retry logic,
    and configurable rate limiting.
    """

    def __init__(
        self,
        settings: AppSettings,
        job_id: Optional[str] = None,
        source_type: Optional[SourceType] = None,
    ):
        self.settings = settings
        self.job_id = job_id
        self.source_type = source_type
        self._playwright = None
        self._browser: Optional["Browser"] = None
        self._context: Optional["BrowserContext"] = None
        self.rate_limiter = RateLimiter(
            settings.default_delay_min,
            settings.default_delay_max,
        )
        self._screenshot_index = 0
        self._blocked_resource_types = self._build_blocked_resource_types()
        # Serializes concurrent browser-tab operations (new_page / navigate fallbacks)
        self.page_lock = asyncio.Lock()

    def _build_blocked_resource_types(self) -> set[str]:
        if self.source_type == SourceType.JOBSUCHE:
            return {"media"}
        if self.source_type == SourceType.GOOGLE_MAPS:
            return {"media", "font"}
        return {"image", "media", "font"}

    async def start(self) -> None:
        if not PLAYWRIGHT_AVAILABLE:
            raise BrowserError(
                "Playwright is not installed.\n"
                "Run: pip install playwright && playwright install chromium"
            )

        # Configure browser path BEFORE launching.
        # Critical for frozen (.exe) builds: sets PLAYWRIGHT_BROWSERS_PATH
        # to the 'browsers' folder next to ZUGZWANG.exe so Playwright
        # can find the Chromium binaries that were installed there.
        from .browser_installer import configure_browsers_path, is_chromium_installed
        configure_browsers_path()

        engine = self.settings.browser_engine
        
        engine = self.settings.browser_engine
        
        # Validation
        if engine in ["chromium", "chrome", "msedge"] and not self.settings.browser_channel:
             # If using bundled chromium, check if installed
             if engine == "chromium" and not is_chromium_installed():
                raise BrowserError(
                    "Chromium browser is not installed.\n\n"
                    "Go to the Dashboard and click 'Install Browser', or run:\n"
                    "  playwright install chromium"
                )

        logger.info(f"[{self.job_id}] Starting browser session (engine={engine}, headless={self.settings.default_headless})")
        self._playwright = await async_playwright().start()



        if not self._browser:
            logger.info(f"[{self.job_id}] Launching local {engine}...")
            # Handle local browser launch (fallback cases or direct selection)
            launch_kwargs = {
                "headless": self.settings.default_headless,
                "args": [
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-background-networking",
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                    "--disable-features=Translate,BackForwardCache",
                    "--disable-extensions",
                    "--mute-audio",
                    "--start-maximized",
                    # RAM Optimization - Unified & Safer
                    "--js-flags='--max-old-space-size=512'", # Limit JS heap
                    "--disable-dev-shm-usage",
                    "--disable-setuid-sandbox" if sys.platform != "win32" else "",
                    "--no-zygote" if sys.platform != "win32" else "",
                    "--single-process" if sys.platform != "win32" else "", # Experimental/Unstable on Win
                ],
            }
            # Clean up empty strings
            launch_kwargs["args"] = [a for a in launch_kwargs["args"] if a]

            if engine in ["chrome", "msedge"]:
                launch_kwargs["channel"] = engine
            elif self.settings.browser_channel:
                launch_kwargs["channel"] = self.settings.browser_channel

            self._browser = await self._playwright.chromium.launch(**launch_kwargs)
            logger.info(f"[{self.job_id}] Local {engine} launched.")

        user_agent = random.choice(self.settings.user_agents)
        
        # Proxy Rotation logic
        proxy_config = None
        if self.settings.proxy_enabled and self.settings.proxies:
            proxy_url = random.choice(self.settings.proxies)
            proxy_config = {"server": proxy_url}
            logger.info(f"[{self.job_id}] Using proxy: {proxy_url}")

        context_kwargs = {
            "user_agent": user_agent,
            "proxy": proxy_config,
            "locale": "de-DE",
            "timezone_id": "Europe/Berlin",
            "java_script_enabled": True,
            "accept_downloads": False,
            "extra_http_headers": {
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        }

        # Handle viewport and scale factor consistency
        if not self.settings.default_headless:
            context_kwargs["no_viewport"] = True
        else:
            # Only use scale factor if we have a viewport (required by Playwright)
            context_kwargs["device_scale_factor"] = 1



        context_kwargs["ignore_https_errors"] = True
        
        logger.debug(f"[{self.job_id}] Creating browser context...")
        self._context = await self._browser.new_context(**context_kwargs)
        await self._context.route("**/*", self._route_request)

        # Anti-detection: override navigator.webdriver
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            window.chrome = {runtime: {}};
        """)

        if not self._context:
             raise BrowserError("Failed to initialize browser context.")

        logger.info(f"[{self.job_id}] Browser session ready with UA: {user_agent[:50]}...")

    async def stop(self) -> None:
        """Gracefully close all browser resources."""
        try:
            if self._context:
                await self._context.close()
                self._context = None
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            logger.debug(f"[{self.job_id}] Browser session closed successfully.")
        except Exception as e:
            logger.warning(f"[{self.job_id}] Error closing browser: {e}")
        finally:
            self._context = None
            self._browser = None
            self._playwright = None

    async def _route_request(self, route, request) -> None:
        """Skip heavyweight assets that are not needed for data extraction."""
        if request.resource_type in self._blocked_resource_types:
            await route.abort()
            return
        await route.continue_()

    async def new_page(self) -> "Page":
        if not self._context:
            raise BrowserError("Browser session not started.")
        page = await self._context.new_page()
        page.set_default_timeout(30_000)  # 30s (reduced from 120s for faster failure recovery)
        return page

    async def navigate(
        self,
        page: "Page",
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: int = 20000,
        retries: int = 3,
        ignore_rate_limit: bool = False,
    ) -> bool:
        """Navigate to URL with retry logic. Returns True on success."""
        if not ignore_rate_limit:
            await self.rate_limiter.wait()
        for attempt in range(1, retries + 1):
            try:
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                logger.debug(f"[{self.job_id}] Navigated to {url} (attempt {attempt})")
                return True
            except PlaywrightTimeout:
                logger.warning(f"[{self.job_id}] Timeout on {url} (attempt {attempt}/{retries})")
                if attempt < retries:
                    await asyncio.sleep(attempt * 2)
            except PlaywrightError as e:
                logger.warning(f"[{self.job_id}] Navigation error {url}: {e} (attempt {attempt}/{retries})")
                if attempt < retries:
                    await asyncio.sleep(attempt * 2)
        return False

    async def get_page_content(self, page: "Page") -> str:
        """Get full page HTML content."""
        try:
            return await page.content()
        except Exception as e:
            logger.warning(f"[{self.job_id}] Could not get page content: {e}")
            return ""

    async def get_markdown(self, page: "Page") -> str:
        """
        Get page content as Markdown.
        """
        return await self.get_page_content(page)

    async def fetch_url_content_fast(
        self, 
        url: str, 
        timeout: int = 10000, 
        ignore_rate_limit: bool = False
    ) -> str:
        """Fetch HTML through the browser context request client.
        Useful for secondary pages where driving the live browser UI is unnecessary.
        """
        if not self._context:
            return ""
        try:
            if not ignore_rate_limit:
                await self.rate_limiter.wait()
            response = await self._context.request.get(url, timeout=timeout)
            if not response.ok:
                return ""
            content_type = (response.headers.get("content-type") or "").lower()
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                return ""
            return await response.text()
        except Exception as e:
            logger.debug(f"[{self.job_id}] Fast fetch failed for {url}: {e}")
            return ""

    async def screenshot_on_failure(self, page: "Page", context: str = "") -> Optional[str]:
        """Capture screenshot for debugging failed pages."""
        if not self.settings.debug_screenshots:
            return None
        try:
            self._screenshot_index += 1
            path = get_screenshots_dir() / f"fail_{self.job_id}_{self._screenshot_index:03d}.png"
            await page.screenshot(path=str(path), full_page=True)
            logger.debug(f"[{self.job_id}] Screenshot saved: {path} ({context})")
            return str(path)
        except Exception:
            return None

    async def scroll_to_bottom(self, page: "Page", pause: float = 1.5, max_scrolls: int = 50) -> None:
        """Scroll page to bottom to trigger lazy loading."""
        prev_height = 0
        for _ in range(max_scrolls):
            height = await page.evaluate("document.body.scrollHeight")
            if height == prev_height:
                break
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(pause)
            prev_height = height

    def is_blacklisted(self, url: str) -> bool:
        """Check if a domain is in the blacklist."""
        domain = urlparse(url).netloc.lower().lstrip("www.")
        return domain in [d.lower().lstrip("www.") for d in self.settings.blacklisted_domains]

    def is_whitelisted(self, url: str) -> bool:
        """Check if whitelist is active and URL matches."""
        if not self.settings.whitelisted_domains:
            return True
        domain = urlparse(url).netloc.lower().lstrip("www.")
        return domain in [d.lower().lstrip("www.") for d in self.settings.whitelisted_domains]
