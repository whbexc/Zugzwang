"""
ZUGZWANG - Das Örtliche Scraper
Scrapes business listings from dasoertliche.de based on keyword and city.
"""

from __future__ import annotations
import asyncio
import re
from typing import AsyncGenerator
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .browser import BrowserSession
from .email_extractor import extract_emails_from_html, deduplicate_emails
from .website_crawler import WebsiteEmailCrawler
from ..core.logger import get_logger
from ..core.security import LicenseManager
from ..core.models import LeadRecord, SearchConfig, SourceType

logger = get_logger(__name__)

DAS_OERTLICHE_URL = "https://www.dasoertliche.de/"

class DasOertlicheScraper:
    """
    Scrapes dasoertliche.de for business listings.
    
    Architecture:
    - Drives the homepage form directly (Branche + Ort).
    - Uses Playwright for navigation and parsing.
    - Detail pages are fetched via in-page JS fetch() to extract email/website if missing.
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
        self.crawler = WebsiteEmailCrawler(session) if config.scrape_emails else None

    def cancel(self) -> None:
        self._cancelled = True

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    async def _dismiss_cookies(self, page) -> None:
        """Robustly dismiss cookie banners via JS."""
        await page.evaluate(
            """() => {
                const selectors = [
                    '#cmpbntyestxt',
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
                // Fallback
                const btns = Array.from(document.querySelectorAll('button, a'));
                const confirm = btns.find(b => {
                    const t = b.textContent.toLowerCase();
                    return t.includes('akzeptieren') || t.includes('alle akzeptieren') || t.includes('zustimmen') || t.includes('einverstanden');
                });
                if (confirm) confirm.click();
            }"""
        )

    async def scrape(self) -> AsyncGenerator[LeadRecord, None]:
        """Async generator that yields LeadRecord objects one by one."""
        page = await self.session.new_page()
        try:
            keyword = self.config.job_title or "Pflegefachmann"
            city = self.config.city or ""

            # Navigate directly to the search URL
            from urllib.parse import quote
            search_url = (
                f"https://www.dasoertliche.de/"
                f"?form_name=search_nat&kw={quote(keyword)}&ci={quote(city)}"
            )
            logger.info(f"[{self.job_id}] Navigating to search: Branche='{keyword}', Ort='{city}'")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(2)
            
            # Check if we landed on a disambiguation page (Ortsauswahl)
            # Das Örtliche does this for ambiguous locations like "Hamburg" or "Köln"
            disambiguation_links = await page.locator('a[onclick*="Ortsliste_Ortsauswahl"]').all()
            if disambiguation_links:
                logger.info(f"[{self.job_id}] Found {len(disambiguation_links)} location disambiguation links. Clicking the first match.")
                
                # Try to find an exact match, otherwise just click the first one
                target_link = disambiguation_links[0]
                for link in disambiguation_links:
                    text = await link.inner_text()
                    if text.strip().lower() == city.lower():
                        target_link = link
                        break
                        
                async with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
                    await target_link.click(force=True)
                await asyncio.sleep(2)

            logger.info(f"[{self.job_id}] Search submitted. Parsing results...")
            processed_urls: set[str] = set()
            processed_names: set[str] = set()
            yielded_count = 0
            page_num = 1
            
            while not self._cancelled:
                # Pause / cancel check
                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.1)
                if self._cancelled:
                    break

                # Extract listings from the current page using Das Oertliche's internal data array
                cards = await page.evaluate(
                    r"""() => {
                        let hData = null;
                        try {
                            const html = document.documentElement.innerHTML;
                            const match = html.match(/var handlerData\s*=\s*(\[\[.*?\]\]);/s);
                            if (match && match[1]) {
                                hData = JSON.parse(match[1]);
                            }
                        } catch(e) {
                            console.error(e);
                        }
                        
                        const results = [];
                        if (hData && Array.isArray(hData)) {
                            for (let i = 0; i < hData.length; i++) {
                                const row = hData[i];
                                if (!row || row.length < 21) continue;
                                
                                const website = row[3] ? row[3] : null;
                                const city = row[4];
                                const zip = row[8];
                                const street = row[9];
                                const streetNum = row[10];
                                const phone = row[11];
                                const name = row[14];
                                const email = row[17] ? row[17] : null;
                                const niceid = row[20];
                                
                                if (name) {
                                    results.push({
                                        name: name,
                                        address: (street ? street + (streetNum ? " " + streetNum : "") + ", " : "") + (zip ? zip + " " : "") + (city ? city : ""),
                                        phone: phone,
                                        email: email,
                                        website: website,
                                        detail_url: niceid ? "https://www.dasoertliche.de/Themen/" + niceid : null
                                    });
                                }
                            }
                        }
                        
                        // Fallback to DOM if handlerData fails
                        if (results.length === 0) {
                            const items = document.querySelectorAll('.hit');
                            items.forEach(item => {
                                const nameEl = item.querySelector('h2 a') || item.querySelector('.name');
                                const addressEl = item.querySelector('.address') || item.querySelector('address');
                                const phoneEl = item.querySelector('.phone') || item.querySelector('a[href^="tel:"]');
                                const emailEl = item.querySelector('a[href^="mailto:"]');
                                const webEl = item.querySelector('a.website') || item.querySelector('a[href^="http"]:not([href*="dasoertliche.de"])');
                                const detailLink = item.querySelector('h2 a') ? item.querySelector('h2 a').href : null;
                                
                                if (nameEl) {
                                    results.push({
                                        name: nameEl.innerText.trim(),
                                        address: addressEl ? addressEl.innerText.trim() : null,
                                        phone: phoneEl ? phoneEl.innerText.trim() : null,
                                        email: emailEl ? emailEl.href.replace('mailto:', '').trim() : null,
                                        website: webEl ? webEl.href : null,
                                        detail_url: detailLink
                                    });
                                }
                            });
                        }
                        
                        return results;
                    }"""
                )
                
                logger.info(f"[{self.job_id}] Page {page_num}: found {len(cards)} card(s)")
                
                if not cards:
                    if page_num == 1:
                        logger.info(f"[{self.job_id}] No results found for this search.")
                    else:
                        logger.info(f"[{self.job_id}] No more results — pagination complete.")
                    break
                    
                for card in cards:
                    while self._paused and not self._cancelled:
                        await asyncio.sleep(0.1)
                    if self._cancelled:
                        break
                        
                    if yielded_count >= self.config.max_results:
                        break

                    # Enforce trial limit per-lead
                    if not LicenseManager.can_extract():
                        logger.warning(f"[{self.job_id}] Trial daily limit reached. Stopping scrape.")
                        self._cancelled = True
                        break

                    company_name = card.get('name')
                    
                    # Skip duplicate names to prevent yielding repeated sub-departments
                    if company_name in processed_names:
                        continue
                    if company_name:
                        processed_names.add(company_name)

                    detail_url = card.get('detail_url')
                    if not detail_url:
                        # Skip sub-departments and nested entries that don't have their own detail page
                        continue

                    if detail_url in processed_urls:
                        continue
                    processed_urls.add(detail_url)

                    # Extract basic info
                    address = card.get('address')
                    phone = card.get('phone')
                    email = card.get('email')
                    website = card.get('website')
                    
                    # Clean up phone if it's like "Tel. 0123"
                    if phone and " " in phone and not phone.startswith("+"):
                        phone = phone.replace("Tel. ", "").replace("Tel: ", "").strip()
                        
                    # Detail page fallback for email/website
                    if (not email or not website) and detail_url:
                        try:
                            # Use in-page fetch() to get detail page HTML silently
                            html = await page.evaluate(
                                """async (url) => {
                                    try {
                                        const res = await fetch(url);
                                        return await res.text();
                                    } catch (e) {
                                        return null;
                                    }
                                }""",
                                detail_url
                            )
                            if html:
                                def parse_detail(html_text: str, current_email: str, current_website: str):
                                    em = current_email
                                    web = current_website
                                    
                                    # Extract email from raw HTML string (much faster than serializing soup)
                                    if not em:
                                        emails = extract_emails_from_html(html_text)
                                        if emails:
                                            em = emails[0]
                                            
                                    # Extract website using Regex instead of BeautifulSoup to prevent GIL-locking the UI thread!
                                    if not web:
                                        import re
                                        # Find all hrefs starting with http or https
                                        for match in re.finditer(r'href\s*=\s*["\'](https?://[^"\']+)["\']', html_text, re.IGNORECASE):
                                            href = match.group(1).strip()
                                            ignore_list = ["dasoertliche.de", "facebook.com", "instagram.com", "twitter.com", "google.com", "bahn.de", "dtme.de", "golocal.de", "vrs.de", "xing.com", "linkedin.com"]
                                            if not any(x in href.lower() for x in ignore_list):
                                                web = href
                                                break
                                    return em, web
                                
                                # Offload CPU-heavy parsing to thread pool to prevent freezing the UI thread
                                em, web = await asyncio.to_thread(parse_detail, html, email, website)
                                if em: email = em
                                if web: website = web
                        except Exception as detail_exc:
                            logger.debug(f"[{self.job_id}] Failed to fetch detail page {detail_url}: {detail_exc}")
                    
                    if not email and website and self.crawler and self.config.scrape_emails:
                        crawled_email, source, socials = await self.crawler.find_email(website, company_name=company_name)
                        if crawled_email:
                            email = crawled_email
                            logger.debug(f"[{self.job_id}] Found email via crawler for {company_name}: {crawled_email}")
                            
                    if self._cancelled:
                        break

                    record = LeadRecord(
                        source_type=SourceType.DAS_OERTLICHE,
                        source_url=detail_url or DAS_OERTLICHE_URL,
                        search_query=f"{keyword} in {city}",
                        company_name=company_name,
                        job_title=keyword,
                        category=keyword,
                        address=address,
                        phone=phone,
                        email=email,
                        website=website,
                        city=city
                    )
                    
                    LicenseManager.record_extraction()
                    yield record
                    yielded_count += 1
                
                if self._cancelled or yielded_count >= self.config.max_results:
                    break
                    
                next_page_exists = await page.evaluate(
                    """() => {
                        const nextBtn = document.querySelector('a.next') || document.querySelector('a[rel="next"]') || document.querySelector('a[title="zur nächsten Seite"]');
                        if (nextBtn) {
                            nextBtn.click();
                            return true;
                        }
                        return false;
                    }"""
                )
                
                if not next_page_exists:
                    logger.info(f"[{self.job_id}] No next page button found. Pagination complete.")
                    break
                    
                logger.info(f"[{self.job_id}] Navigating to next page...")
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                await asyncio.sleep(2)
                page_num += 1

        except Exception as exc:
            logger.error(f"[{self.job_id}] Das Oertliche scraper error: {exc}", exc_info=True)
        finally:
            try:
                await page.close()
            except Exception:
                pass  # Browser may have already crashed (e.g. SSL/TLS driver error)
