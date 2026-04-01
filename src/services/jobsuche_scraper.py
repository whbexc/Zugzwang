"""
ZUGZWANG - Jobsuche Portal Scraper
Core logic adapted from the proven sync Playwright scraper,
converted to async and integrated with ZUGZWANG's architecture.

Improvements over v1:
- Smart waits (networkidle / waitForSelector) instead of hardcoded sleeps
- Full HTML-level email extraction (mailto, data-attrs, entities)
- Retry logic via BrowserSession.navigate()
- Location ("Wo") filter for geo-targeted results
- Robust company/location selectors with multiple fallbacks
- Publication date extraction
- Error tracking with structured log events
- Configurable rate-limit delays via BrowserSession.rate_limiter
"""

from __future__ import annotations
import asyncio
import time
import re
from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional
from urllib.parse import urlparse

if TYPE_CHECKING:
    from playwright.async_api import Page
else:
    Page = Any

from .browser import BrowserSession, BrowserError
from .jobsuche_api import JobsucheAPIClient, JobsucheAPIError
from .website_crawler import WebsiteEmailCrawler
from .email_extractor import (
    normalize_phone, normalize_website,
    extract_emails_from_html, deduplicate_emails,
)
from ..core.events import event_bus
from ..core.logger import get_logger
from ..core.models import LeadRecord, SearchConfig, SourceType
from ..core.security import LicenseManager

logger = get_logger(__name__)

JOBSUCHE_URL = "https://www.arbeitsagentur.de/jobsuche/"
DETAIL_BASE  = "https://www.arbeitsagentur.de"
LISTING_SEL  = 'a[href*="/jobsuche/jobdetail/"]'
RESULT_CARD_SEL = '[id^="ergebnisliste-item-"], article:has(a[href*="/jobsuche/jobdetail/"])'

CAPTCHA_ERROR_SIGNALS = [
    "beim laden der sicherheitsabfrage ist ein fehler aufgetreten",
    "erneut versuchen",
]

CAPTCHA_SIGNALS = [
    "sicherheitsabfrage", "captcha", "ich bin kein roboter",
    "are you a robot", "bitte bestätigen", "verify you are human",
    "zugriff verweigert", "access denied", "bot-erkennung",
    "datenschutz-check",
]

# Known portal domains that usually do not expose a direct employer email.
_KNOWN_JOB_PORTAL_DOMAINS = {
    "heyjobs.co",
    "stepstone.de",
    "indeed.com",
    "monster.de",
    "jobware.de",
    "linkedin.com",
    "xing.com",
    "kununu.com",
    "arbeitsagentur.de",
    "instagram.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "tiktok.com",
}

# Regex for German phone numbers (international and domestic formats)
_PHONE_PATTERN = re.compile(
    r"""
    (?!\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4}\b)
    (?:
        \+49[\s\-/.]?\(?\d{1,5}\)?[\s\-/.]?\d[\d\s\-/.]{4,}  # +49 variants
      | 0049[\s\-/.]?\(?\d{1,5}\)?[\s\-/.]?\d[\d\s\-/.]{4,}   # 0049 variants
      | 0\d{1,5}[\s\-/.]?\d[\d\s\-/.]{4,}                      # domestic 0xx
    )
    """,
    re.VERBOSE,
)

# Date patterns on Jobsuche detail pages
_DATE_PATTERN = re.compile(
    r"""
    (?:Veröffentlicht\s+am|Online\s+seit|Datum|Eingestellt\s+am)
    \s*[:\-]?\s*
    (\d{1,2}\.\d{1,2}\.\d{2,4})
    """,
    re.IGNORECASE | re.VERBOSE,
)
_ISO_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")
_DETAIL_ERROR_PATTERN = re.compile(
    r"(stellenangebot konnte leider nicht geladen|erneut versuchen|fehler aufgetreten|nicht verf(?:u|ü)gbar)",
    re.IGNORECASE,
)


