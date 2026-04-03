"""
ZUGZWANG - Ausbildung.de Scraper
Translated from Chrome Extension JS logic to native async Playwright.
"""

import asyncio
from typing import AsyncGenerator

from .browser import BrowserSession, BrowserError
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

    def cancel(self):
        self._cancelled = True

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    async def scrape(self) -> AsyncGenerator[LeadRecord, None]:
        logger.info(f"[{self.job_id}] Ausbildung scrape: '{self.config.job_title}' in '{self.config.city or self.config.country}'")
        
        import urllib.parse
        
        # Build search URL using the new working format
        query = urllib.parse.quote(self.config.job_title)
        
        location_val = self.config.city or ""
        if not location_val and self.config.country and self.config.country != "Germany":
            location_val = self.config.country
            
        if location_val:
            loc = urllib.parse.quote(location_val)
            url = f"https://www.ausbildung.de/suche/?form_main_search[what]={query}&form_main_search[where]={loc}&form_main_search[radius]=50"
        else:
            url = f"https://www.ausbildung.de/suche/?form_main_search[what]={query}"
        
        event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, message=f"Starting Ausbildung.de search for '{self.config.job_title}' in '{location_val}'", level="INFO")
        
        page = await self.session.new_page()
        try:
            success = await self.session.navigate(page, url, wait_until="domcontentloaded")
            if not success:
                raise BrowserError("Failed to load Ausbildung portal")
            
            # Step 1: Apply filters if configured
            if self.config.offer_type and "Ausbildung" in self.config.offer_type:
                await self._apply_filters(page)
            
            await asyncio.sleep(2)
            
            # Step 2: Infinite scroll and harvest cards
            yielded_count = 0
            retries = 0
            processed_urls = set()
            
            while not self._cancelled and yielded_count < self.config.max_results:
                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.5)
                if self._cancelled:
                    break
                
                # Extract all card links on the current page
                cards = await page.query_selector_all(".JobPostingCard-module__RpcvXq__cardWrapper a")
                
                event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, message=f"Scanning page: found {len(cards)} total job cards.", level="INFO")
                
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
                    continue
                
                # Step 3: Visit each URL to extract deep email
                for href in urls_to_visit:
                    if self._cancelled or yielded_count >= self.config.max_results:
                        break
                    while self._paused and not self._cancelled:
                        await asyncio.sleep(0.5)
                    
                    full_url = href if href.startswith("http") else f"https://www.ausbildung.de{href}"
                    event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, message=f"Inspecting detail page: {full_url}", level="INFO")
                    record = await self._extract_job_detail(full_url)
                    
                    if record and (record.company_name or record.email or record.address):
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
                await asyncio.sleep(2)  # Give the SPA more time to render the filter menu
                
            # Find div id: "klassische-duale-berufsausbildung-label" and check it
            check_label = await page.query_selector("#klassische-duale-berufsausbildung-label")
            if check_label:
                await check_label.evaluate("el => el.click()")
            else:
                check_icon = await page.query_selector(".CheckboxItem-module__P4--Qq__checkmark")
                if check_icon:
                    await check_icon.evaluate("el => el.click()")
            await asyncio.sleep(2)
            logger.info(f"[{self.job_id}] Applied Ausbildung dual-vocational filter")
        except Exception as e:
            logger.warning(f"[{self.job_id}] Could not apply filters: {e}")

    async def _load_more(self, page) -> bool:
        try:
            # Scroll down
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5)
            
            spinner_btn = await page.query_selector(".SearchResults-module__6Vm6GG__spinnerContainer button")
            if spinner_btn:
                await spinner_btn.evaluate("el => el.click()")
                await asyncio.sleep(2)
                return True
                
            load_more_btns = await page.query_selector_all("button")
            for btn in load_more_btns:
                text = await btn.inner_text()
                txt_lower = text.lower()
                if "load more" in txt_lower or "mehr laden" in txt_lower or "weitere" in txt_lower:
                    await btn.evaluate("el => el.click()")
                    await asyncio.sleep(2)
                    return True
            return False
        except Exception as e:
            logger.debug(f"[{self.job_id}] Load more failed: {e}")
            return False

    async def _extract_job_detail(self, url: str) -> LeadRecord | None:
        detail_page = None
        try:
            detail_page = await self.session.new_page()
            success = await self.session.navigate(detail_page, url, wait_until="domcontentloaded", timeout=30000)
            if not success:
                return None
            
            # Simple bot detection evasion
            await asyncio.sleep(self.config.delay_min)
            
            company_name_el = await detail_page.query_selector(".jp-c-header__corporation-link")
            company_name = await company_name_el.inner_text() if company_name_el else ""
            if company_name:
                company_name = company_name.replace("Arbeitgeber:", "").strip()
                company_name = company_name.strip()
            
            address = ""
            contact_person = ""
            
            # Use the richer detail address block if available
            detail_addr_el = await detail_page.query_selector("#detail-bewerbung-adresse")
            if detail_addr_el:
                content = await detail_addr_el.inner_text()
                lines = [l.strip() for l in content.splitlines() if l.strip()]
                # Filter out "Arbeitgeber:" label if it appears on its own line
                lines = [l for l in lines if l.lower().rstrip(":") != "arbeitgeber"]
                if len(lines) >= 3:
                    # Format: Company \n Contact \n Street \n Zip City
                    if "herr " in lines[1].lower() or "frau " in lines[1].lower() or any(x in lines[1].lower() for x in ["dir. ", "dr. ", "diederik"]):
                        if not company_name:
                            company_name = lines[0].replace("Arbeitgeber:", "").strip()
                        contact_person = lines[1]
                        address = ", ".join(lines[2:])
                    else:
                        # Probably just Company \n Street \n Zip City
                        if not company_name:
                            company_name = lines[0].replace("Arbeitgeber:", "").strip()
                        address = ", ".join(lines[1:])
                elif len(lines) == 2:
                    if not company_name:
                        company_name = lines[0].replace("Arbeitgeber:", "").strip()
                    address = lines[1]
                elif len(lines) == 1:
                    address = lines[0]
                    
            # Fallback to simple address if still empty
            if not address:
                address_el = await detail_page.query_selector(".jp-title__address")
                address = await address_el.inner_text() if address_el else ""
                if address:
                    address = address.replace("📍", "").strip()
                
            # Extract phone number
            phone = ""
            phone_el = await detail_page.query_selector("#detail-bewerbung-telefon-Telefon")
            if not phone_el:
                phone_el = await detail_page.query_selector('a[href^="tel:"]')
            
            if phone_el:
                phone_href = await phone_el.get_attribute("href")
                if phone_href:
                    phone = phone_href.replace("tel:", "").strip()
                else:
                    phone = await phone_el.inner_text()
                    phone = phone.strip()

            # Extract specific city/postal code from the address
            extracted_city = ""
            postal_code = ""
            if address:
                # Look for "12345 City" pattern
                import re
                city_pc_match = re.search(r'(\d{5})\s+([^,]+)', address)
                if city_pc_match:
                    postal_code = city_pc_match.group(1)
                    extracted_city = city_pc_match.group(2).strip()
            
            # Use extracted city if available, fallback to config if not generic "Ort"
            city = self.config.city
            if extracted_city and (not city or city.lower() == "ort"):
                city = extracted_city

            # Extract apprenticeship start date (Ausbildungsbeginn) if available
            start_date = ""
            try:
                page_text = await detail_page.inner_text("body")
                # Look for format: 01.09.2026 or 01092026
                # Many Ausbildung listings show a Beginn date
                date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})|(\d{8})', page_text)
                if date_match:
                    start_date = date_match.group(0)
            except:
                pass

            email = ""
            mailto_links = await detail_page.query_selector_all('a[href^="mailto:"]')
            for a in mailto_links:
                href = await a.get_attribute("href")
                if href and "@" in href:
                    email = href.replace("mailto:", "").split("?")[0].strip()
                    event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, message=f"Found email: {email}", level="INFO")
                    break
                    
        except Exception as e:
            logger.warning(f"[{self.job_id}] Error extracting {url}: {e}")
            self._total_errors += 1
            return None
        finally:
            if detail_page:
                await detail_page.close()
            if not email and self.config.scrape_emails:
                return None
                
            record = LeadRecord(
                source_type=SourceType.AUSBILDUNG_DE,
                source_url=url,
                search_query=self.config.job_title,
                city=city,
                postal_code=postal_code,
                company_name=company_name,
                address=address,
                phone=phone,
                email=email,
                contact_person=contact_person,
                job_title=self.config.job_title,
                publication_date=start_date,
            ).normalize()
            
            # As requested in the content script, skip if no email AND user wants emails
            if not email and self.config.scrape_emails:
                return None
                
            return record
    # End of file
