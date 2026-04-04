"""
ZUGZWANG - Azubiyo.de Scraper
Playwright-based scraper integrating logic from the reference parser.
"""

import asyncio
from typing import AsyncGenerator

from .browser import BrowserSession, BrowserError
from ..core.security import LicenseManager
from ..core.events import event_bus
from ..core.logger import get_logger
from ..core.models import LeadRecord, SearchConfig, SourceType

logger = get_logger(__name__)


class AzubiyoScraper:
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
        location_val = self.config.city or self.config.region or ""
        logger.info(f"[{self.job_id}] Azubiyo scrape: '{self.config.job_title}' in '{location_val}'")
        
        event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, message=f"Starting Azubiyo.de search for '{self.config.job_title}' in '{location_val}'", level="INFO")
        
        page = await self.session.new_page()
        try:
            # Step 1: Navigate to homepage and search
            success = await self.session.navigate(page, "https://www.azubiyo.de/", wait_until="domcontentloaded")
            if not success:
                raise BrowserError("Failed to load Azubiyo portal")
            
            await asyncio.sleep(2)
            
            # Dismiss cookies if present
            try:
                cookie_btn = page.locator('button:has-text("Akzeptieren"), button:has-text("Zustimmen")')
                if await cookie_btn.first.is_visible(timeout=3000):
                    await cookie_btn.first.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

            # Form interaction based on live Azubiyo DOM
            logger.info(f"[{self.job_id}] Filling Azubiyo search form via UI selectors")
            
            # 1. Fill Job Title ('Was')
            if self.config.job_title:
                await page.fill('input#text, input[name="text"]', self.config.job_title)
                await asyncio.sleep(0.5)
                
            # 2. Fill Location ('Wo')
            if location_val:
                await page.fill('input#location-query, input[name="location"]', location_val)
                await asyncio.sleep(1.0) # Wait for autocomplete/dropdown to stabilize
                
            # 3. Click "Freie Stellen finden"
            submit_btn = page.locator('button[type="submit"]:has-text("Freie Stellen finden")')
            if not await submit_btn.is_visible():
                submit_btn = page.locator('button[type="submit"]')
                
            await submit_btn.first.click()
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3.0)

            # Step 2: Harvest cards and paginate
            yielded_count = 0
            retries = 0
            processed_urls = set()
            
            # The reference script uses pagination by appending /page/ or similar
            # Let's use Playwright to click the "Next" button or harvest all links
            
            while not self._cancelled and yielded_count < self.config.max_results:
                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.5)
                if self._cancelled:
                    break
                
                # Using the exact selector from job_offers_parser.py
                # div.col-lg-12.col-md-6.mb-3.mb-md-30px.mb-lg-3
                cards = await page.query_selector_all('div.col-lg-12.col-md-6, article, .job-item')
                
                event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, message=f"Scanning page: found {len(cards)} job cards.", level="INFO")
                
                urls_to_visit = []
                for card in cards:
                    # Look for the title link inside the card
                    link = await card.query_selector('a, h3 a')
                    if link:
                        href = await link.get_attribute("href")
                        if href and href not in processed_urls and "/ausbildung/" in href or "/duales-studium/" in href or "/stellenanzeigen/" in href:
                            processed_urls.add(href)
                            urls_to_visit.append(href)
                
                if not urls_to_visit:
                    # Let's try alternative card selectors just in case
                    a_tags = await page.query_selector_all('a[href*="/ausbildung/"], a[href*="/stellenanzeigen/"]')
                    for a in a_tags:
                        href = await a.get_attribute("href")
                        if href and href not in processed_urls:
                            processed_urls.add(href)
                            urls_to_visit.append(href)
                    
                    if not urls_to_visit:
                        logger.debug(f"[{self.job_id}] No links found on this page. Stopping pagination.")
                        break

                # Step 3: Visit each URL to extract details
                for href in urls_to_visit:
                    if self._cancelled or yielded_count >= self.config.max_results:
                        break
                    while self._paused and not self._cancelled:
                        await asyncio.sleep(0.5)
                    
                    full_url = href if href.startswith("http") else f"https://www.azubiyo.de{href}"
                    event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, message=f"Inspecting detail page: {full_url}", level="INFO")
                    
                    record = await self._extract_job_detail(full_url)
                    
                    if record and (record.company_name or record.email or record.job_title):
                        if not LicenseManager.can_extract():
                            logger.warning(f"[{self.job_id}] Free trial limit reached.")
                            event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, message="Free trial limit reached (20 scraps/day). Please upgrade to Professional.", level="WARNING")
                            event_bus.emit(event_bus.TRIAL_LIMIT_REACHED, job_id=self.job_id)
                            return

                        yielded_count += 1
                        event_bus.emit(event_bus.JOB_RESULT, job_id=self.job_id, record=record, count=yielded_count)
                        LicenseManager.record_extraction()
                        yield record

                # Try to go to next page
                next_btn = await page.query_selector('a.page-link[aria-label="Weiter"], a:has-text("Nächste"), li.next a')
                if next_btn:
                    await next_btn.click()
                    await asyncio.sleep(3)
                else:
                    break
                    
            logger.info(f"[{self.job_id}] Scrape finished. Yielded {yielded_count} records.")
            
        except Exception as e:
            logger.error(f"[{self.job_id}] Fatal error during Azubiyo scrape: {e}", exc_info=True)
            self._total_errors += 1
            event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, level="ERROR", message=f"Azubiyo scan aborted: {str(e)}")
        finally:
            if page:
                await page.close()

    async def _extract_job_detail(self, url: str) -> LeadRecord | None:
        detail_page = None
        try:
            detail_page = await self.session.new_page()
            success = await self.session.navigate(detail_page, url, wait_until="domcontentloaded", timeout=30000)
            if not success:
                return None
            
            await asyncio.sleep(self.config.delay_min)
            
            # Using selectors based on standard Azubiyo detail pages
            title_el = await detail_page.query_selector('h1')
            job_title = await title_el.inner_text() if title_el else self.config.job_title

            # Company is often near the title or in an profile header
            company_el = await detail_page.query_selector('.az-profile-header h2, .company-name, h2')
            company_name = await company_el.inner_text() if company_el else ""
            if not company_name:
                company_name = await detail_page.title()
                company_name = company_name.split("|")[0].strip()

            address = ""
            city = self.config.city or ""
            postal_code = ""

            # Look for contact details section
            address_wrapper = await detail_page.query_selector_all('.address, .contact-info, address')
            for wrapper in address_wrapper:
                text = await wrapper.inner_text()
                if text:
                    address = text.strip()
                    break

            # Extract Phone
            phone = ""
            phone_el = await detail_page.query_selector('a[href^="tel:"]')
            if phone_el:
                phone_href = await phone_el.get_attribute("href")
                if phone_href:
                    phone = phone_href.replace("tel:", "").strip()

            # Extract Email
            email = ""
            mailto_links = await detail_page.query_selector_all('a[href^="mailto:"]')
            for a in mailto_links:
                href = await a.get_attribute("href")
                if href and "@" in href:
                    email = href.replace("mailto:", "").split("?")[0].strip()
                    event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, message=f"Found email: {email}", level="INFO")
                    break

            # Extract Website
            website = ""
            ext_links = await detail_page.query_selector_all('a[target="_blank"]')
            for a in ext_links:
                href = await a.get_attribute("href")
                if href and "http" in href and "azubiyo.de" not in href and "facebook" not in href:
                    website = href
                    break
                    
        except Exception as e:
            logger.warning(f"[{self.job_id}] Error extracting {url}: {e}")
            self._total_errors += 1
            return None
        finally:
            if detail_page:
                try:
                    await detail_page.close()
                except:
                    pass

        if not email and self.config.scrape_emails:
            return None
            
        record = LeadRecord(
            source_type=SourceType.AZUBIYO,
            source_url=url,
            search_query=self.config.job_title,
            city=city,
            postal_code=postal_code,
            company_name=company_name,
            address=address,
            phone=phone,
            email=email,
            contact_person="",
            job_title=job_title,
        ).normalize()
        
        return record
