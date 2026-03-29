"""
ZUGZWANG - Aubi-Plus Scraper
Translated from Chrome Extension JS logic to native async Playwright.
"""

import asyncio
import re
from typing import AsyncGenerator
from urllib.parse import urljoin

from .browser import BrowserSession, BrowserError
from ..core.security import LicenseManager
from ..core.events import event_bus
from ..core.logger import get_logger
from ..core.models import LeadRecord, SearchConfig, SourceType

logger = get_logger(__name__)

# Basic fallback regex for deep email scanning
_EMAIL_REGEX = re.compile(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6})")

class AubiPlusScraper:
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
        logger.info(f"[{self.job_id}] Aubi-Plus scrape: '{self.config.job_title}' in '{self.config.city or self.config.country}'")
        
        # Build search URL
        query = self.config.job_title.replace(" ", "%20")
        loc = (self.config.city or self.config.country).replace(" ", "%20")
        url = f"https://www.aubi-plus.de/suchmaschine/?query={query}&location={loc}&radius=50"
        
        page = await self.session.new_page()
        try:
            success = await self.session.navigate(page, url, wait_until="domcontentloaded")
            if not success:
                raise BrowserError("Failed to load Aubi-Plus portal")
            
            # Step 1: Apply filters if configured
            if self.config.offer_type and "Ausbildung" in self.config.offer_type:
                await self._apply_filters(page)
            
            await asyncio.sleep(2)
            
            yielded_count = 0
            processed_urls = set()
            
            while not self._cancelled and yielded_count < self.config.max_results:
                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.5)
                if self._cancelled:
                    break
                
                # Step 2: Harvest cards on this page
                cards = await page.query_selector_all(".my-3.text-primary-dark.overflow-hidden.rounded-3")
                if not cards:
                    logger.info(f"[{self.job_id}] No cards found. Pagination ending.")
                    break
                    
                urls_to_visit = []
                for card in cards:
                    link_el = await card.query_selector("a.stretched-link, h2 a, a:not([href='#'])")
                    if link_el:
                        href = await link_el.get_attribute("href")
                        if href:
                            full_url = urljoin("https://www.aubi-plus.de", href)
                            if full_url not in processed_urls:
                                processed_urls.add(full_url)
                                urls_to_visit.append(full_url)
                
                # Visit the details
                for href in urls_to_visit:
                    if self._cancelled or yielded_count >= self.config.max_results:
                        break
                    while self._paused and not self._cancelled:
                        await asyncio.sleep(0.5)
                        
                    record = await self._extract_job_detail(href)
                    if record and (record.company_name or record.email or record.address or record.phone):
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
                
                if self._cancelled or yielded_count >= self.config.max_results:
                    break
                
                # Step 3: Pagination
                next_btn = await page.query_selector('li.page-item a[rel="next"], a.page-link[aria-label*="Next"], a.page-link[aria-label*="Weiter"]')
                if not next_btn:
                    # Fallback text search
                    all_page_links = await page.query_selector_all("ul.pagination a.page-link")
                    for link in all_page_links:
                        text = await link.inner_text()
                        if "»" in text or "Weiter" in text or "Nächste" in text:
                            next_btn = link
                            break
                            
                if next_btn:
                    next_url = await next_btn.get_attribute("href")
                    if next_url:
                        full_next = urljoin("https://www.aubi-plus.de", next_url)
                        logger.debug(f"[{self.job_id}] Navigating to next page: {full_next}")
                        success = await self.session.navigate(page, full_next, wait_until="domcontentloaded")
                        if not success:
                            break
                        await asyncio.sleep(2)
                        continue
                        
                logger.info(f"[{self.job_id}] No more pages available.")
                break
                    
            logger.info(f"[{self.job_id}] Scrape finished. Yielded {yielded_count} records.")
            
        except Exception as e:
            logger.error(f"[{self.job_id}] Fatal error during scrape: {e}", exc_info=True)
            self._total_errors += 1
            event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, level="ERROR", message=f"Aubi-Plus scan aborted: {str(e)}")

    async def _apply_filters(self, page):
        try:
            filter_btn = await page.query_selector(".btn-filter")
            if filter_btn:
                await filter_btn.evaluate("el => el.click()")
                await asyncio.sleep(2)  # Give the SPA more time
                
            ausbildung_label = await page.query_selector('label[for="fTyp_ausbildung"]')
            if ausbildung_label:
                checkbox = await page.query_selector("#fTyp_ausbildung")
                if checkbox:
                    is_checked = await checkbox.is_checked()
                    if not is_checked:
                        await ausbildung_label.evaluate("el => el.click()")
                        await asyncio.sleep(2)
                        logger.info(f"[{self.job_id}] Applied Ausbildung filter")
        except Exception as e:
            logger.warning(f"[{self.job_id}] Could not apply filters: {e}")

    async def _extract_job_detail(self, url: str) -> LeadRecord | None:
        detail_page = None
        try:
            detail_page = await self.session.new_page()
            success = await self.session.navigate(detail_page, url, wait_until="domcontentloaded", timeout=30000)
            if not success:
                return None
            
            await asyncio.sleep(self.config.delay_min)
            
            # Company Name
            company_el = await detail_page.query_selector(".fs-6.mb-0.lh-1")
            company_name = await company_el.inner_text() if company_el else ""
            if company_name:
                company_name = re.sub(r'\s+', ' ', company_name).strip()
                
            # Address
            address = ""
            location_icons = await detail_page.query_selector_all(".fa-location-dot")
            for icon in location_icons:
                # Need to run JS to reliably get next sibling
                next_text = await icon.evaluate("el => el.nextElementSibling ? el.nextElementSibling.innerText : ''")
                if next_text:
                    address = next_text.strip()
                    break
                    
            # Phone
            phone_el = await detail_page.query_selector(".phoneNumber")
            phone = await phone_el.inner_text() if phone_el else ""
            if phone:
                phone = phone.strip()
                
            # Email (Primary targets)
            email = ""
            email_bewerb = await detail_page.query_selector("#emailbewerbung")
            if email_bewerb:
                href = await email_bewerb.get_attribute("href")
                if href and "mailto:" in href:
                    email = href.replace("mailto:", "").split("?")[0].strip()
                    
            if not email:
                mailto_links = await detail_page.query_selector_all('a[href^="mailto:"]')
                for a in mailto_links:
                    href = await a.get_attribute("href")
                    if href and "@" in href:
                        email = href.replace("mailto:", "").split("?")[0].strip()
                        break
                        
            # Email (Fallback regex scan on cards)
            if not email:
                card_bodies = await detail_page.query_selector_all(".card-body.p-4")
                for cb in card_bodies:
                    text = await cb.inner_text()
                    match = _EMAIL_REGEX.search(text)
                    if match:
                        email = match.group(1).strip()
                        break
                        
            if detail_page:
                await detail_page.close()
            
            if not email and self.config.scrape_emails:
                return None
                
            record = LeadRecord(
                source_type=SourceType.AUBIPLUS_DE,
                source_url=url,
                search_query=self.config.job_title,
                city=self.config.city,
                company_name=company_name,
                address=address,
                email=email,
                phone=phone,
                job_title=self.config.job_title,
            )
            return record
        except Exception as e:
            logger.warning(f"[{self.job_id}] Error extracting {url}: {e}")
            self._total_errors += 1
            return None
        finally:
            if detail_page:
                await detail_page.close()