class JobsucheScraper:

    def __init__(self, session: BrowserSession, config: SearchConfig, job_id: str):
        self.session = session
        self.config = config
        self.job_id = job_id
        self.crawler = WebsiteEmailCrawler(session) if config.scrape_emails else None
        self.api_client = JobsucheAPIClient()
        self._cancelled = False
        self._paused = False
        self._total_errors = 0
        self._interaction_queue: asyncio.Queue = asyncio.Queue()
        self._interaction_loop = None
        self._last_solver_url: Optional[str] = None
        self._last_solver_completed_at: float = 0.0

    def cancel(self):  self._cancelled = True
    def pause(self):   self._paused = True
    def resume(self):  self._paused = False

    def _on_solver_completed(self, job_id: str, cookies: list, **kw):
        if job_id == self.job_id:
            logger.info(f"[{self.job_id}] Jobsuche solver reported completion, syncing cookies...")
            message = {"type": "solver_complete", "cookies": cookies}
            if self._interaction_loop is not None:
                self._interaction_loop.call_soon_threadsafe(
                    self._interaction_queue.put_nowait,
                    message,
                )
            else:
                self._interaction_queue.put_nowait(message)

    # ── Main scrape loop ──────────────────────────────────────────────────

    async def scrape(self) -> AsyncGenerator[LeadRecord, None]:
        location = self.config.city or self.config.region
        if not location and self.config.country and self.config.country != "Germany":
            location = self.config.country
        
        logger.info(
            f"[{self.job_id}] Jobsuche scrape: '{self.config.job_title}' "
            f"in '{location or 'All Germany'}'"
        )

        page = None
        try:
            # The API is great for lightweight listing-only runs, but it does not
            # expose the browser detail flow we use for website/email enrichment.
            # Keep browser scraping as the primary path whenever email scraping is enabled.
            if not self.config.scrape_emails:
                api_records = await self._scrape_via_api()
                if api_records:
                    logger.info(
                        f"[{self.job_id}] Jobsuche API returned {len(api_records)} records; "
                        "skipping browser fallback"
                    )
                    async for record in self._yield_records(api_records):
                        yield record
                    return

            page = await self.session.new_page()
            page.set_default_timeout(60_000)

            # ── Open Jobsuche ─────────────────────────────────────
            success = await self.session.navigate(
                page, JOBSUCHE_URL, timeout=60_000, retries=3,
                wait_until="domcontentloaded",
            )
            if not success:
                raise BrowserError("Failed to load Jobsuche portal after retries")

            await self._wait_for_page_ready(page)
            await self._handle_captcha(page)

            # ── Accept cookies ────────────────────────────────────
            await self._dismiss_cookie_banner(page)
            # Ensure results are still there if we get interrupted
            await self._wait_for_page_ready(page)

            # ── Select Ausbildung/Duales Studium from dropdown ────
            await self._select_angebotsart(page)

            # ── Fill "Was" (search term) ──────────────────────────
            await self._fill_search_field(
                page,
                selectors='input[id*="was"], input[placeholder*="Berufsfeld"], input[aria-label*="Was"]',
                value=self.config.job_title,
                field_name="Was",
            )

            # ── Fill "Wo" (location) if provided ──────────────────
            if self.config.city or self.config.region:
                wo_value = self.config.city or self.config.region
                await self._fill_search_field(
                    page,
                    selectors='input[id*="wo"], input[placeholder*="Ort"], input[aria-label*="Wo"]',
                    value=wo_value,
                    field_name="Wo",
                )

            # ── Submit search ─────────────────────────────────────
            await page.keyboard.press("Enter")
            await self._wait_for_results(page)
            captcha_seen = await self._handle_captcha(page)
            if captcha_seen:
                await self._resync_results_after_captcha(page)
            await self._wait_for_results(page)  # Wait again in case Captcha triggered a reload

            # ── Apply "Latest" sorting if requested ────────────────
            if self.config.latest_offers_only:
                await self._select_sorting_latest(page)

            streamed_results = 0
            try:
                async for record in self._scrape_from_results_view(page):
                    streamed_results += 1
                    yield record
            except Exception as e:
                logger.warning(f"[{self.job_id}] Results-view extraction fallback triggered: {e}")

            if streamed_results:
                logger.info(f"[{self.job_id}] Jobsuche completed via results view with {streamed_results} results")
                return

            logger.warning(f"[{self.job_id}] Falling back to direct detail pages because results-view extraction produced no results")
            hrefs = await self._collect_listing_hrefs(page)
            if not hrefs:
                logger.warning(f"[{self.job_id}] No Jobsuche detail pages found")
                return

            logger.info(f"[{self.job_id}] Unique detail pages to visit: {len(hrefs)}")

            results_count = 0
            for index, url in enumerate(hrefs, start=1):
                if self._cancelled or results_count >= self.config.max_results:
                    break

                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.5)

                try:
                    logger.info(f"[{self.job_id}] Opening Jobsuche detail {index}/{len(hrefs)}")
                    record = await self._extract_detail(page, url)
                    if not record:
                        self._log_skip(url, "empty record (no company/title)")
                        continue

                    if self.crawler and not record.email:
                        await self._enrich_from_website_candidates(record)

                    if not LicenseManager.can_extract():
                        logger.warning(f"[{self.job_id}] Free trial limit reached (20/day). Stopping.")
                        event_bus.emit(
                            event_bus.JOB_LOG,
                            job_id=self.job_id,
                            message="Free trial limit reached (20 scraps/day). Please upgrade to Professional.",
                            level="WARNING",
                        )
                        event_bus.emit(event_bus.TRIAL_LIMIT_REACHED, job_id=self.job_id)
                        return

                    results_count += 1
                    logger.info(
                        f"[{self.job_id}] [{results_count}] {record.company_name or '-'} - "
                        f"{record.job_title or '-'} | email={'yes' if record.email else 'no'}"
                    )
                    event_bus.emit(
                        event_bus.JOB_RESULT,
                        job_id=self.job_id,
                        record=record,
                        count=results_count,
                    )
                    LicenseManager.record_extraction()
                    yield record

                except Exception as e:
                    self._total_errors += 1
                    logger.warning(f"[{self.job_id}] Error on detail page {index}: {e}")
                    event_bus.emit(
                        event_bus.JOB_LOG,
                        job_id=self.job_id,
                        message=f"Error extracting detail page {index}: {e}",
                        level="WARNING",
                    )

                await asyncio.sleep(0.35)
                await self.session.rate_limiter.wait()


        except BrowserError:
            raise
        except Exception as e:
            logger.error(f"[{self.job_id}] Scraper error: {e}", exc_info=True)
            if page is not None:
                await self.session.screenshot_on_failure(page, "crash")
            raise
        finally:
            if self._total_errors > 0:
                logger.warning(
                    f"[{self.job_id}] Scrape finished with {self._total_errors} errors"
                )
            try:
                if page is not None:
                    await page.close()
            except Exception:
                pass

    async def _scrape_via_api(self) -> list[LeadRecord]:
        """Fetch Jobsuche records from the public JSON API before falling back to Playwright."""
        try:
            records = await self.api_client.fetch_records(self.config)
            return records
        except JobsucheAPIError as e:
            logger.info(f"[{self.job_id}] Jobsuche API unavailable, falling back to browser: {e}")
        except Exception as e:
            logger.info(f"[{self.job_id}] Jobsuche API request failed, falling back to browser: {e}")
        return []

    async def _yield_records(self, records: list[LeadRecord]) -> AsyncGenerator[LeadRecord, None]:
        results_count = 0
        for record in records:
            if self._cancelled or results_count >= self.config.max_results:
                break

            while self._paused and not self._cancelled:
                await asyncio.sleep(0.5)

            if self.crawler and not record.email:
                await self._enrich_from_website_candidates(record)

            if not LicenseManager.can_extract():
                logger.warning(f"[{self.job_id}] Free trial limit reached (20/day). Stopping.")
                event_bus.emit(
                    event_bus.JOB_LOG,
                    job_id=self.job_id,
                    message="Free trial limit reached (20 scraps/day). Please upgrade to Professional.",
                    level="WARNING",
                )
                event_bus.emit(event_bus.TRIAL_LIMIT_REACHED, job_id=self.job_id)
                return

            results_count += 1
            logger.info(
                f"[{self.job_id}] [{results_count}] {record.company_name or '-'} - "
                f"{record.job_title or '-'} | email={'yes' if record.email else 'no'}"
            )
            event_bus.emit(
                event_bus.JOB_RESULT,
                job_id=self.job_id,
                record=record,
                count=results_count,
            )
            LicenseManager.record_extraction()
            yield record

    # ── Detail page extraction ────────────────────────────────────────────

    async def _extract_detail(self, page: Page, url: str) -> Optional[LeadRecord]:
        """Visit a job detail page and extract all available fields."""
        # Use session.navigate for built-in retry + timeout handling
        success = await self.session.navigate(
            page, url, timeout=30_000, retries=3, wait_until="domcontentloaded",
        )
        if not success:
            self._total_errors += 1
            self._log_skip(url, "navigation failed after retries")
            return None

        await self._wait_for_page_ready(page, timeout=5_000)
        await self._handle_captcha(page)
        await self._wait_for_page_ready(page, timeout=2_000)

        record = LeadRecord(
            source_type=SourceType.JOBSUCHE,
            search_query=self._build_query(),
            source_url=url,
            country=self.config.country,
        )

        # Get both innerText (for regex) and full HTML (for email extraction)
        full_text = ""
        html_content = ""
        try:
            full_text = await page.inner_text("body", timeout=2000)
        except Exception:
            pass
        try:
            html_content = await page.content()
        except Exception:
            pass

        # ── Email — use improved HTML-level extraction ────────────
        if html_content:
            emails = deduplicate_emails(extract_emails_from_html(html_content))
        elif full_text:
            emails = deduplicate_emails(extract_emails_from_html(full_text))
        else:
            emails = []

        if emails:
            record.email = emails[0]
            record.email_source_page = url

        # Also check for tel: links → may contain mailto adjacent
        try:
            tel_links = await page.locator('a[href^="tel:"]').all()
            for link in tel_links[:3]:
                href = await link.get_attribute("href", timeout=2000)
                if href:
                    phone_raw = href.replace("tel:", "").strip()
                    if phone_raw and not record.phone:
                        record.phone = normalize_phone(phone_raw)
        except Exception:
            pass

        # ── Job title ─────────────────────────────────────────────
        record.job_title = await self._extract_text_with_fallbacks(page, [
            "h1",
            '[data-testid*="title"]',
            '[class*="jobtitle"]',
            '[class*="stellentitel"]',
        ]) or ""

        # ── Company name ──────────────────────────────────────────
        record.company_name = await self._extract_text_with_fallbacks(page, [
            '[class*="company"]',
            '[class*="arbeitgeber"]',
            '[data-testid*="company"]',
            '[data-testid*="employer"]',
        ]) or ""

        # Fallback: parse "Arbeitgeber:" from page text
        if not record.company_name and full_text:
            m = re.search(
                r"Arbeitgeber\s*[:\-]\s*(.+?)(?:\n|$)", full_text
            )
            if m:
                record.company_name = m.group(1).strip()

        # ── Location / city ───────────────────────────────────────
        location_text = await self._extract_text_with_fallbacks(page, [
            '[class*="location"]',
            '[class*="ort"]',
            '[class*="arbeitsort"]',
            '[data-testid*="location"]',
        ])
        if location_text and not self._is_generic_location_text(location_text):
            record.city = location_text
            record.address = location_text
            # Try to extract postal code from location text
            plz_match = re.search(r"\b(\d{5})\b", location_text)
            if plz_match:
                record.postal_code = plz_match.group(1)
            # Try to extract city name after postal code
            city_match = re.search(
                r"\d{5}\s+([A-ZÄÖÜa-zäöüß][^\n,]{2,})", location_text
            )
            if city_match:
                record.city = city_match.group(1).strip()

        # ── Phone (from text if not already found via tel: link) ──
        if not record.phone and full_text:
            phone = self._extract_phone_candidate(full_text)
            if phone:
                record.phone = phone

        # ── Website — first external link on page ─────────────────
        if not record.website:
            record.website = await self._extract_website_url(page)

        # ── Publication date ──────────────────────────────────────
        if full_text and not record.publication_date:
            date_match = _DATE_PATTERN.search(full_text)
            if date_match:
                record.publication_date = date_match.group(1)
            else:
                iso_match = _ISO_DATE_PATTERN.search(full_text)
                if iso_match:
                    record.publication_date = iso_match.group(1)

        if not record.company_name and not record.job_title:
            return None

        return record.normalize()

    async def _scrape_from_results_view(self, page: Page) -> AsyncGenerator[LeadRecord, None]:
        """Prefer extracting from the split results view to avoid direct jobdetail 403s."""
        await self._switch_to_detail_view(page)
        await self._wait_for_results(page)

        seen: set[str] = set()
        results_count = 0
        card_index = 0

        while not self._cancelled and results_count < self.config.max_results:
            while self._paused and not self._cancelled:
                await asyncio.sleep(0.5)

            cards = page.locator(RESULT_CARD_SEL)
            current_count = await cards.count()

            if current_count <= 0:
                logger.warning(f"[{self.job_id}] No result cards visible in Detailansicht")
                break

            if card_index >= current_count:
                grew = await self._advance_results_list(page, current_count)
                refreshed_count = await cards.count()
                if not grew and refreshed_count <= current_count:
                    break
                continue

            card = cards.nth(card_index)
            card_index += 1

            try:
                record = await self._extract_result_card(page, card, card_index)
                if not record:
                    continue

                dedupe_key = record.source_url or f"{record.company_name}|{record.job_title}|{record.website}"
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                if self.crawler and not record.email:
                    await self._enrich_from_website_candidates(record)

                if not LicenseManager.can_extract():
                    logger.warning(f"[{self.job_id}] Free trial limit reached (20/day). Stopping.")
                    event_bus.emit(
                        event_bus.JOB_LOG,
                        job_id=self.job_id,
                        message="Free trial limit reached (20 scraps/day). Please upgrade to Professional.",
                        level="WARNING",
                    )
                    event_bus.emit(event_bus.TRIAL_LIMIT_REACHED, job_id=self.job_id)
                    return

                results_count += 1
                logger.info(
                    f"[{self.job_id}] [{results_count}] {record.company_name or '-'} - "
                    f"{record.job_title or '-'} | email={'yes' if record.email else 'no'}"
                )
                event_bus.emit(
                    event_bus.JOB_RESULT,
                    job_id=self.job_id,
                    record=record,
                    count=results_count,
                )
                LicenseManager.record_extraction()
                yield record

            except Exception as e:
                self._total_errors += 1
                logger.warning(f"[{self.job_id}] Error on result card {card_index}: {e}")

            await asyncio.sleep(0.25)
            await self.session.rate_limiter.wait()

    # ── Helper methods ────────────────────────────────────────────────────

    async def _wait_for_page_ready(self, page: Page, timeout: int = 10_000) -> None:
        """Wait for page to be reasonably loaded."""
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            # networkidle can be flaky on SPAs; fall back to a short pause
            await asyncio.sleep(1.0)

    async def _wait_for_results(self, page: Page) -> None:
        """Wait for search results to appear after form submission."""
        try:
            # Wait for either the listing container or the "no results" message
            await page.wait_for_selector(
                f"{LISTING_SEL}, .ergebnismeldung, h1:has-text('keine Treffer')", 
                state="attached", 
                timeout=20_000,
            )
            await asyncio.sleep(0.2)
        except Exception:
            # Results might take longer or there may be none
            logger.debug(f"[{self.job_id}] Results selector timeout - continuing")
            await asyncio.sleep(0.4)

    async def _resync_results_after_captcha(self, page: Page) -> None:
        """Re-establish the split results view after a Jobsuche captcha reload."""
        try:
            await self._wait_for_page_ready(page, timeout=8_000)
            await self._wait_for_results(page)
            await self._switch_to_detail_view(page)
            await self._wait_for_results(page)
            logger.info(f"[{self.job_id}] Results view re-synced after captcha")
        except Exception as e:
            logger.debug(f"[{self.job_id}] Could not fully re-sync after captcha: {e}")

    async def _dismiss_cookie_banner(self, page: Page) -> None:
        """Accept GDPR / cookie banner if present."""
        try:
            cookie_btn = page.locator('button:has-text("Alle Cookies akzeptieren")')
            if await cookie_btn.first.is_visible(timeout=4_000):
                await cookie_btn.first.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass

    async def _select_angebotsart(self, page: Page) -> None:
        """Select the configured offer type from the dropdown."""
        try:
            target = self.config.offer_type
            if target == "Arbeit":
                return # Default is already 'Arbeit' usually, or it's the first option.
                
            dropdown_btn = page.locator("button#angebotsart-dropdown-button")
            await dropdown_btn.wait_for(state="visible", timeout=10_000)
            await dropdown_btn.click()
            await asyncio.sleep(0.12)

            option = page.locator(
                f"#angebotsart-dropdownList li:has-text('{target}')"
            ).first
            await option.wait_for(state="visible", timeout=8_000)
            await option.click()
            await asyncio.sleep(0.15)
            logger.info(f"[{self.job_id}] Angebotsart set to {target}")
        except Exception as e:
            logger.warning(f"[{self.job_id}] Could not set Angebotsart: {e}")

    async def _select_sorting_latest(self, page: Page) -> None:
        """Select 'Neueste Veröffentlichung' from the sorting dropdown."""
        try:
            logger.info(f"[{self.job_id}] Applying 'Latest' sorting...")
            
            # 1. Click the sort dropdown button
            sort_btn = page.locator("button#sortierung-dropdown-button")
            await sort_btn.wait_for(state="visible", timeout=10_000)
            await sort_btn.click()
            await asyncio.sleep(0.5)

            # 2. Select 'Neueste Veröffentlichung' (typically the second item)
            # Identifying by text is safer than by ID if IDs change
            latest_opt = page.locator(
                "a[id*='sortierung-dropdown-item']:has-text('Neueste'), "
                "a:has-text('Neueste Veröffentlichung')"
            ).first
            
            await latest_opt.wait_for(state="visible", timeout=8_000)
            await latest_opt.click()
            
            # 3. Wait for the page to refresh results
            await asyncio.sleep(1.5)
            await self._wait_for_results(page)
            logger.info(f"[{self.job_id}] Sorted by: Neueste Veröffentlichung")
            
        except Exception as e:
            logger.warning(f"[{self.job_id}] Could not apply latest sorting: {e}")

    async def _switch_to_detail_view(self, page: Page) -> None:
        """Switch the Jobsuche results page into the split-pane detail view."""
        selectors = [
            '#ansicht-auswahl-tabbar-item-1',
            'button:has-text("Detailansicht")',
            'a:has-text("Detailansicht")',
            '[role="tab"]:has-text("Detailansicht")',
        ]
        for selector in selectors:
            try:
                button = page.locator(selector).first
                if await button.count() <= 0:
                    continue
                await button.scroll_into_view_if_needed(timeout=1_200)
                if await button.get_attribute("aria-selected") == "true":
                    logger.info(f"[{self.job_id}] Detailansicht already active")
                    return
                await button.click()
                await asyncio.sleep(0.3)
                logger.info(f"[{self.job_id}] Switched to Detailansicht")
                return
            except Exception:
                continue

        logger.warning(f"[{self.job_id}] Could not switch to Detailansicht")

    async def _advance_results_list(self, page: Page, previous_count: int) -> bool:
        """Try to reveal more result cards in the left results column via infinite scroll."""
        try:
            # Jobsuche uses infinite scroll on the results list. 
            # We need to scroll the actual list container.
            await page.evaluate("""
            () => {
                const listContainer = document.querySelector(
                    '[id*="ergebnisliste"], .ergebnisliste, main, section'
                );
                if (listContainer) {
                    listContainer.scrollTop = listContainer.scrollHeight;
                }
                window.scrollTo(0, document.body.scrollHeight);
            }
            """)
            
            # Use mouse wheel as a fallback to trigger lazy loading listeners
            await page.mouse.wheel(0, 3500)
            await asyncio.sleep(1.0)
        except Exception as e:
            logger.debug(f"[{self.job_id}] Scroll failed: {e}")
            await page.mouse.wheel(0, 2500)

        # Fallback click if a "Mehr laden" button exists (Jobsuche sometimes shows one after many scrolls)
        clicked_more = await self._click_load_more(page)
        await asyncio.sleep(0.5 if clicked_more else 0.25)

        try:
            return await page.locator(RESULT_CARD_SEL).count() > previous_count
        except Exception:
            return False

        clicked_more = await self._click_load_more(page)
        await asyncio.sleep(0.5 if clicked_more else 0.25)

        try:
            return await page.locator(RESULT_CARD_SEL).count() > previous_count
        except Exception:
            return False

    async def _extract_result_card(self, page: Page, card: Any, card_index: int) -> Optional[LeadRecord]:
        """Click a left-side result card and extract data from the right detail panel."""
        await self._click_result_card(page, card, card_index, "initial")
        await asyncio.sleep(0.25)
        captcha_seen = await self._handle_captcha(page)
        if captcha_seen:
            await self._resync_results_after_captcha(page)
            refreshed_cards = page.locator(RESULT_CARD_SEL)
            if await refreshed_cards.count() >= card_index:
                card = refreshed_cards.nth(card_index - 1)
                await self._click_result_card(page, card, card_index, "post-captcha")
                await asyncio.sleep(0.5)

        detail_url = await self._extract_card_href(card)
        card_text = ""
        try:
            card_text = (await card.inner_text(timeout=1500)).strip()
        except Exception:
            pass
        record = LeadRecord(
            source_type=SourceType.JOBSUCHE,
            search_query=self._build_query(),
            source_url=detail_url or page.url,
            country=self.config.country,
        )

        # Prefer detail panel on the right side for clean data extraction.
        # Scoped to the header (kopfbereich) which is stable across all view types.
        try:
            extracted = await page.evaluate("""
            () => {
                const container = document.querySelector('#jobdetail-container');
                if (!container) return null;

                // Job title: stable #jobdetail-titel or #detail-kopfbereich-titel
                let jobTitle = (
                    container.querySelector('#detail-kopfbereich-titel') ||
                    container.querySelector('#jobdetail-titel') || 
                    container.querySelector('.ba-jobdetail-titel') ||
                    container.querySelector('h1')
                )?.innerText?.trim() || '';
                
                // Company name: prefer the stable employer lane and strip screen-reader labels.
                const companyNode = (
                    container.querySelector('#detail-kopfbereich-firma') ||
                    container.querySelector('#jobdetail-arbeitgeber') ||
                    container.querySelector('.ba-jobdetail-firma') ||
                    container.querySelector('.detail-begleittext')
                );
                let company = '';
                if (companyNode) {
                    const clone = companyNode.cloneNode(true);
                    clone.querySelectorAll('.sr-only, .visually-hidden, [aria-hidden="true"]').forEach((node) => node.remove());
                    company = (clone.textContent || '').trim();
                }
                
                // Location: usually found in the details below the action buttons or in data-testid
                let location = (container.querySelector(
                    '#detail-kopfbereich-ort, [id*="arbeitsort"], [class*="arbeitsort"], [data-testid*="location"]'
                )?.innerText || '').trim();

                // Final safety scrub for accessibility artifacts
                if (jobTitle.toLowerCase().includes('sicherheitsabfrage')) jobTitle = '';
                if (company.toLowerCase().includes('filterbarer inhalt')) company = '';
                company = company.replace(/^arbeitgeber\\s*[:\\-]?\\s*/i, '').trim();
                
                return { jobTitle, company, location };
            }
            """)
            if extracted:
                record.job_title = extracted.get('jobTitle', '')
                record.company_name = extracted.get('company', '')
                location_text = extracted.get('location', '')
                if location_text and not self._is_generic_location_text(location_text):
                    record.city = location_text
                    plz_match = __import__('re').search(r'\\b(\\d{5})\\b', location_text)
                    if plz_match:
                        record.postal_code = plz_match.group(1)
        except Exception as e:
            logger.debug(f"[{self.job_id}] JS extraction failed: {e}")

        try:
            visible_meta = await page.evaluate(
                """() => {
                    const container = document.querySelector('#jobdetail-container') || document.body;
                    const pick = (...selectors) => {
                        for (const selector of selectors) {
                            const el = container.querySelector(selector) || document.querySelector(selector);
                            if (!el) continue;
                            const text = (el.innerText || el.textContent || '').trim();
                            if (text) return text;
                        }
                        return '';
                    };
                    return {
                        headerLocation: pick('#detail-kopfbereich-ort', '[id*="arbeitsort"]', '[class*="arbeitsort"]', '[data-testid*="location"]'),
                        publishedText: pick('time', '[class*="veroeffentlicht"]', '[class*="veröffentlicht"]', '[class*="datum"]', '[class*="date"]'),
                        detailText: (container.innerText || '').trim(),
                    };
                }"""
            )
            if visible_meta:
                header_location = (visible_meta.get("headerLocation") or "").strip()
                if header_location and not self._is_generic_location_text(header_location):
                    if not record.city:
                        record.city = self._extract_city_candidate(
                            header_location,
                            company_name=record.company_name or "",
                            job_title=record.job_title or "",
                        ) or header_location
                    if not record.postal_code:
                        plz_match = re.search(r"\b(\d{5})\b", header_location)
                        if plz_match:
                            record.postal_code = plz_match.group(1)

                if not record.publication_date:
                    record.publication_date = self._extract_publication_candidate(visible_meta.get("publishedText") or "")
                if not record.publication_date:
                    record.publication_date = self._extract_publication_candidate(visible_meta.get("detailText") or "")
                if not record.phone:
                    record.phone = self._extract_phone_candidate(visible_meta.get("detailText") or "")
                if not record.city:
                    record.city = self._extract_city_candidate(
                        visible_meta.get("detailText") or "",
                        company_name=record.company_name or "",
                        job_title=record.job_title or "",
                    )
        except Exception:
            pass

        try:
            visible_detail_text = await page.locator('#jobdetail-container').inner_text(timeout=1500)
        except Exception:
            visible_detail_text = ""
        labeled_fields = self._extract_labeled_contact_fields(visible_detail_text)
        visible_detail_fields = self._extract_visible_detail_fields(visible_detail_text)
        if not record.email and labeled_fields.get("email"):
            record.email = labeled_fields["email"]
            record.email_source_page = detail_url or page.url
        if not record.phone and labeled_fields.get("phone"):
            record.phone = labeled_fields["phone"]
        if not record.website and labeled_fields.get("website"):
            record.website = labeled_fields["website"]
        if not record.city and visible_detail_fields.get("city"):
            record.city = visible_detail_fields["city"]
        if not record.publication_date and visible_detail_fields.get("publication_date"):
            record.publication_date = visible_detail_fields["publication_date"]

        # Fallback: read from card selectors
        if not record.job_title:
            raw_title = await self._extract_card_text(card, [
                'h2', 'h3', '[class*="titel"]', '[class*="title"]',
            ]) or ''
            # Strip screen-reader prefix like "X. Ergebnis: <title>"
            if ':' in raw_title and 'ergebnis' in raw_title.lower():
                record.job_title = raw_title.split(':', 1)[-1].strip()
            elif 'sicherheitsabfrage' not in raw_title.lower() and 'ergebnis' not in raw_title.lower():
                record.job_title = raw_title

        if not record.company_name:
            record.company_name = await self._extract_card_text(card, [
                '[class*="arbeitgeber"]', '[class*="company"]', '[class*="firma"]',
            ]) or ''

        if not record.city:
            card_location = await self._extract_card_text(card, [
                '[class*="arbeitsort"]',
                '[class*="ort"]',
                '[class*="location"]',
                '[data-testid*="location"]',
            ]) or ''
            if card_location and not self._is_generic_location_text(card_location):
                record.city = card_location
                plz_match = re.search(r"\b(\d{5})\b", card_location)
                if plz_match:
                    record.postal_code = plz_match.group(1)
        if not record.city and card_text:
            record.city = self._extract_city_candidate(
                card_text,
                company_name=record.company_name or "",
                job_title=record.job_title or "",
            )

        if not record.publication_date:
            card_date = await self._extract_card_text(card, [
                '[class*="veroeffentlicht"]',
                '[class*="veröffentlicht"]',
                '[class*="datum"]',
                '[class*="date"]',
                'time',
            ]) or ''
            if card_date:
                date_match = _DATE_PATTERN.search(card_date)
                iso_match = _ISO_DATE_PATTERN.search(card_date)
                if date_match:
                    record.publication_date = date_match.group(1)
                elif iso_match:
                    record.publication_date = iso_match.group(1)
                elif any(token in card_date.lower() for token in ("heute", "gestern", "tage", "veröffentlicht")):
                    record.publication_date = card_date.strip()

        if not record.publication_date and card_text:
            record.publication_date = self._extract_publication_candidate(card_text)

        # Final fallback: read from detail panel h1/h2 via Python
        if not record.job_title:
            for sel in ['h1', 'h2']:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0:
                        text = (await loc.inner_text(timeout=1500)).strip()
                        if text and 'sicherheitsabfrage' not in text.lower() and 'ergebnis' not in text.lower():
                            record.job_title = text
                            break
                except Exception:
                    pass

        if not record.company_name:
            for sel in ['[class*="arbeitgeber"]', '[class*="company"]', 'h2 + div', 'h1 + div']:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0:
                        text = (await loc.inner_text(timeout=1500)).strip()
                        if text and 'sicherheitsabfrage' not in text.lower():
                            record.company_name = text
                            break
                except Exception:
                    pass

        website_candidates = await self._extract_application_website_candidates(page)
        if website_candidates:
            preferred_website = self._choose_preferred_website(website_candidates)
            if preferred_website:
                record.website = preferred_website

        if record.company_name and _DETAIL_ERROR_PATTERN.search(record.company_name):
            record.company_name = None
        if record.job_title and _DETAIL_ERROR_PATTERN.search(record.job_title):
            record.job_title = None

        # Extension-inspired fallback: harvest the visible Jobsuche detail IDs
        # even when the application panel was not considered "ready".
        if not record.email:
            direct_email = await self._extract_application_email(page)
            if direct_email:
                record.email = direct_email
                record.email_source_page = detail_url or page.url
            else:
                try:
                    desc_html = ""
                    desc = page.locator('#detail-beschreibung-text-container').first
                    if await desc.count() > 0:
                        desc_html = await desc.inner_html(timeout=1500)
                    if desc_html:
                        match = re.search(r"mailto:([^\"'?<>\s]+)", desc_html, flags=re.IGNORECASE)
                        if match:
                            record.email = match.group(1).strip().lower()
                            record.email_source_page = detail_url or page.url
                except Exception:
                    pass

        if not record.phone:
            try:
                phone_el = page.locator('#detail-bewerbung-telefon-Telefon').first
                if await phone_el.count() > 0:
                    phone_href = await phone_el.get_attribute('href', timeout=1000)
                    phone_text = (phone_href or "").replace('tel:', '').strip() or (await phone_el.inner_text(timeout=1000)).strip()
                    if phone_text:
                        record.phone = normalize_phone(phone_text)
            except Exception:
                pass

        try:
            visible_contact = await page.evaluate(
                """() => {
                    const addressParent = document.getElementById('detail-bewerbung-adresse');
                    const mailElement = document.getElementById('detail-bewerbung-mail');
                    const phoneElement = document.getElementById('detail-bewerbung-telefon-Telefon');
                    const descContainer = document.getElementById('detail-beschreibung-text-container');
                    const externalBtn = document.getElementById('detail-beschreibung-externe-url-btn');

                    let company = '';
                    let contact = '';
                    let address = '';
                    let city = '';
                    let postalCode = '';
                    let email = mailElement ? (mailElement.textContent || '').trim() : '';
                    let phone = '';
                    let website = externalBtn ? (externalBtn.getAttribute('href') || '').trim() : '';

                    if (phoneElement) {
                        phone = ((phoneElement.getAttribute('href') || '').replace('tel:', '').trim() || (phoneElement.textContent || '').trim());
                    }

                    if (addressParent) {
                        const html = addressParent.innerHTML || '';
                        const lines = html
                            .split(/<br\\s*\\/?>/i)
                            .map(l => l.trim().replace(/<.*?>/g, '').trim())
                            .filter(Boolean);
                        company = lines[0] || '';
                        contact = lines[1] || '';
                        address = lines.join('\\n');
                        const lastLine = lines[lines.length - 1] || '';
                        const plzMatch = lastLine.match(/\\b(\\d{5})\\b/);
                        if (plzMatch) {
                            postalCode = plzMatch[1];
                            const cityMatch = lastLine.match(/\\b\\d{5}\\s+(.+)$/);
                            if (cityMatch) city = cityMatch[1].trim();
                        }
                    }

                    if (!email && descContainer) {
                        const html = descContainer.innerHTML || '';
                        const mailtoMatch = html.match(/mailto:([^"'?<>\\s]+)/i);
                        if (mailtoMatch) {
                            email = mailtoMatch[1].trim();
                        }
                    }

                    return { company, contact, address, city, postalCode, email, phone, website };
                }"""
            )
            if visible_contact:
                if not record.company_name and visible_contact.get("company"):
                    record.company_name = visible_contact["company"]
                if not record.contact_person and visible_contact.get("contact"):
                    record.contact_person = visible_contact["contact"]
                if not record.address and visible_contact.get("address"):
                    address_lines = [line.strip() for line in str(visible_contact["address"]).splitlines() if line.strip()]
                    record.address = "\n".join(address_lines[2:]) if len(address_lines) >= 3 else visible_contact["address"]
                if not record.city and visible_contact.get("city"):
                    record.city = visible_contact["city"]
                if not record.postal_code and visible_contact.get("postalCode"):
                    record.postal_code = visible_contact["postalCode"]
                if not record.email and visible_contact.get("email"):
                    record.email = visible_contact["email"].lower()
                    record.email_source_page = detail_url or page.url
                if not record.phone and visible_contact.get("phone"):
                    record.phone = normalize_phone(visible_contact["phone"])
                if not record.website and visible_contact.get("website"):
                    normalized_website = normalize_website(visible_contact["website"])
                    if normalized_website and not normalized_website.lower().startswith("mailto:") and not self._is_untrusted_website_candidate(normalized_website):
                        record.website = normalized_website
        except Exception:
            pass

        if not record.address:
            address_block = await self._extract_application_address(page)
            if address_block and not self._is_generic_location_text(address_block):
                record.address = address_block
                address_lines = [line.strip() for line in address_block.splitlines() if line.strip()]
                if not record.company_name and address_lines:
                    record.company_name = address_lines[0]
                if len(address_lines) >= 2 and not record.contact_person:
                    possible_contact = address_lines[1]
                    if not re.search(r'\b\d{5}\b', possible_contact) and not re.search(r'\d', possible_contact):
                        record.contact_person = possible_contact
                if not record.city:
                    city_match = re.search(r'\b\d{5}\s+([^\n,]+)', address_block)
                    if city_match:
                        record.city = city_match.group(1).strip()
                if not record.postal_code:
                    plz_match = re.search(r'\b(\d{5})\b', address_block)
                    if plz_match:
                        record.postal_code = plz_match.group(1)

        if not record.website:
            direct_website = await self._extract_application_website(page)
            if direct_website:
                record.website = direct_website

        panel_ready = False
        should_try_panel = not any([
            record.email,
            record.phone,
            record.address,
            record.website,
        ])
        if should_try_panel:
            await self._open_application_panel(page)
            panel_ready = await self._wait_for_application_panel(page)
            if panel_ready:
                captcha_seen = await self._handle_captcha(page)
                if captcha_seen:
                    await self._open_application_panel(page)
                    panel_ready = await self._wait_for_application_panel(page) or panel_ready

        if not panel_ready:
            logger.info(
                f"[{self.job_id}] Application panel not visible for card {card_index}; continuing with visible detail data"
            )
            return record.normalize() if (record.company_name or record.job_title or record.website) else None

        panel_text = await self._get_application_panel_text(page)
        panel_html = await self._get_application_panel_html(page)
        labeled_fields = self._extract_labeled_contact_fields("\n".join(filter(None, [panel_text, panel_html])))
        if not record.email and labeled_fields.get("email"):
            record.email = labeled_fields["email"]
            record.email_source_page = detail_url or page.url
        if not record.phone and labeled_fields.get("phone"):
            record.phone = labeled_fields["phone"]
        if not record.website and labeled_fields.get("website"):
            record.website = labeled_fields["website"]

        direct_email = await self._extract_application_email(page)
        if direct_email:
            record.email = direct_email
            record.email_source_page = detail_url or page.url
        else:
            emails = deduplicate_emails(extract_emails_from_html(panel_html or panel_text or ''))
            if emails:
                record.email = emails[0]
                record.email_source_page = detail_url or page.url
        
        # Targeted Phone ID provided by user
        p_el = page.locator('#detail-bewerbung-telefon-Telefon, [id*="bewerbung-telefon"], [id*="kontakt-telefon"]').first
        if await p_el.count() > 0:
            p_text = (await p_el.inner_text(timeout=500)).strip()
            if p_text:
                record.phone = normalize_phone(p_text)

        if not record.phone:
            phone = self._extract_phone_candidate(panel_text or '')
            if phone:
                record.phone = phone

        if not record.phone:
            phone_match = re.search(r'Telefon\s*:\s*([+\d][\d\s()./\-]{5,})', panel_text or '', re.IGNORECASE)
            if phone_match:
                phone = normalize_phone(phone_match.group(1).strip())
                if phone:
                    record.phone = phone

        address_block = await self._extract_application_address(page)
        if address_block and not self._is_generic_location_text(address_block):
            record.address = address_block
            address_lines = [line.strip() for line in address_block.splitlines() if line.strip()]
            plz_match = re.search(r'\b(\d{5})\b', address_block)
            if plz_match:
                record.postal_code = plz_match.group(1)
            city_match = re.search(r'\d{5}\s+([^\n,]+)', address_block)
            if city_match:
                record.city = city_match.group(1).strip()

            if len(address_lines) >= 2:
                possible_contact = address_lines[1]
                if not re.search(r'\b\d{5}\b', possible_contact) and not re.search(r'\d', possible_contact):
                    record.contact_person = possible_contact

            if not record.company_name:
                first_line = address_lines[0].strip() if address_lines else ''
                if first_line and not self._is_generic_location_text(first_line):
                    record.company_name = first_line
        elif panel_text:
            address_lines = self._extract_address_lines_from_panel_text(panel_text)
            if address_lines:
                address_block = "\n".join(address_lines)
                record.address = address_block
                plz_match = re.search(r'\b(\d{5})\b', address_block)
                if plz_match:
                    record.postal_code = plz_match.group(1)
                city_match = re.search(r'\b\d{5}\s+([^\n,]+)', address_block)
                if city_match:
                    record.city = city_match.group(1).strip()
                if len(address_lines) >= 2:
                    possible_contact = address_lines[1]
                    if not re.search(r'\b\d{5}\b', possible_contact) and not re.search(r'\d', possible_contact):
                        record.contact_person = possible_contact
                if not record.company_name and address_lines:
                    first_line = address_lines[0].strip()
                    if first_line and not self._is_generic_location_text(first_line):
                        record.company_name = first_line

        if not record.company_name and panel_text:
            company_match = re.search(r'Informationen zur Bewerbung\s+(.+?)\n', panel_text, re.DOTALL)
            if company_match:
                candidate = company_match.group(1).strip()
                if 'sicherheitsabfrage' not in candidate.lower() and 'ergebnis' not in candidate.lower():
                    record.company_name = candidate

        # Always save if we have useful signal, even with partial data
        has_useful_data = (
            record.company_name or record.job_title or
            record.email or record.website or record.phone
        )
        if not has_useful_data:
            logger.debug(f"[{self.job_id}] Card {card_index} did not produce usable data")
            return None

        return record.normalize()

    async def _wait_for_application_panel(self, page: Page) -> bool:
        selectors = [
            '#detail-bewerbung-mail',
            'a#detail-bewerbung-mail',
            '#detail-bewerbung-telefon-Telefon',
            '#detail-bewerbung-url',
            '#detail-bewerbung-adresse',
            '#jobdetails-kontaktdaten-block',
            '#jobdetails-kontaktdaten-container',
            'text=Informationen zur Bewerbung',
            'text=Bewerben Sie sich',
            '[id*="detail-bewerbung"]',
            '[id*="jobdetails-kontaktdaten"]',
            'text=R??ckfragen und Bewerbung an',
            'text=Kontakt',
            'a:has-text("Jetzt bewerben")',
            'section:has(#detail-bewerbung-mail)',
            'section:has(#detail-bewerbung-telefon-Telefon)',
        ]
        try:
            visible_contact_now = await page.evaluate(
                """() => {
                    const selectors = [
                        '#detail-bewerbung-mail',
                        'a#detail-bewerbung-mail',
                        '#detail-bewerbung-telefon-Telefon',
                        '#detail-bewerbung-url',
                        '#detail-bewerbung-adresse',
                        '#detail-beschreibung-externe-url-btn',
                    ];
                    return selectors.some((sel) => {
                        const el = document.querySelector(sel);
                        if (!el) return false;
                        const text = (el.textContent || '').trim();
                        const href = el.getAttribute?.('href') || '';
                        return Boolean(text || href);
                    });
                }"""
            )
            if visible_contact_now:
                return True
        except Exception:
            pass

        for attempt in range(2):
            for selector in selectors:
                try:
                    if selector in {
                        '#jobdetails-kontaktdaten-block',
                        '#jobdetails-kontaktdaten-container',
                        '[id*="jobdetails-kontaktdaten"]',
                        'text=Informationen zur Bewerbung',
                        'text=Bewerben Sie sich',
                        'text=Kontakt',
                    }:
                        has_real_contact_fields = await page.evaluate(
                            """() => {
                                const contactSelectors = [
                                    '#detail-bewerbung-mail',
                                    'a#detail-bewerbung-mail',
                                    '#detail-bewerbung-telefon-Telefon',
                                    '#detail-bewerbung-url',
                                    '#detail-bewerbung-adresse',
                                    '[id*="detail-bewerbung"]'
                                ];
                                return contactSelectors.some((sel) => {
                                    const el = document.querySelector(sel);
                                    if (!el) return false;
                                    const text = (el.textContent || '').trim();
                                    const href = el.getAttribute?.('href') || '';
                                    return Boolean(text || href);
                                });
                            }"""
                        )
                        if not has_real_contact_fields:
                            continue
                    locator = page.locator(selector).first
                    if await locator.count() > 0:
                        try:
                            await locator.scroll_into_view_if_needed(timeout=800)
                        except Exception:
                            pass
                        await locator.wait_for(state='visible', timeout=350)
                        logger.info(f"[{self.job_id}] Application panel ready via {selector}")
                        return True
                except Exception:
                    continue
            await self._reveal_application_panel(page, attempt)
        return False

    async def _reveal_application_panel(self, page: Page, attempt: int) -> None:
        """Scroll the right-side detail area down until the application section is visible."""
        await self._open_application_panel(page)
        try:
            await page.evaluate(
                """
                (step) => {
                    const delta = 1100 + step * 220;
                    const containers = Array.from(document.querySelectorAll('main, [role="main"], section, div'))
                        .filter((el) => {
                            const style = window.getComputedStyle(el);
                            return /(auto|scroll)/.test(style.overflowY || '') &&
                                   el.scrollHeight > el.clientHeight + 40;
                        })
                        .sort((a, b) => b.clientHeight - a.clientHeight);
                    for (const el of containers.slice(0, 6)) {
                        el.scrollTop += delta;
                    }
                    window.scrollBy(0, delta);
                }
                """,
                attempt,
            )
        except Exception:
            try:
                await page.mouse.wheel(0, 1200 + attempt * 200)
            except Exception:
                pass
        await asyncio.sleep(0.2)

    async def _open_application_panel(self, page: Page) -> None:
        selectors = [
            '#detail-bewerbung-button',
            '#detail-kontakt-button',
            '#detail-bewerbung-heading',
            '#detail-bewerbung-url',
            '#jobdetails-kontaktdaten-heading',
            '#jobdetails-kontaktdaten-block',
            '[id*="detail-bewerbung"] .ba-btn-primary',
            '[id*="jobdetails-kontaktdaten"] .ba-btn-primary',
            'button.ba-btn-primary:has-text("Info zur Bewerbung")',
            'button.ba-btn-primary:has-text("Bewerben Sie sich")',
            'button.ba-btn-primary:has-text("Kontakt")',
            'button:has-text("Info zur Bewerbung")',
            'button:has-text("Informationen zur Bewerbung")',
            'button:has-text("Kontakt")',
            'button:has-text("Bewerben")',
            'a.ba-btn-primary:has-text("Info zur Bewerbung")',
            'a.ba-btn-primary:has-text("Bewerben Sie sich")',
            'a.ba-btn-primary:has-text("Kontakt")',
            'a:has-text("Info zur Bewerbung")',
            'a:has-text("Informationen zur Bewerbung")',
            'a:has-text("Kontakt")',
        ]
        for _ in range(2):
            for selector in selectors:
                try:
                    button = page.locator(selector).first
                    if await button.count() <= 0:
                        continue
                    try:
                        await button.scroll_into_view_if_needed(timeout=800)
                    except Exception:
                        pass
                    try:
                        await button.click(timeout=1200)
                    except Exception:
                        try:
                            await button.click(timeout=1000, force=True)
                        except Exception:
                            continue
                    await asyncio.sleep(0.45)
                    return
                except Exception:
                    continue
            try:
                await page.mouse.wheel(0, 900)
            except Exception:
                pass
            await asyncio.sleep(0.2)

    async def _click_result_card(self, page: Page, card: Any, card_index: int, phase: str) -> None:
        try:
            await card.scroll_into_view_if_needed(timeout=1_200)
        except Exception:
            pass

        try:
            await card.click(timeout=1_500)
            logger.info(f"[{self.job_id}] Clicked Jobsuche card {card_index} ({phase})")
            return
        except Exception as e:
            logger.debug(f"[{self.job_id}] Standard click failed on card {card_index} ({phase}): {e}")

        try:
            await card.click(timeout=1_000, force=True)
            logger.info(f"[{self.job_id}] Force-clicked Jobsuche card {card_index} ({phase})")
            return
        except Exception as e:
            logger.debug(f"[{self.job_id}] Force click failed on card {card_index} ({phase}): {e}")

        box = await card.bounding_box()
        if not box:
            raise BrowserError(f"Could not click Jobsuche card {card_index}: no bounding box")
        await page.mouse.click(
            box["x"] + min(box["width"] / 2, 80),
            box["y"] + min(box["height"] / 2, 80),
        )
        logger.info(f"[{self.job_id}] Mouse-clicked Jobsuche card {card_index} ({phase})")

    async def _get_application_panel_text(self, page: Page) -> str:
        selectors = [
            '#jobdetails-kontaktdaten-block',
            '#jobdetails-kontaktdaten-container',
            '.angebotskontakt-bewerbungsdetails-wrapper',
            '.angebotskontakt',
            '.informationen-zur-bewerbung',
            '.ba-jobdetail-kontakt',
            'section:has-text("Informationen zur Bewerbung")',
            'section:has-text("Kontakt")',
            '[id*="detail-bewerbung"]',
            '[id*="jobdetails-kontaktdaten"]',
            'div:has-text("Bewerben Sie sich")',
            'div:has-text("Kontakt")',
            'section:has-text("R??ckfragen und Bewerbung an")',
            '#detail-bewerbung-url',
            'a#detail-bewerbung-url',
        ]
        for selector in selectors:
            try:
                panel = page.locator(selector).first
                if await panel.count() > 0:
                    text = (await panel.inner_text(timeout=2000)).strip()
                    if text:
                        return text
            except Exception:
                continue
        try:
            return (await page.inner_text('body', timeout=2000)).strip()
        except Exception:
            return ''

    async def _get_application_panel_html(self, page: Page) -> str:
        selectors = [
            '#jobdetails-kontaktdaten-block',
            '#jobdetails-kontaktdaten-container',
            '.angebotskontakt-bewerbungsdetails-wrapper',
            '.angebotskontakt',
            '.informationen-zur-bewerbung',
            '.ba-jobdetail-kontakt',
            'section:has-text("Informationen zur Bewerbung")',
            'section:has-text("Kontakt")',
            '[id*="detail-bewerbung"]',
            '[id*="jobdetails-kontaktdaten"]',
            'div:has-text("Bewerben Sie sich")',
            'div:has-text("Kontakt")',
            'section:has-text("R??ckfragen und Bewerbung an")',
            '#detail-bewerbung-url',
            'a#detail-bewerbung-url',
        ]
        for selector in selectors:
            try:
                panel = page.locator(selector).first
                if await panel.count() > 0:
                    html = await panel.inner_html(timeout=2000)
                    if html:
                        return html
            except Exception:
                continue
        return ''

    async def _extract_application_address(self, page: Page) -> Optional[str]:
        selectors = [
            '[id="detail-bewerbung-adresse"]',
            '[id*="detail-bewerbung-adresse"]',
            '#jobdetails-kontaktdaten-container [id*="detail-bewerbung-adresse"]',
            '.angebotskontakt [id*="detail-bewerbung-adresse"]',
            'section:has-text("Informationen zur Bewerbung")',
        ]
        for selector in selectors:
            try:
                block = page.locator(selector).first
                if await block.count() <= 0:
                    continue
                value = (await block.inner_text(timeout=2000)).strip()
                if not value:
                    continue
                if 'Informationen zur Bewerbung' in value:
                    addr = block.locator('#detail-bewerbung-adresse, [id*="detail-bewerbung-adresse"]').first
                    if await addr.count() > 0:
                        addr_value = (await addr.inner_text(timeout=1000)).strip()
                        if addr_value:
                            return addr_value
                    lines = [line.strip() for line in value.splitlines() if line.strip()]
                    if len(lines) >= 4:
                        return '\n'.join(lines[1:5])
                return value
            except Exception:
                continue
        return None

    async def _extract_application_email(self, page: Page) -> Optional[str]:
        panel_selectors = [
            '#jobdetails-kontaktdaten-block',
            '#jobdetails-kontaktdaten-container',
            '.angebotskontakt-bewerbungsdetails-wrapper',
            '.angebotskontakt',
            'section:has(#detail-bewerbung-mail)',
            'section:has-text("Informationen zur Bewerbung")',
        ]
        link_selectors = [
            '#detail-bewerbung-mail',
            'a#detail-bewerbung-mail',
            'a[href^="mailto:"]',
            'a:has-text("E-Mail")',
            'p:has-text("per E-Mail") a[href^="mailto:"]',
            'p:has-text("E-Mail an") a[href^="mailto:"]',
        ]
        for panel_selector in panel_selectors:
            try:
                panel = page.locator(panel_selector).first
                if await panel.count() <= 0:
                    continue
                for selector in link_selectors:
                    link = panel.locator(selector).first
                    if await link.count() <= 0:
                        continue
                    href = await link.get_attribute('href', timeout=2000)
                    if href and href.lower().startswith('mailto:'):
                        candidate = href.split(':', 1)[-1].split('?', 1)[0].strip()
                        if candidate:
                            return candidate.lower()
                    value = (await link.inner_text(timeout=2000)).strip()
                    if value and '@' in value:
                        return value.lower()
            except Exception:
                continue
        try:
            panel_html = await self._get_application_panel_html(page)
            match = re.search(r"mailto:([^\"'?<>\s]+)", panel_html, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip().lower()
        except Exception:
            pass
        for selector in ('#detail-bewerbung-mail', 'a#detail-bewerbung-mail'):
            try:
                link = page.locator(selector).first
                if await link.count() <= 0:
                    continue
                href = await link.get_attribute('href', timeout=2000)
                if href and href.lower().startswith('mailto:'):
                    candidate = href.split(':', 1)[-1].split('?', 1)[0].strip()
                    if candidate:
                        return candidate.lower()
                value = (await link.inner_text(timeout=2000)).strip()
                if value and '@' in value:
                    return value.lower()
            except Exception:
                continue
        return None

    async def _extract_application_website(self, page: Page) -> Optional[str]:
        selectors = [
            'a#detail-beschreibung-externe-url-btn',
            'a[id="detail-beschreibung-externe-url-btn"]',
            'a#detail-bewerbung-url',
            'a[id="detail-bewerbung-url"]',
            'a[id^="agdarstellung-websitelink-"]',
            'a:has-text("Internetseite des Arbeitgebers")',
            'a:has-text("Externe Seite öffnen")',
            'a[target="_blank"]:has-text("Arbeitgebers")',
            'a[target="_blank"][id*="externe-url"]',
        ]
        for selector in selectors:
            try:
                link = page.locator(selector).first
                if await link.count() <= 0:
                    continue
                href = await link.get_attribute('href', timeout=2000)
                if href:
                    if href.lower().startswith('mailto:'):
                        continue
                    normalized = normalize_website(href)
                    if not self._is_untrusted_website_candidate(normalized):
                        return normalized
            except Exception:
                continue
        return None

    async def _extract_application_website_candidates(self, page: Page) -> list[str]:
        selectors = [
            '#detail-beschreibung-externe-url-btn',
            '#detail-beschreibung',
            '#detail-beschreibung-container',
            '[id*="detail-beschreibung"]',
            '#detail-bewerbung-url',
            'a#detail-bewerbung-url',
            '#jobdetails-kontaktdaten-block',
            '#jobdetails-kontaktdaten-container',
            '.angebotskontakt-bewerbungsdetails-wrapper',
            '.angebotskontakt',
            '.informationen-zur-bewerbung',
            '.ba-jobdetail-kontakt',
            '[id*="detail-bewerbung"]',
            'section:has-text("Informationen zur Bewerbung")',
            'section:has-text("Kontakt")',
        ]
        candidates: list[str] = []

        async def _collect(locator) -> None:
            try:
                anchors = locator.locator('a[href^="http"]')
                count = await anchors.count()
                for i in range(min(count, 10)):
                    href = await anchors.nth(i).get_attribute('href', timeout=2000)
                    if href:
                        if href.lower().startswith('mailto:'):
                            continue
                        normalized = normalize_website(href)
                        if not self._is_untrusted_website_candidate(normalized):
                            candidates.append(normalized)
            except Exception:
                pass

        for selector in selectors:
            try:
                panel = page.locator(selector).first
                if await panel.count() <= 0:
                    continue
                await _collect(panel)
            except Exception:
                continue

        return self._dedupe_websites(candidates)

    def _choose_preferred_website(self, candidates: list[str]) -> Optional[str]:
        for url in candidates:
            if not self._is_untrusted_website_candidate(url):
                return url
        return None

    def _dedupe_websites(self, urls: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for url in urls:
            if not url:
                continue
            if str(url).lower().startswith("mailto:"):
                continue
            normalized = normalize_website(url)
            if normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    def _is_job_portal_domain(self, url: str) -> bool:
        try:
            domain = urlparse(url).netloc.lower().lstrip("www.")
            return any(
                domain == known_domain or domain.endswith(f".{known_domain}")
                for known_domain in _KNOWN_JOB_PORTAL_DOMAINS
            )
        except Exception:
            return False

    def _is_untrusted_website_candidate(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().lstrip("www.")
            path = (parsed.path or "").lower()
            query = (parsed.query or "").lower()
            if any(
                domain == known_domain or domain.endswith(f".{known_domain}")
                for known_domain in _KNOWN_JOB_PORTAL_DOMAINS
            ):
                return True
            if domain.startswith(("bewerbung.", "jobs.", "job.", "career.", "careers.", "karriere.")):
                return True
            if "jobsuche" in path or "kundennummer=" in query:
                return True
            if "ag-darstellung-ui" in path or "/vermittlung/" in path:
                return True
            if "/apply" in path or "jobposting" in path:
                return True
            return False
        except Exception:
            return True

    def _extract_address_lines_from_panel_text(self, panel_text: str) -> list[str]:
        if not panel_text:
            return []

        lines = [line.strip() for line in panel_text.splitlines() if line.strip()]
        result: list[str] = []
        capture = False

        for line in lines:
            lower = line.lower()
            if lower in {"informationen zur bewerbung", "kontaktadresse"}:
                capture = True
                continue
            if not capture:
                continue
            if lower.startswith(("telefon:", "e-mail:", "bewerben sie sich:", "oder", "sonstige angaben")):
                break
            if lower in {"per e-mail", "per post"}:
                break
            result.append(line)

        return result

    async def _enrich_from_website_candidates(self, record: LeadRecord) -> None:
        if not self.crawler:
            return

        candidates = [
            website
            for website in self._dedupe_websites([record.website or ""])
            if not self._is_untrusted_website_candidate(website)
        ]
        if record.website and self._is_untrusted_website_candidate(record.website):
            logger.info(
                f"[{self.job_id}] Website candidate is untrusted ({record.website}); "
                "skipping email crawl for portal/listing pages"
            )

        for website in candidates:
            email, source, socials = await self.crawler.find_email(
                website,
                record.company_name,
                self.job_id,
                bypass_cache=False,
            )
            if email:
                record.email = email
                record.email_source_page = source
                if record.website and self._is_untrusted_website_candidate(record.website):
                    record.website = website
                return

    def _is_generic_location_text(self, text: str) -> bool:
        normalized = " ".join((text or "").strip().lower().split())
        return normalized in {
            "",
            "ort",
            "standort",
            "location",
            "arbeitsort",
            "arbeitsplatz",
        }

    def _extract_phone_candidate(self, text: str) -> Optional[str]:
        if not text:
            return None

        for match in _PHONE_PATTERN.finditer(text):
            raw_candidate = match.group(0).strip()
            digits_in_raw = re.sub(r"\D", "", raw_candidate)

            # Free-text extraction is more error-prone than tel: links.
            # Reject long ID-like digit runs such as Jobsuche offer IDs.
            if not any(sep in raw_candidate for sep in ("+", " ", "/", "-", "(", ")")) and len(digits_in_raw) >= 10:
                continue
            if digits_in_raw.startswith(("10000", "10001")):
                continue

            candidate = normalize_phone(raw_candidate)
            digits = re.sub(r"\D", "", candidate)

            # Reject bare publication-date style values like 01082027.
            if re.fullmatch(r"\d{8}", digits):
                continue

            if digits and len(digits) >= 6:
                return candidate

        return None

    def _extract_publication_candidate(self, text: str) -> Optional[str]:
        if not text:
            return None

        date_match = _DATE_PATTERN.search(text)
        if date_match:
            return date_match.group(1)

        iso_match = _ISO_DATE_PATTERN.search(text)
        if iso_match:
            return iso_match.group(1)

        for line in [line.strip() for line in text.splitlines() if line.strip()]:
            lower = line.lower()
            if any(token in lower for token in ("heute", "gestern", "veröffentlicht", "veroeffentlicht", "vor ", "tage", "stunden", "minuten")):
                return line

        return None

    def _extract_labeled_contact_fields(self, text: str) -> dict[str, str]:
        if not text:
            return {}

        fields: dict[str, str] = {}
        normalized_text = text.replace("\xa0", " ")

        email_match = re.search(
            r"E-?Mail\s*:\s*([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})",
            normalized_text,
            re.IGNORECASE,
        )
        if email_match:
            fields["email"] = email_match.group(1).strip().lower()

        phone_match = re.search(
            r"Telefon\s*:\s*([+()\d][\d\s()./\-]{7,})",
            normalized_text,
            re.IGNORECASE,
        )
        if phone_match:
            phone = normalize_phone(phone_match.group(1).strip())
            if phone:
                fields["phone"] = phone

        website_match = re.search(
            r"Web\s*:\s*((?:https?://|www\.)[^\s<>\"]+)",
            normalized_text,
            re.IGNORECASE,
        )
        if website_match:
            website = normalize_website(website_match.group(1).strip())
            if website and not self._is_untrusted_website_candidate(website):
                fields["website"] = website

        return fields

    def _extract_visible_detail_fields(self, text: str) -> dict[str, str]:
        if not text:
            return {}

        fields: dict[str, str] = {}
        normalized = text.replace("\xa0", " ")

        city_patterns = [
            r"\bOrt\s*\n\s*([^\n]{2,60})",
            r"\bArbeitsort\s*\n\s*([^\n]{2,60})",
            r"\bStandort\s*\n\s*([^\n]{2,60})",
        ]
        for pattern in city_patterns:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                if candidate and not self._is_generic_location_text(candidate):
                    fields["city"] = candidate
                    break

        publication_patterns = [
            r"(Heute veröffentlicht)",
            r"(Gestern veröffentlicht)",
            r"(Vor\s+\d+\s+Tagen?\s+veröffentlicht)",
            r"(Vor\s+\d+\s+Stunden?\s+veröffentlicht)",
            r"(Vor\s+\d+\s+Minuten?\s+veröffentlicht)",
        ]
        for pattern in publication_patterns:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                fields["publication_date"] = match.group(1).strip()
                break

        return fields

    def _extract_city_candidate(self, text: str, *, company_name: str = "", job_title: str = "") -> Optional[str]:
        if not text:
            return None

        postal_match = re.search(r"\b\d{5}\s+([A-ZÄÖÜa-zäöüß][^\n,]{1,60})", text)
        if postal_match:
            return postal_match.group(1).strip()

        ignored_literals = {
            "",
            "ort",
            "standort",
            "location",
            (company_name or "").strip().lower(),
            (job_title or "").strip().lower(),
        }
        ignored_keywords = (
            "veröffentlicht",
            "veroeffentlicht",
            "heute",
            "gestern",
            "tage",
            "stunden",
            "minuten",
            "vollzeit",
            "teilzeit",
            "anstellungsart",
            "benötigter schulabschluss",
            "pflegefach",
            "ausbildung",
            "kontakt",
            "bewerben",
            "pdf",
            "drucken",
            "status",
            "merken",
            "notiz",
        )

        for raw_line in text.splitlines():
            line = " ".join(raw_line.strip().split())
            lower = line.lower()
            if lower in ignored_literals or not line:
                continue
            if self._is_generic_location_text(line):
                continue
            if any(keyword in lower for keyword in ignored_keywords):
                continue
            if re.search(r"\d", line):
                continue
            if len(line) > 60:
                continue
            if not re.fullmatch(r"[A-Za-zÄÖÜäöüß .'\-/]+", line):
                continue
            return line

        return None

    async def _extract_card_text(self, card: Any, selectors: list[str]) -> Optional[str]:
        for selector in selectors:
            try:
                node = card.locator(selector).first
                if await node.count() <= 0:
                    continue
                text = (await node.inner_text(timeout=2000)).strip()
                if text:
                    return text
            except Exception:
                continue
        return None

    async def _extract_card_href(self, card: Any) -> Optional[str]:
        try:
            href = await card.locator(LISTING_SEL).first.get_attribute('href', timeout=2000)
            if href:
                return href if href.startswith('http') else DETAIL_BASE + href
        except Exception:
            return None
        return None

    async def _fill_search_field(
        self, page: Page, selectors: str, value: str, field_name: str,
    ) -> None:
        """Fill a form field using multiple selector fallbacks."""
        try:
            field = page.locator(selectors).first
            await field.wait_for(state="visible", timeout=8_000)
            await field.click()
            await field.fill(value)
            await asyncio.sleep(0.08)
            logger.info(f"[{self.job_id}] {field_name} field set to '{value}'")
        except Exception as e:
            logger.warning(f"[{self.job_id}] Could not fill {field_name}: {e}")

    async def _collect_listing_hrefs(self, page: Page) -> list[str]:
        """Scroll to load listings and collect unique detail page URLs."""
        previously_counted = -1
        unchanged_iterations = 0
        max_unchanged = 5
        hrefs: list[str] = []
        
        logger.info(f"[{self.job_id}] Collecting up to {self.config.max_results} listings...")

        while not self._cancelled:
            while self._paused and not self._cancelled:
                await asyncio.sleep(0.5)

            # Scroll bit-by-bit to trigger lazy loading more reliably
            for _ in range(3):
                await page.mouse.wheel(0, 2000)
                await asyncio.sleep(0.3)
            
            await asyncio.sleep(1.0)

            count = await page.locator(LISTING_SEL).count()
            
            if count != previously_counted:
                logger.info(f"[{self.job_id}] Listings loaded so far: {count}")
                unchanged_iterations = 0
            else:
                unchanged_iterations += 1
                logger.debug(f"[{self.job_id}] No new listings (iteration {unchanged_iterations}/{max_unchanged})")

            if count >= self.config.max_results:
                logger.info(f"[{self.job_id}] Reached target count: {self.config.max_results}")
                break

            if unchanged_iterations >= max_unchanged:
                # Try "load more" button before giving up
                clicked_more = await self._click_load_more(page)
                if not clicked_more:
                    logger.info(f"[{self.job_id}] No more listings to load or stuck. Total: {count}")
                    break
                else:
                    unchanged_iterations = 0 # Reset if we clicked something
            else:
                # Proactively try to click "load more" if it's visible
                await self._click_load_more(page)

            previously_counted = count

        # Collect hrefs
        all_links = await page.locator(LISTING_SEL).all()
        all_links = all_links[: self.config.max_results]

        for link in all_links:
            try:
                href = await link.get_attribute("href", timeout=2000)
                if href:
                    full = href if href.startswith("http") else DETAIL_BASE + href
                    hrefs.append(full)
            except Exception:
                pass

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for h in hrefs:
            if h not in seen:
                seen.add(h)
                unique.append(h)
        return unique

    async def _click_load_more(self, page: Page) -> bool:
        """Try to click a 'load more' button. Returns True if clicked."""
        try:
            # Jobsuche mostly uses infinite scroll, but fallback buttons exist
            more_btn = page.locator(
                'button:has-text("Weitere"), '
                'button:has-text("Mehr laden"), '
                'button:has-text("Mehr anzeigen"), '
                'button:has-text("Mehr Ergebnisse")'
            )
            if await more_btn.first.is_visible(timeout=1_500):
                await more_btn.first.click()
                await asyncio.sleep(1.5)
                return True
        except Exception:
            pass
        return False

    async def _extract_text_with_fallbacks(
        self, page: Page, selectors: list[str],
    ) -> Optional[str]:
        """Try multiple selectors and return the first non-empty text found."""
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    text = (await loc.inner_text(timeout=2000)).strip()
                    if text:
                        return text
            except Exception:
                continue
        return None

    async def _extract_website_url(self, page: Page) -> Optional[str]:
        """Extract the first external (non-arbeitsagentur) website URL."""
        try:
            # Prefer explicit website links
            ext_links = page.locator(
                'a[href^="http"]:not([href*="arbeitsagentur"])'
                ':not([href*="google"])'
                ':not([href*="facebook"])'
                ':not([href*="twitter"])'
                ':not([href*="linkedin"])'
                ':not([href*="instagram"])'
                ':not([href*="youtube"])'
            )
            count = await ext_links.count()
            for i in range(min(count, 5)):
                href = await ext_links.nth(i).get_attribute("href", timeout=2000)
                if href and not href.lower().startswith("mailto:") and not href.endswith((".pdf", ".jpg", ".png")):
                    return normalize_website(href)
        except Exception:
            pass
        return None

    async def _handle_captcha(self, page: Page) -> bool:
        """Detect CAPTCHA and wait for human to solve it via Remote Desktop."""
        try:
            is_blocked = await self._is_security_challenge_present(page)
        except Exception:
            return False

        if not is_blocked:
            return False

        try:
            body_text = (await page.inner_text("body", timeout=1000)).lower()
            has_captcha_error = any(sig in body_text for sig in CAPTCHA_ERROR_SIGNALS)
        except Exception:
            has_captcha_error = False

        if has_captcha_error:
            logger.warning(f"[{self.job_id}] Jobsuche security challenge failed to load - retrying")
            event_bus.emit(
                event_bus.JOB_LOG,
                job_id=self.job_id,
                message="Jobsuche security check failed to load. Retrying...",
                level="WARNING",
            )
            if await self._recover_security_challenge(page):
                try:
                    still_blocked = await self._is_security_challenge_present(page)
                    if not still_blocked:
                        await self._restore_default_view(page)
                        logger.info(f"[{self.job_id}] CAPTCHA resolved - resuming")
                        return True
                except Exception:
                    pass

        if not self.session.settings.default_headless:
            await self._prepare_captcha_view(page)
            logger.warning(f"[{self.job_id}] CAPTCHA detected - waiting for resolution directly in browser...")
            event_bus.emit(
                event_bus.JOB_LOG,
                job_id=self.job_id,
                message="CAPTCHA detected. Please solve it directly in the browser.",
                level="WARNING",
            )
            clear_checks = 0
            for _ in range(120):
                await asyncio.sleep(2)
                try:
                    if await self._is_security_challenge_error(page):
                        await self._recover_security_challenge(page)
                    if not await self._is_security_challenge_present(page):
                        clear_checks += 1
                    else:
                        clear_checks = 0
                    if clear_checks >= 2:
                        await self._restore_default_view(page)
                        logger.info(f"[{self.job_id}] CAPTCHA resolved - resuming")
                        return True
                except Exception:
                    break
            return True

        logger.warning(f"[{self.job_id}] Headless CAPTCHA detected - requesting headed solver.")
        if (
            self._last_solver_url == page.url
            and (time.time() - self._last_solver_completed_at) < 20
        ):
            logger.info(f"[{self.job_id}] Recent solver already completed for this page; waiting for browser state to settle...")
            await asyncio.sleep(2.0)
            if not await self._is_security_challenge_present(page):
                logger.info(f"[{self.job_id}] CAPTCHA cleared after settle wait; skipping duplicate solver request.")
                return True

        event_bus.emit(
            event_bus.JOB_LOG,
            job_id=self.job_id,
            message="CAPTCHA detected. Opening a real browser window to solve it.",
            level="WARNING",
        )

        event_bus.subscribe(event_bus.SOLVER_COMPLETED, self._on_solver_completed)
        self._interaction_loop = asyncio.get_running_loop()

        while not self._interaction_queue.empty():
            try:
                self._interaction_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        try:
            cookies = await page.context.cookies()
            event_bus.emit(
                event_bus.SOLVER_REQUESTED,
                job_id=self.job_id,
                url=page.url,
                cookies=cookies,
            )

            try:
                msg = await asyncio.wait_for(self._interaction_queue.get(), timeout=600.0)
                if msg.get("type") == "solver_complete":
                    new_cookies = msg.get("cookies", [])
                    if new_cookies:
                        await page.context.add_cookies(new_cookies)
                    self._last_solver_url = page.url
                    self._last_solver_completed_at = time.time()
                    logger.info(f"[{self.job_id}] Jobsuche solver cookies synced; resuming browser flow...")
                    await asyncio.sleep(0.75)
                    logger.info(f"[{self.job_id}] CAPTCHA resolved via headed solver!")
                    return True
            except asyncio.TimeoutError:
                logger.warning(f"[{self.job_id}] Headed solver timed out after 10m")
        finally:
            self._interaction_loop = None
            event_bus.unsubscribe(event_bus.SOLVER_COMPLETED, self._on_solver_completed)

        return True

    async def _is_security_challenge_present(self, page: Page) -> bool:
        try:
            return await page.evaluate("""() => {
                const text = document.body.innerText.toLowerCase();
                if (document.title.toLowerCase().includes('sicherheitsabfrage')) return true;

                const h1 = document.querySelector('h1');
                if (h1 && h1.innerText.toLowerCase().includes('sicherheitsabfrage')) return true;

                if (document.querySelector('iframe[src*="captcha"]')) return true;
                if (document.querySelector('iframe[src*="geo.captcha"]')) return true;
                if (document.querySelector('#datadome-slider')) return true;
                if (document.querySelector('#captchaForm')) return true;
                if (document.querySelector('#kontaktdaten-captcha-input')) return true;
                if (document.querySelector('#kontaktdaten-captcha-absenden-button')) return true;
                if (document.querySelector('#jobdetails-kontaktdaten-block #captchaForm')) return true;
                if (document.querySelector('[id*="kontaktdaten-captcha"]')) return true;

                if (text.includes('ich bin kein roboter')) return true;
                if (text.includes('verify you are human')) return true;
                if (text.includes('beim laden der sicherheitsabfrage')) return true;

                return false;
            }""")
        except Exception:
            return False

    async def _prepare_captcha_view(self, page: Page) -> None:
        """Zoom out and scroll the Jobsuche security panel into view."""
        try:
            await page.evaluate(
                """
                () => {
                    document.documentElement.style.zoom = '0.85';
                    const selectors = [
                        '#captchaForm',
                        '#kontaktdaten-captcha-input',
                        '#kontaktdaten-captcha-image-container',
                        '#jobdetails-kontaktdaten-block',
                        '#jobdetails-kontaktdaten-container',
                        'form[id*="captcha"]',
                        '[id*="kontaktdaten-captcha"]',
                    ];
                    let target = null;
                    for (const selector of selectors) {
                        const node = document.querySelector(selector);
                        if (node) {
                            target = node;
                            break;
                        }
                    }
                    if (!target) {
                        const containsCaptcha = (el) =>
                            ((el.textContent || '').toLowerCase().includes('sicherheitsabfrage'));
                        const candidates = Array.from(document.querySelectorAll('section, div, article'));
                        target = candidates.find(containsCaptcha) || null;
                    }
                    if (!target) {
                        return;
                    }
                    let node = target;
                    while (node) {
                        const style = window.getComputedStyle(node);
                        const scrollable =
                            /(auto|scroll)/.test(style.overflowY || '') &&
                            node.scrollHeight > node.clientHeight + 10;
                        if (scrollable) {
                            const offset = target.getBoundingClientRect().top - node.getBoundingClientRect().top;
                            node.scrollTop = Math.max(0, offset - node.clientHeight * 0.08);
                        }
                        node = node.parentElement;
                    }
                    target.scrollIntoView({ block: 'start', inline: 'nearest' });
                    window.scrollBy(0, -28);
                }
                """
            )
        except Exception as e:
            logger.debug(f"[{self.job_id}] Could not prepare captcha view: {e}")

    async def _capture_captcha_frame(self, page: Page) -> bytes:
        selectors = [
            '#captchaForm',
            '#jobdetails-kontaktdaten-block',
            '#jobdetails-kontaktdaten-container',
            '#kontaktdaten-captcha-image-container',
            '[id*="kontaktdaten-captcha"]',
            'form[id*="captcha"]',
        ]
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count() <= 0:
                    continue
                await locator.scroll_into_view_if_needed(timeout=1000)
                return await locator.screenshot(type="jpeg", quality=85)
            except Exception:
                continue
        return await page.screenshot(type="jpeg", quality=65)

    async def _apply_captcha_text(self, page: Page, text: str) -> None:
        selectors = [
            '#kontaktdaten-captcha-input',
            'input[id*="captcha"]',
            '#captchaForm input[type="text"]',
        ]
        for selector in selectors:
            try:
                field = page.locator(selector).first
                if await field.count() <= 0:
                    continue
                await field.click(timeout=1_000)
                try:
                    await field.fill("", timeout=1_000)
                except Exception:
                    await page.keyboard.press("Control+A")
                    await page.keyboard.press("Backspace")
                await field.type(text, delay=40, timeout=2_000)

                submit_selectors = [
                    '#kontaktdaten-captcha-absenden-button',
                    '#captchaForm button[type="submit"]',
                    'button[id*="captcha"][type="submit"]',
                ]
                for submit_selector in submit_selectors:
                    try:
                        button = page.locator(submit_selector).first
                        if await button.count() <= 0:
                            continue
                        disabled = await button.get_attribute("disabled")
                        aria_disabled = await button.get_attribute("aria-disabled")
                        if disabled is None and aria_disabled != "true":
                            await button.click(timeout=1_000)
                            return
                    except Exception:
                        continue
                await page.keyboard.press("Enter")
                return
            except Exception:
                continue

        await page.keyboard.type(text)

    async def _restore_default_view(self, page: Page) -> None:
        try:
            await page.evaluate("() => { document.documentElement.style.zoom = '1'; }")
        except Exception:
            pass

    async def _is_security_challenge_error(self, page: Page) -> bool:
        try:
            text = (await page.inner_text("body", timeout=2000)).lower()
        except Exception:
            return False
        return any(sig in text for sig in CAPTCHA_ERROR_SIGNALS)

    async def _recover_security_challenge(self, page: Page) -> bool:
        """Retry a broken Jobsuche security-check page before requiring manual action."""
        for attempt in range(3):
            try:
                retry_btn = page.locator(
                    'button:has-text("Erneut versuchen"), a:has-text("Erneut versuchen")'
                ).first
                if await retry_btn.count() > 0:
                    await retry_btn.click(timeout=3_000)
                else:
                    await page.reload(wait_until="domcontentloaded", timeout=20_000)
                await asyncio.sleep(2.0)
                if not await self._is_security_challenge_error(page):
                    return True
            except Exception as e:
                logger.debug(
                    f"[{self.job_id}] Security challenge recovery attempt {attempt + 1} failed: {e}"
                )
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=20_000)
                    await asyncio.sleep(2.0)
                    if not await self._is_security_challenge_error(page):
                        return True
                except Exception:
                    pass
        return False

    def _log_skip(self, url: str, reason: str) -> None:
        """Log and emit a structured event when a listing is skipped."""
        logger.debug(f"[{self.job_id}] Skipped {url}: {reason}")
        event_bus.emit(
            event_bus.JOB_LOG,
            job_id=self.job_id,
            message=f"Skipped: {reason}",
            level="DEBUG",
        )

    def _build_query(self) -> str:
        return " · ".join(filter(None, [
            self.config.job_title,
            self.config.city or self.config.region,
            self.config.country,
        ]))
