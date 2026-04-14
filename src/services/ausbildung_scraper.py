"""
ZUGZWANG - Ausbildung.de Scraper
Translated from Chrome Extension JS logic to native async Playwright.
"""

import asyncio
import re
import urllib.parse
from typing import AsyncGenerator

from .browser import BrowserSession, BrowserError
from .website_crawler import WebsiteEmailCrawler
from ..core.security import LicenseManager
from ..core.events import event_bus
from ..core.logger import get_logger
from ..core.models import LeadRecord, SearchConfig, SourceType

logger = get_logger(__name__)


class AusbildungScraper:
    def __init__(self, session: BrowserSession, config: SearchConfig, job_id: str):
        self.session = session
        self.config = config
        self.job_id = job_id
        self._cancelled = False
        self._paused = False
        self._total_errors = 0
        self.crawler = WebsiteEmailCrawler(session) if config.scrape_emails else None

    def cancel(self):
        self._cancelled = True

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    async def scrape(self) -> AsyncGenerator[LeadRecord, None]:
        logger.info(f"[{self.job_id}] Ausbildung scrape: '{self.config.job_title}' in '{self.config.city or self.config.country}'")
        
        location_val = self.config.city or ""
        if not location_val and self.config.country and self.config.country != "Germany":
            location_val = self.config.country
            
        radius_val = getattr(self.config, 'radius', 25)

        # Build search URL using the precise verified format
        if location_val:
            query_encoded = urllib.parse.quote(self.config.job_title)
            loc_encoded = urllib.parse.quote(location_val)
            url = f"https://www.ausbildung.de/suche/?search={query_encoded}%7C{loc_encoded}&radius={radius_val}"
        else:
            query_encoded = urllib.parse.quote(self.config.job_title)
            url = f"https://www.ausbildung.de/suche/?search={query_encoded}&radius={radius_val}"
        
        event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, message=f"Starting Ausbildung.de search for '{self.config.job_title}' in '{location_val}' (Radius: {radius_val}km)", level="INFO")
        
        page = await self.session.new_page()
        try:
            success = await self.session.navigate(page, url, wait_until="domcontentloaded")
            if not success:
                raise BrowserError("Failed to load Ausbildung portal")

            await self._accept_cookies(page)
            
            # Step 1: Apply filters if configured
            if self.config.offer_type and "Ausbildung" in self.config.offer_type:
                await self._apply_filters(page)
            
            # Step 1.5: Expand radius if location was provided
            if location_val:
                await self._expand_radius(page)
            
            await asyncio.sleep(0.5)
            
            # Step 2: Infinite scroll and harvest cards
            yielded_count = 0
            retries = 0
            processed_urls = set()
            
            while not self._cancelled and yielded_count < self.config.max_results:
                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.5)
                if self._cancelled:
                    break

                cards = await self._query_result_cards(page)

                event_bus.emit(
                    event_bus.JOB_LOG,
                    job_id=self.job_id,
                    message=f"Scanning page: found {len(cards)} total job cards.",
                    level="INFO",
                )

                urls_to_visit = []
                for card in cards:
                    href = await card.get_attribute("href")
                    if href and href not in processed_urls:
                        urls_to_visit.append(href)
                        processed_urls.add(href)
                
                if not urls_to_visit:
                    # Try to load more
                    logger.debug(f"[{self.job_id}] Trying to load more results. Currently have {len(processed_urls)}.")
                    event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, message="Loading more results from Ausbildung.de...", level="INFO")
                    loaded_more = await self._load_more(page)
                    if not loaded_more:
                        retries += 1
                        if retries > 3:
                            logger.info(f"[{self.job_id}] No more cards to load.")
                            break
                    else:
                        retries = 0
                        # FIX #3: DOM Settling wait
                        await asyncio.sleep(1.0)
                    continue
                
                # Step 3: Visit URLs in parallel batches of 5
                async for record in self._fetch_batch(urls_to_visit):
                    if self._cancelled or yielded_count >= self.config.max_results:
                        break
                    if record is None:
                        continue
                    if not (record.company_name or record.email or record.address):
                        continue
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

                    yielded_count += 1
                    event_bus.emit(
                        event_bus.JOB_RESULT,
                        job_id=self.job_id,
                        record=record,
                        count=yielded_count,
                    )
                    LicenseManager.record_extraction()
                    yield record

            logger.info(f"[{self.job_id}] Scrape finished. Yielded {yielded_count} records.")
            
        except Exception as e:
            logger.error(f"[{self.job_id}] Fatal error during scrape: {e}", exc_info=True)
            self._total_errors += 1
            event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, level="ERROR", message=f"Ausbildung scan aborted: {str(e)}")

    async def _fetch_batch(self, hrefs: list[str]) -> AsyncGenerator[LeadRecord | None, None]:
        """Fetch detail pages sequentially to prevent UI thread flooding."""
        for href in hrefs:
            if self._cancelled:
                return

            while self._paused and not self._cancelled:
                await asyncio.sleep(0.3)
            
            full = href if href.startswith("http") else f"https://www.ausbildung.de{href}"
            event_bus.emit(
                event_bus.JOB_LOG,
                job_id=self.job_id,
                message=f"Inspecting detail page: {full}",
                level="INFO",
            )
            try:
                record = await self._extract_job_detail(full)
                # Small yield to let UI and DB pipeline breathe one-by-one.
                await asyncio.sleep(0.1)
                yield record
            except Exception as e:
                logger.warning(f"[{self.job_id}] Detail task failed for {full}: {e}")
                yield None

    async def _apply_filters(self, page):
        try:
            # Try original ID first, then fallback to any toggle named Filter
            filter_btn = await page.query_selector("#_R_d6cpav5tpflb_")
            if not filter_btn:
                buttons = await page.query_selector_all("button")
                for btn in buttons:
                    text = await btn.inner_text()
                    if "Filter" in text:
                        filter_btn = btn
                        break
                        
            if filter_btn:
                await filter_btn.evaluate("el => el.click()")
                await asyncio.sleep(0.5)  # Give the SPA more time to render the filter menu
                
            # Find div id: "klassische-duale-berufsausbildung-label" and check it
            check_label = await page.query_selector("#klassische-duale-berufsausbildung-label")
            if check_label:
                await check_label.evaluate("el => el.click()")
            else:
                check_icon = await page.query_selector(".CheckboxItem-module__P4--Qq__checkmark")
                if check_icon:
                    await check_icon.evaluate("el => el.click()")
            await asyncio.sleep(0.5)
            logger.info(f"[{self.job_id}] Applied Ausbildung dual-vocational filter")
        except Exception as e:
            logger.warning(f"[{self.job_id}] Could not apply filters: {e}")

    async def _expand_radius(self, page):
        """Maximize search radius to configured value to guarantee matching leads."""
        try:
            radius = getattr(self.config, 'radius', 25)
            # FIX #2: Radius normalization
            target_text = f"{radius} km"
            
            radius_toggle = await page.query_selector("[data-testid='radius-filter']")
            if not radius_toggle:
                # Fallback for dynamic ID
                radius_toggle = await page.query_selector("button[id*='toggle-button'][aria-label='Radiusauswahl']")
            
            if radius_toggle:
                curr_text = (await radius_toggle.inner_text()).replace("\xa0", " ").strip()
                if target_text in curr_text:
                    logger.info(f"[{self.job_id}] Radius is already {target_text}.")
                    return

                await radius_toggle.evaluate("el => el.click()")
                # FIX #2: Jitter and load wait
                await asyncio.sleep(1.5)
                
                # Look for the target option in the dropdown
                options = await page.query_selector_all("li[role='option'], .RadiusFilter-module__5FLedG__menuItem")
                for opt in options:
                    text = (await opt.inner_text()).replace("\xa0", " ").strip()
                    if target_text in text:
                        await opt.evaluate("el => el.click()")
                        await asyncio.sleep(1.5)
                        try:
                            await page.wait_for_load_state("networkidle", timeout=5000)
                        except Exception:
                            pass
                        logger.info(f"[{self.job_id}] Expanded search radius to {target_text}.")
                        return
                
                # Second fallback: look for text directly
                max_radius_btn = await page.query_selector(f"text='{target_text}'")
                if max_radius_btn:
                    await max_radius_btn.evaluate("el => el.click()")
                    await asyncio.sleep(1.5)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                    logger.info(f"[{self.job_id}] Expanded search radius to {target_text} (text fallback).")
        except Exception as e:
            logger.debug(f"[{self.job_id}] Could not expand radius: {e}")

    async def _load_more(self, page) -> bool:
        try:
            # Scroll down
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.5)

            # FIX #1: Resilient structural selectors
            spinner_selector = "button[class*='spinnerContainer'], [class*='spinnerContainer'] button, button[class*='loadMore'], button[class*='load-more']"
            spinner_btn = await page.query_selector(spinner_selector)
            if spinner_btn:
                await spinner_btn.evaluate("el => el.click()")
                # FIX #1: Increased sleep and selector wait
                await asyncio.sleep(2.5)
                try:
                    await page.wait_for_selector("a[href*='/stellen/']", state="attached", timeout=4000)
                    return True
                except Exception:
                    return False

            load_more_btns = await page.query_selector_all("button")
            for btn in load_more_btns:
                text = await btn.inner_text()
                txt_lower = text.lower()
                if any(x in txt_lower for x in ["mehr ergebnisse laden", "load more", "mehr laden", "weitere"]):
                    event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, message="Clicked 'Mehr Ergebnisse laden' button.", level="INFO")
                    await btn.evaluate("el => el.click()")
                    # FIX #1: Increased sleep and selector wait
                    await asyncio.sleep(2.5)
                    try:
                        await page.wait_for_selector("a[href*='/stellen/']", state="attached", timeout=4000)
                        return True
                    except Exception:
                        # Maybe new cards didn't load but we don't want to fail if it was just a slow DOM
                        return False
            return False
        except Exception as e:
            logger.debug(f"[{self.job_id}] Load more failed: {e}")
            return False

    async def _accept_cookies(self, page) -> None:
        try:
            buttons = await page.query_selector_all("button")
            for btn in buttons:
                try:
                    text = (await btn.inner_text()).strip().lower()
                except Exception:
                    continue
                if "alles akzeptieren" in text or "accept all" in text:
                    await btn.evaluate("el => el.click()")
                    await asyncio.sleep(0.6)
                    return
        except Exception as e:
            logger.debug(f"[{self.job_id}] Cookie accept skipped: {e}")

    async def _query_result_cards(self, page):
        selectors = [
            ".JobPostingCard-module__RpcvXq__cardWrapper a[href]",  # From user script
            "[class*='JobPostingCard-module__'][class*='cardWrapper'] a[href]",
            "article[data-testid='jp-card'] a[href]",
            "a[href*='/stellen/']",
        ]
        seen = set()
        nodes = []
        for selector in selectors:
            try:
                found = await page.query_selector_all(selector)
            except Exception:
                continue
            for node in found:
                try:
                    href = await node.get_attribute("href")
                except Exception:
                    continue
                if not href or "/stellen/" not in href:
                    continue
                key = href if href.startswith("http") else f"https://www.ausbildung.de{href}"
                if key in seen:
                    continue
                seen.add(key)
                nodes.append(node)
        return nodes

    def _parse_detail_html(self, html: str) -> dict:
        from bs4 import BeautifulSoup

        doc = BeautifulSoup(html, "html.parser")
        company_name = ""
        company_name_el = doc.select_one(".jp-c-header__corporation-link")
        if company_name_el:
            company_name = company_name_el.get_text(" ", strip=True).replace("Arbeitgeber:", "").strip()

        address = ""
        contact_person = ""
        detail_addr_el = doc.select_one("#detail-bewerbung-adresse")
        if detail_addr_el:
            lines = [line.strip() for line in detail_addr_el.get_text("\n", strip=True).splitlines() if line.strip()]
            lines = [line for line in lines if line.lower().rstrip(":") != "arbeitgeber"]
            if len(lines) >= 3:
                if "herr " in lines[1].lower() or "frau " in lines[1].lower() or any(x in lines[1].lower() for x in ["dir. ", "dr. "]):
                    if not company_name:
                        company_name = lines[0].replace("Arbeitgeber:", "").strip()
                    contact_person = lines[1]
                    address = ", ".join(lines[2:])
                else:
                    if not company_name:
                        company_name = lines[0].replace("Arbeitgeber:", "").strip()
                    address = ", ".join(lines[1:])
            elif len(lines) == 2:
                if not company_name:
                    company_name = lines[0].replace("Arbeitgeber:", "").strip()
                address = lines[1]
            elif len(lines) == 1:
                address = lines[0]

        if not address:
            address_el = doc.select_one(".jp-title__address")
            if address_el:
                address = address_el.get_text(" ", strip=True).replace("📍", "").strip()

        phone = ""
        phone_el = doc.select_one("#detail-bewerbung-telefon-Telefon") or doc.select_one('a[href^="tel:"]')
        if phone_el:
            phone_href = phone_el.get("href", "")
            phone = phone_href.replace("tel:", "").strip() if phone_href else phone_el.get_text(" ", strip=True).strip()

        email = ""
        for a in doc.select('a[href^="mailto:"]'):
            href = a.get("href", "")
            if href and "@" in href:
                email = href.replace("mailto:", "").split("?")[0].strip()
                break

        website = ""
        website_selectors = [
            "#detail-bewerbung-url",
            "a[href*='homepage']",
            "a[href*='internetseite']",
            "a[href*='website']",
            "a[target='_blank'][href^='http']",
        ]
        for selector in website_selectors:
            for a in doc.select(selector):
                href = (a.get("href") or "").strip()
                if not href:
                    continue
                lower_href = href.lower()
                if lower_href.startswith(("mailto:", "tel:")):
                    continue
                if "ausbildung.de" in lower_href:
                    continue
                website = href
                break
            if website:
                break

        body_text = doc.get_text("\n", strip=True)
        start_date = ""
        date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})|(\d{8})", body_text)
        if date_match:
            start_date = date_match.group(0)

        postal_code = ""
        extracted_city = ""
        if address:
            city_pc_match = re.search(r"(\d{5})\s+([^,]+)", address)
            if city_pc_match:
                postal_code = city_pc_match.group(1)
                extracted_city = city_pc_match.group(2).strip()

        return {
            "company_name": company_name,
            "address": address,
            "contact_person": contact_person,
            "phone": phone,
            "email": email,
            "website": website,
            "start_date": start_date,
            "postal_code": postal_code,
            "extracted_city": extracted_city,
        }

    async def _extract_job_detail(self, url: str) -> LeadRecord | None:
        try:
            html = await self.session.fetch_url_content_fast(url, ignore_rate_limit=True)
            
            if not html:
                logger.debug(f"[{self.job_id}] Fast fetch empty for {url}, falling back to tab navigation.")
                async with self.session.page_lock:
                    detail_page = await self.session.new_page()
                    try:
                        success = await self.session.navigate(detail_page, url, wait_until="domcontentloaded", timeout=30000)
                        if not success:
                            return None
                        await asyncio.sleep(0.5)
                        html = await detail_page.content()
                    except Exception as e:
                        logger.warning(f"[{self.job_id}] Tab navigation failed for {url}: {e}")
                        return None
                    finally:
                        await detail_page.close()

            if not html:
                return None

            fields = self._parse_detail_html(html)
            company_name = fields["company_name"]
            address = fields["address"]
            contact_person = fields["contact_person"]
            phone = fields["phone"]
            email = fields["email"]
            website = fields["website"]
            start_date = fields["start_date"]
            postal_code = fields["postal_code"]
            extracted_city = fields["extracted_city"]
            city = self.config.city
            if extracted_city and (not city or city.lower() == "ort"):
                city = extracted_city

            if email:
                event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, message=f"Found email: {email}", level="INFO")

            if self.crawler and website and (not email or not phone):
                crawled_email, crawled_phone, source_page, _socials = await self.crawler.find_contact_info(
                    website,
                    company_name=company_name,
                    job_id=self.job_id,
                )
                if crawled_email and not email:
                    email = crawled_email
                    event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, message=f"Found email: {email}", level="INFO")
                if crawled_phone and not phone:
                    phone = crawled_phone
                if source_page and not website:
                    website = source_page
                    
        except Exception as e:
            logger.warning(f"[{self.job_id}] Error extracting {url}: {e}")
            self._total_errors += 1
            return None

        record = LeadRecord(
            source_type=SourceType.AUSBILDUNG_DE,
            source_url=url,
            search_query=self.config.job_title,
            city=city,
            postal_code=postal_code,
            company_name=company_name,
            address=address,
            website=website,
            phone=phone,
            email=email,
            contact_person=contact_person,
            job_title=self.config.job_title,
            publication_date=start_date,
        ).normalize()
        
        return record
