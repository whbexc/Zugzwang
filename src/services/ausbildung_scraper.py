"""
ZUGZWANG - Ausbildung.de Scraper
Lightweight scraper using in-page fetch() for detail pages.
ONE browser page stays open for the entire session.
All detail pages are fetched via JS fetch() — no new tabs opened.
HTML is parsed with BeautifulSoup in Python memory.
"""

from __future__ import annotations
import asyncio
import re
from typing import AsyncGenerator
from urllib.parse import quote

from bs4 import BeautifulSoup

from .browser import BrowserSession
from ..core.logger import get_logger
from ..core.models import LeadRecord, SearchConfig, SourceType

logger = get_logger(__name__)

SEARCH_URL = "https://www.ausbildung.de/suche/"


def _build_search_url(title: str, city: str, radius: int) -> str:
    """Build a direct search URL with query and radius params."""
    query = f"{title}|{city}" if city else title
    return f"{SEARCH_URL}?search={quote(query)}&radius={radius}"


class AusbildungScraper:
    """
    Scrapes ausbildung.de job listings.

    Architecture:
    - One Playwright page is opened for the entire session.
    - Detail pages are fetched via in-page JS fetch() — no new tabs.
    - HTML is parsed with BeautifulSoup in Python memory.
    - Resource blocking (images, fonts) reduces memory and network overhead.
    - Uses URL-based pagination (&page=N) for reliable multi-page scraping.
    """

    def __init__(
        self,
        session: BrowserSession,
        config: SearchConfig,
        job_id: str,
    ):
        self.session = session
        self.config = config
        self.job_id = job_id
        self._cancelled = False
        self._paused = False

    def cancel(self) -> None:
        self._cancelled = True

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    # ──────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────

    async def scrape(self) -> AsyncGenerator[LeadRecord, None]:
        """Async generator that yields LeadRecord objects one by one."""
        page = await self.session.new_page()
        try:
            # Block heavy assets — faster page loads, lower RAM
            await page.route(
                "**/*.{png,jpg,jpeg,gif,svg,woff,woff2}",
                lambda route, _req: route.abort(),
            )

            # ── Step 1: Navigate to search URL with radius ──
            url = _build_search_url(
                self.config.job_title,
                self.config.city or "",
                self.config.radius,
            )
            logger.info(f"[{self.job_id}] Navigating to {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # Dismiss cookie consent if present
            await self._dismiss_cookies(page)
            await asyncio.sleep(0.3)

            logger.info(
                f"[{self.job_id}] Search submitted: "
                f'"{self.config.job_title}" in "{self.config.city or "all"}" '
                f"(radius={self.config.radius}km)"
            )

            # Track all visited detail URLs (prevents re-fetching)
            processed_urls: set[str] = set()
            yielded_count = 0
            page_num = 1

            # ── Main pagination loop ──
            while not self._cancelled:
                # Pause / cancel check
                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.1)
                if self._cancelled:
                    break

                # ── Step 2: Harvest card links from current DOM ──
                all_links: list[str] = await page.evaluate(
                    """() => {
                        const cards = document.querySelectorAll('a[href*="/stellen/"]');
                        const seen = new Set();
                        const results = [];
                        for (const a of cards) {
                            const href = a.href;
                            if (
                                href
                                && !seen.has(href)
                                && href.includes('/stellen/')
                                && !href.includes('/suche/')
                            ) {
                                seen.add(href);
                                results.push(href);
                            }
                        }
                        return results;
                    }"""
                )

                # Only process URLs we haven't visited yet
                new_links = [u for u in all_links if u not in processed_urls]
                logger.info(
                    f"[{self.job_id}] Page {page_num}: found {len(all_links)} card(s), "
                    f"{len(new_links)} new"
                )

                if not new_links:
                    if not processed_urls:
                        logger.info(f"[{self.job_id}] No results found for this search.")
                    else:
                        logger.info(
                            f"[{self.job_id}] No more results — pagination complete "
                            f"({len(processed_urls)} cards total)."
                        )
                    break

                # ── Step 3: Fetch + parse + yield detail pages in batches ──
                BATCH_SIZE = 5
                for i in range(0, len(new_links), BATCH_SIZE):
                    while self._paused and not self._cancelled:
                        await asyncio.sleep(0.1)
                    if self._cancelled:
                        break

                    batch = new_links[i : i + BATCH_SIZE]

                    # Mark ALL batch URLs as processed BEFORE fetching
                    for link in batch:
                        processed_urls.add(link)

                    tasks = [self._fetch_and_parse(page, link) for link in batch]
                    batch_results = await asyncio.gather(*tasks)

                    for lead in batch_results:
                        while self._paused and not self._cancelled:
                            await asyncio.sleep(0.1)
                        if self._cancelled:
                            break

                        if lead:
                            if yielded_count >= self.config.max_results:
                                break

                            # Skip leads without email when email scraping is enabled
                            if self.config.scrape_emails and not lead.email:
                                logger.debug(
                                    f"[{self.job_id}] Skipping lead (no email): "
                                    f"{lead.company_name}"
                                )
                                continue

                            yield lead
                            yielded_count += 1

                if self._cancelled:
                    break

                if yielded_count >= self.config.max_results:
                    logger.info(f"[{self.job_id}] Reached max results ({self.config.max_results}).")
                    break

                # Pause check before pagination
                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.1)
                if self._cancelled:
                    break

                # ── Step 4: Scroll to bottom to trigger infinite scroll for next page ──
                # (SPA ignores &page=N and often lazy-loads instead of showing a button)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(0.5)
                await self._dismiss_cookies(page)

                prev_count = len(all_links)

                # Wait for new cards to appear in DOM (poll every 200ms, up to 5s)
                found_new = False
                for _ in range(25):
                    await asyncio.sleep(0.2)
                    new_count: int = await page.evaluate(
                        """() => {
                            const seen = new Set();
                            document.querySelectorAll('a[href*="/stellen/"]').forEach(a => {
                                if (a.href && !a.href.includes('/suche/')) seen.add(a.href);
                            });
                            return seen.size;
                        }"""
                    )
                    if new_count > prev_count:
                        found_new = True
                        break

                if not found_new:
                    # Final fallback: maybe there's a button we need to click?
                    diag = await page.evaluate(
                        """() => {
                            const elements = Array.from(document.querySelectorAll('button, a, div[role="button"]'));
                            const btn = elements.find(b => {
                                const txt = (b.textContent || "").trim().toLowerCase();
                                return txt.includes('mehr ergebnisse') || txt.includes('weitere ergebnisse');
                            });
                            if (btn && !btn.disabled) {
                                btn.scrollIntoView({ behavior: 'instant', block: 'center' });
                                btn.click();
                                return true;
                            }
                            return false;
                        }"""
                    )
                    
                    if diag:
                        # We clicked a button, wait another 3s for cards
                        for _ in range(15):
                            await asyncio.sleep(0.2)
                            new_count = await page.evaluate("document.querySelectorAll('a[href*=\"/stellen/\"]').length")
                            if new_count > prev_count:
                                found_new = True
                                break

                    if not found_new:
                        logger.info(
                            f"[{self.job_id}] No new cards after scroll/click — "
                            f"pagination complete ({len(processed_urls)} cards total)."
                        )
                        break

                page_num += 1
                logger.info(
                    f"[{self.job_id}] Pagination success: {new_count} total cards "
                    f"(+{new_count - prev_count} new)"
                )

        except Exception as exc:
            logger.error(
                f"[{self.job_id}] Ausbildung scraper error: {exc}",
                exc_info=True,
            )
        finally:
            await page.close()

    async def _dismiss_cookies(self, page) -> None:
        """Robustly dismiss cookie banners via JS."""
        await page.evaluate(
            """() => {
                const selectors = [
                    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
                    'button[id*="accept"]',
                    'button[id*="cookie"]',
                    '.cookie-banner__accept',
                    '.uc-accept-all'
                ];
                for (const sel of selectors) {
                    const btn = document.querySelector(sel);
                    if (btn) {
                        btn.click();
                        return;
                    }
                }
                // Fallback: find any button containing 'Akzeptieren' or 'Zustimmen'
                const btns = Array.from(document.querySelectorAll('button'));
                const confirm = btns.find(b => {
                    const t = b.textContent.toLowerCase();
                    return t.includes('akzeptieren') || t.includes('alle akzeptieren') || t.includes('zustimmen');
                });
                if (confirm) confirm.click();
            }"""
        )

    # ──────────────────────────────────────────────────────────────
    # Detail page parser
    # ──────────────────────────────────────────────────────────────

    async def _fetch_and_parse(self, page, url: str) -> Optional[LeadRecord]:
        """Fetch detail page HTML via in-page fetch() and parse it."""
        try:
            html = await page.evaluate(
                """async (url) => {
                    const resp = await fetch(url);
                    return await resp.text();
                }""",
                url
            )
            return self._parse_detail(html, url)
        except Exception as e:
            logger.debug(f"[{self.job_id}] Concurrent fetch failed for {url}: {e}")
            return None

    def _parse_detail(self, html: str, url: str) -> Optional[LeadRecord]:
        """
        Extract all fields from a detail page's raw HTML.
        Returns LeadRecord with None for any field not found.
        Never raises — all selectors are guarded.
        """
        doc = BeautifulSoup(html, "html.parser")

        # ── Email ──
        email: str | None = None
        el = doc.select_one(
            "a#t-link-email-contact, "
            "a.job-posting-contact-person__link[href^='mailto:']"
        )
        if el and el.get("href"):
            email = el["href"].replace("mailto:", "").strip() or None
        
        if not email:
            # Fallback: regex search through whole HTML
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', html)
            if email_match:
                candidate = email_match.group(0).lower()
                # Blacklist common false positives
                if not any(x in candidate for x in ["info@ausbildung.de", "support@", "cookie"]):
                    email = candidate

        # ── Phone ──
        phone: str | None = None
        el = doc.select_one(
            "a.job-posting-contact-person__link[href^='tel:']"
        )
        if el:
            phone = el.get_text(strip=True) or None

        # ── Contact person ──
        contact: str | None = None
        el = doc.select_one(".job-posting-contact-person__name")
        if el:
            contact = el.get_text(strip=True) or None

        # ── Company name ──
        company: str | None = None
        el = doc.select_one(".jp-c-header__corporation-link")
        if el:
            company = el.get_text(strip=True) or None

        # ── Address / location ──
        address: str | None = None
        city: str | None = None
        el = doc.select_one(".jp-title__address")
        if el:
            # Strip emoji and whitespace
            raw = el.get_text(separator=" ", strip=True)
            # Remove the emoji character if present
            raw = "".join(c for c in raw if c.isprintable() and not c in "\U0001F000-\U0001FFFF").strip()
            # Remove any leading pin emoji
            raw = raw.lstrip("\U0001F4CD").strip()
            address = raw or None
            # City is the last word (after the zip code)
            if raw:
                city = raw.split()[-1] or None
        
        # Fallback: old selector
        if not address:
            el = doc.select_one(
                ".job-posting-vacancy-select__vacancy .selectize-input .item"
            )
            if el:
                address = el.get_text(strip=True) or None

        # ── Start date (Frühester Beginn) ──
        start_date: str | None = None
        for fact in doc.select(".fact__content"):
            label = fact.select_one(".label")
            if label and "Beginn" in label.get_text():
                val = fact.select_one(".value")
                start_date = val.get_text(strip=True) if val else None
                break

        # ── Job type (Ausbildungsberuf) ──
        job_type: str | None = None
        for fact in doc.select(".fact__content"):
            label = fact.select_one(".label")
            if label and "Ausbildungsberuf" in label.get_text():
                val = fact.select_one(".value")
                job_type = val.get_text(strip=True) if val else None
                break

        return LeadRecord(
            source_type=SourceType.AUSBILDUNG_DE,
            source_url=url,
            search_query=self.config.job_title,
            city=city or self.config.city or None,
            company_name=company,
            address=address,
            email=email,
            phone=phone,
            contact_person=contact,
            job_title=job_type,
            publication_date=start_date,
        )
