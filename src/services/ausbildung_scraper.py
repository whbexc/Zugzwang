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

from bs4 import BeautifulSoup

from .browser import BrowserSession
from ..core.logger import get_logger
from ..core.models import LeadRecord, SearchConfig, SourceType

logger = get_logger(__name__)

SEARCH_URL = "https://www.ausbildung.de/suche/"


class AusbildungScraper:
    """
    Scrapes ausbildung.de job listings.

    Architecture:
    - One Playwright page is opened for the entire session.
    - Detail pages are fetched via in-page JS fetch() — no new tabs.
    - HTML is parsed with BeautifulSoup in Python memory.
    - Resource blocking (images, fonts) reduces memory and network overhead.
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

            # ── Step 1: Navigate to search page ──
            logger.info(f"[{self.job_id}] Navigating to {SEARCH_URL}")
            await page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30_000)

            # Dismiss cookie consent if present
            await self._dismiss_cookies(page)
            await asyncio.sleep(0.25)

            # ── Step 2: Fill search inputs via JS (bypasses autocomplete) ──
            await page.evaluate(
                """(args) => {
                    const what  = document.querySelector('[data-testid="search-input-what"]');
                    const where = document.querySelector('[data-testid="search-input-where"]');
                    const nativeSet = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value'
                    ).set;
                    if (what) {
                        nativeSet.call(what, args.title);
                        what.dispatchEvent(new Event('input', {bubbles: true}));
                    }
                    if (where && args.city) {
                        nativeSet.call(where, args.city);
                        where.dispatchEvent(new Event('input', {bubbles: true}));
                    }
                }""",
                {"title": self.config.job_title, "city": self.config.city or ""},
            )

            await asyncio.sleep(0.1)
            await page.keyboard.press("Enter")
            await asyncio.sleep(0.5)

            logger.info(
                f"[{self.job_id}] Search submitted: "
                f'"{self.config.job_title}" in "{self.config.city or "all"}"'
            )

            processed_urls: set[str] = set()
            yielded_count = 0

            # ── Main pagination loop ──
            while not self._cancelled:
                # Pause / cancel check
                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.1)
                if self._cancelled: break

                # ── Step 3: Harvest card links from current page ──
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
                    f"[{self.job_id}] Found {len(all_links)} card(s), "
                    f"{len(new_links)} new"
                )

                if not new_links:
                    # Could be a load-more that hasn't injected cards yet —
                    # only stop if this is truly the first harvest (no cards at all).
                    if not processed_urls:
                        logger.info(f"[{self.job_id}] No links found on first harvest — stopping.")
                        break
                    # Otherwise the loop will fall through to the has_more check.
                    logger.debug(f"[{self.job_id}] No new links this pass (all already processed).")

                # ── Steps 4–6: Fetch + parse + yield ──
                # --- Step 4 & 5: Process Detail Links in Batches ---
                if new_links:
                    # Process in batches of 5 for speed boost
                    BATCH_SIZE = 5
                    for i in range(0, len(new_links), BATCH_SIZE):
                        # Pause / cancel check
                        while self._paused and not self._cancelled:
                            await asyncio.sleep(0.1)
                        if self._cancelled:
                            break

                        batch = new_links[i : i + BATCH_SIZE]
                        tasks = [self._fetch_and_parse(page, link) for link in batch]
                        batch_results = await asyncio.gather(*tasks)
                        
                        for lead in batch_results:
                            # Pause check between yielding batch items
                            while self._paused and not self._cancelled:
                                await asyncio.sleep(0.1)
                            if self._cancelled: break
                            
                            if lead:
                                if yielded_count >= self.config.max_results:
                                    break
                                
                                # Step 6: Yield if conditions met
                                if self.config.scrape_emails and not lead.email:
                                    logger.debug(f"[{self.job_id}] Skipping lead (no email found): {lead.company_name}")
                                    continue

                                processed_urls.add(lead.source_url)
                                yield lead
                                yielded_count += 1

                        # Incremental scroll to trigger next batch/pagination
                        await page.evaluate("window.scrollBy(0, 800)")
                        await asyncio.sleep(0.1)

                if self._cancelled:
                    break

                if yielded_count >= self.config.max_results:
                    break

                # Pause check before pagination
                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.1)
                if self._cancelled: break

                # ── Step 7: Load-more pagination ──
                # Scroll to bottom to trigger the Intersection Observer
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.keyboard.press("End")
                await asyncio.sleep(0.1)

                await self._dismiss_cookies(page)

                prev_count = len(all_links)

                # Use JS click and return diagnostic info
                diag = await page.evaluate(
                    """() => {
                        const buttons = Array.from(document.querySelectorAll('button'));
                        const btn = buttons.find(b => {
                            const txt = b.textContent.trim().toLowerCase();
                            return txt === 'mehr ergebnisse laden';
                        });

                        if (btn) {
                            const info = {
                                found: true,
                                text: btn.textContent.trim(),
                                disabled: btn.disabled,
                            };
                            btn.scrollIntoView({ behavior: 'instant', block: 'center' });
                            btn.click();
                            return info;
                        }
                        return { found: false };
                    }"""
                )

                if not diag.get("found"):
                    # Button not in DOM yet — wait 2s for lazy-render, then give up
                    logger.debug(f"[{self.job_id}] Load-more button not visible, waiting for lazy-render…")
                    await asyncio.sleep(0.5)
                    lazy_count: int = await page.evaluate(
                        """() => {
                            const seen = new Set();
                            document.querySelectorAll('a[href*="/stellen/"]').forEach(a => {
                                if (a.href && !a.href.includes('/suche/')) seen.add(a.href);
                            });
                            return seen.size;
                        }"""
                    )
                    if lazy_count <= prev_count:
                        logger.info(f"[{self.job_id}] No more results — pagination complete ({prev_count} cards total).")
                        break
                    else:
                        logger.info(f"[{self.job_id}] Lazy-loaded {lazy_count - prev_count} new cards without button click.")
                elif diag.get("disabled"):
                    logger.warning(f"[{self.job_id}] Load-more button is DISABLED — end of results.")
                    break
                else:
                    logger.info(f"[{self.job_id}] JS Click: '{diag.get('text')}'")

                # Poll every 200 ms for up to 8 s
                found_new = False
                for _ in range(40):
                    await asyncio.sleep(0.1)
                    candidate_count: int = await page.evaluate(
                        """() => {
                            const seen = new Set();
                            document.querySelectorAll('a[href*="/stellen/"]').forEach(a => {
                                if (a.href && !a.href.includes('/suche/')) seen.add(a.href);
                            });
                            return seen.size;
                        }"""
                    )
                    if candidate_count > prev_count:
                        found_new = True
                        break

                if not found_new:
                    logger.info(f"[{self.job_id}] No new cards after 8s — pagination complete.")
                    break
                else:
                    logger.info(
                        f"[{self.job_id}] Load-more success: {candidate_count} total cards (+{candidate_count - prev_count})"
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
