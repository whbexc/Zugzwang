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
import re
from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional

if TYPE_CHECKING:
    from playwright.async_api import Page
else:
    Page = Any

from .browser import BrowserSession, BrowserError
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

# Regex for German phone numbers (international and domestic formats)
_PHONE_PATTERN = re.compile(
    r"""
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


class JobsucheScraper:

    def __init__(self, session: BrowserSession, config: SearchConfig, job_id: str):
        self.session = session
        self.config = config
        self.job_id = job_id
        self.crawler = WebsiteEmailCrawler(session) if config.scrape_emails else None
        self._cancelled = False
        self._paused = False
        self._total_errors = 0

    def cancel(self):  self._cancelled = True
    def pause(self):   self._paused = True
    def resume(self):  self._paused = False

    # ── Main scrape loop ──────────────────────────────────────────────────

    async def scrape(self) -> AsyncGenerator[LeadRecord, None]:
        location = self.config.city or self.config.region or self.config.country
        logger.info(
            f"[{self.job_id}] Jobsuche scrape: '{self.config.job_title}' "
            f"in '{location}'"
        )

        page = await self.session.new_page()
        page.set_default_timeout(60_000)

        try:
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

                    if self.crawler and record.website and not record.email:
                        email, source = await self.crawler.find_email(
                            record.website, record.company_name, self.job_id
                        )
                        if email:
                            record.email = email
                            record.email_source_page = source

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
            await self.session.screenshot_on_failure(page, "crash")
            raise
        finally:
            if self._total_errors > 0:
                logger.warning(
                    f"[{self.job_id}] Scrape finished with {self._total_errors} errors"
                )
            try:
                await page.close()
            except Exception:
                pass

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
        if location_text:
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
            phone_match = _PHONE_PATTERN.search(full_text)
            if phone_match:
                record.phone = normalize_phone(phone_match.group(0).strip())

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

        return record

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

                if self.crawler and record.website and not record.email:
                    email, source = await self.crawler.find_email(
                        record.website, record.company_name, self.job_id
                    )
                    if email:
                        record.email = email
                        record.email_source_page = source

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
            # Short sleep to let the DOM settle
            await asyncio.sleep(1.0)
        except Exception:
            # Results might take longer or there may be none
            logger.debug(f"[{self.job_id}] Results selector timeout - continuing")
            await asyncio.sleep(2.0)

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
            await asyncio.sleep(0.5)

            option = page.locator(
                f"#angebotsart-dropdownList li:has-text('{target}')"
            ).first
            await option.wait_for(state="visible", timeout=8_000)
            await option.click()
            await asyncio.sleep(0.5)
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
        """Try to reveal more result cards in the left results column."""
        try:
            last_card = page.locator(RESULT_CARD_SEL).nth(max(previous_count - 1, 0))
            if await last_card.count() > 0:
                await last_card.scroll_into_view_if_needed(timeout=1_200)
                box = await last_card.bounding_box()
                if box:
                    await page.mouse.move(box['x'] + min(box['width'] / 2, 60), box['y'] + min(box['height'] / 2, 60))
                    await page.mouse.wheel(0, 2200)
            else:
                await page.mouse.wheel(0, 2200)
        except Exception:
            await page.mouse.wheel(0, 2200)

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
                await asyncio.sleep(0.25)
        panel_ready = await self._wait_for_application_panel(page)

        detail_url = await self._extract_card_href(card)
        record = LeadRecord(
            source_type=SourceType.JOBSUCHE,
            search_query=self._build_query(),
            source_url=detail_url or page.url,
            country=self.config.country,
        )

        record.job_title = await self._extract_card_text(card, [
            'h2', 'h3', '[class*="titel"]', '[class*="title"]',
        ]) or ''
        record.company_name = await self._extract_card_text(card, [
            '[class*="arbeitgeber"]', '[class*="company"]', '[class*="firma"]',
        ]) or ''

        if not record.job_title:
            record.job_title = await self._extract_text_with_fallbacks(page, ['h1', 'h2']) or ''
        if not record.company_name:
            record.company_name = await self._extract_text_with_fallbacks(page, [
                'h1 + div',
                'h2 + div',
                '[class*="arbeitgeber"]',
                '[class*="company"]',
            ]) or ''

        record.website = await self._extract_application_website(page) or record.website

        if not panel_ready:
            logger.info(
                f"[{self.job_id}] Application panel not visible for card {card_index}; continuing with visible detail data"
            )
            return record if (record.company_name or record.job_title or record.website) else None

        panel_text = await self._get_application_panel_text(page)
        panel_html = await self._get_application_panel_html(page)

        emails = deduplicate_emails(extract_emails_from_html(panel_html or panel_text or ''))
        if emails:
            record.email = emails[0]
            record.email_source_page = detail_url or page.url

        phone_match = _PHONE_PATTERN.search(panel_text or '')
        if phone_match:
            record.phone = normalize_phone(phone_match.group(0).strip())

        address_block = await self._extract_application_address(page)
        if address_block:
            record.address = address_block
            plz_match = re.search(r'\b(\d{5})\b', address_block)
            if plz_match:
                record.postal_code = plz_match.group(1)
            city_match = re.search(r'\d{5}\s+([^\n,]+)', address_block)
            if city_match:
                record.city = city_match.group(1).strip()

        if not record.company_name and panel_text:
            company_match = re.search(r'Informationen zur Bewerbung\s+(.+?)\n', panel_text, re.DOTALL)
            if company_match:
                record.company_name = company_match.group(1).strip()

        if not record.company_name:
            company_link_text = await self._extract_card_text(card, ['a[href*="jobdetail"]', 'a'])
            if company_link_text:
                record.company_name = company_link_text

        if not record.company_name and not record.job_title:
            logger.debug(f"[{self.job_id}] Card {card_index} did not produce usable data")
            return None

        return record

    async def _wait_for_application_panel(self, page: Page) -> bool:
        selectors = [
            'text=Informationen zur Bewerbung',
            'text=Bewerben Sie sich',
            '[id*="detail-bewerbung"]',
            'text=Rückfragen und Bewerbung an',
            'text=Kontakt',
            'a:has-text("Jetzt bewerben")',
        ]
        for attempt in range(2):
            for selector in selectors:
                try:
                    locator = page.locator(selector).first
                    if await locator.count() > 0:
                        try:
                            await locator.scroll_into_view_if_needed(timeout=800)
                        except Exception:
                            pass
                        await locator.wait_for(state='visible', timeout=900)
                        logger.info(f"[{self.job_id}] Application panel ready via {selector}")
                        return True
                except Exception:
                    continue
            await self._reveal_application_panel(page, attempt)
        return False

    async def _reveal_application_panel(self, page: Page, attempt: int) -> None:
        """Scroll the right-side detail area down until the application section is visible."""
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
            'section:has-text("Informationen zur Bewerbung")',
            '[id*="detail-bewerbung"]',
            'div:has-text("Bewerben Sie sich")',
            'section:has-text("Rückfragen und Bewerbung an")',
            'section:has-text("Kontakt")',
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
            'section:has-text("Informationen zur Bewerbung")',
            '[id*="detail-bewerbung"]',
            'div:has-text("Bewerben Sie sich")',
            'section:has-text("Rückfragen und Bewerbung an")',
            'section:has-text("Kontakt")',
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
            'section:has-text("Informationen zur Bewerbung")',
        ]
        for selector in selectors:
            try:
                block = page.locator(selector).first
                if await block.count() <= 0:
                    continue
                text = (await block.inner_text(timeout=2000)).strip()
                if not text:
                    continue
                if 'Informationen zur Bewerbung' in text:
                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                    if len(lines) >= 4:
                        return '\n'.join(lines[1:5])
                return text
            except Exception:
                continue
        return None

    async def _extract_application_website(self, page: Page) -> Optional[str]:
        selectors = [
            'a[id^="agdarstellung-websitelink-"]',
            'a:has-text("Internetseite des Arbeitgebers")',
            'a:has-text("Externe Seite öffnen")',
            'a[target="_blank"]:has-text("Arbeitgebers")',
        ]
        for selector in selectors:
            try:
                link = page.locator(selector).first
                if await link.count() <= 0:
                    continue
                href = await link.get_attribute('href', timeout=2000)
                if href:
                    return normalize_website(href)
            except Exception:
                continue
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
            await asyncio.sleep(0.3)
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
            more_btn = page.locator(
                'button:has-text("Weitere"), '
                'button:has-text("Mehr laden"), '
                'button:has-text("Mehr Ergebnisse")'
            )
            if await more_btn.first.is_visible(timeout=2_000):
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
                if href and not href.endswith((".pdf", ".jpg", ".png")):
                    return normalize_website(href)
        except Exception:
            pass
        return None

    async def _handle_captcha(self, page: Page) -> bool:
        """Detect CAPTCHA and wait for human to solve it."""
        try:
            body_text = (await page.inner_text("body", timeout=2000)).lower()
        except Exception:
            return False

        has_captcha = any(sig in body_text for sig in CAPTCHA_SIGNALS)
        has_captcha_error = any(sig in body_text for sig in CAPTCHA_ERROR_SIGNALS)
        if not has_captcha and not has_captcha_error:
            return False

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
                    body_text = (await page.inner_text("body", timeout=2000)).lower()
                except Exception:
                    return True
                has_captcha = any(sig in body_text for sig in CAPTCHA_SIGNALS)
                has_captcha_error = any(sig in body_text for sig in CAPTCHA_ERROR_SIGNALS)
                if not has_captcha and not has_captcha_error:
                    logger.info(f"[{self.job_id}] Jobsuche security challenge recovered")
                    return True

        await self._prepare_captcha_view(page)
        logger.warning(f"[{self.job_id}] CAPTCHA detected — waiting for resolution…")
        event_bus.emit(
            event_bus.JOB_LOG,
            job_id=self.job_id,
            message="⚠ CAPTCHA detected. Please solve it in the browser window.",
            level="WARNING",
        )

        for _ in range(120):  # wait up to 4 minutes
            await asyncio.sleep(2)
            try:
                if await self._is_security_challenge_error(page):
                    await self._recover_security_challenge(page)
                current = (await page.inner_text("body", timeout=2000)).lower()
                if (
                    not any(sig in current for sig in CAPTCHA_SIGNALS)
                    and not any(sig in current for sig in CAPTCHA_ERROR_SIGNALS)
                ):
                    await self._restore_default_view(page)
                    logger.info(f"[{self.job_id}] CAPTCHA resolved — resuming")
                    return True
            except Exception:
                break
        return True

    async def _prepare_captcha_view(self, page: Page) -> None:
        """Zoom out and scroll the Jobsuche security panel into view."""
        try:
            await page.evaluate(
                """
                () => {
                    document.documentElement.style.zoom = '0.85';
                    const containsCaptcha = (el) =>
                        ((el.textContent || '').toLowerCase().includes('sicherheitsabfrage'));
                    const candidates = Array.from(document.querySelectorAll('section, div, article'));
                    const target = candidates.find(containsCaptcha);
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
