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

_DEDUP_LOG_EVERY = 5  # emit a JOB_LOG every N deduplicated records to avoid spam

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

    async def _dismiss_cookie_modal(self, page) -> None:
        """
        Dismiss Aubi-Plus cookie modal which blocks all clicks.
        Log shows: cookie-manager modal intercepts pointer events 54x times.
        Must be dismissed BEFORE any other interaction.
        """
        try:
            # Wait up to 5s for cookie modal to appear
            for _ in range(10):
                modal = await page.query_selector("#cookie-manager.show, .cookie-manager.show")
                if modal:
                    break
                await asyncio.sleep(0.5)

            # Try every possible accept button selector
            accept_selectors = [
                "button#cookie-manager-accept-all",
                "button#cookie-accept-all",
                ".cookie-manager button.btn-primary",
                ".cookie-manager button.btn-success",
                "button:has-text('Alle akzeptieren')",
                "button:has-text('Akzeptieren')",
                "button:has-text('Accept all')",
                "button:has-text('Accept')",
                ".cookie-manager .btn",
            ]

            for sel in accept_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        # Use JS click to bypass interception
                        await btn.evaluate("el => el.click()")
                        logger.debug(f"[{self.job_id}] Cookie modal dismissed with: {sel}")
                        await asyncio.sleep(0.5)
                        # Verify modal is gone
                        modal_gone = await page.query_selector("#cookie-manager.show")
                        if not modal_gone:
                            return
                except Exception:
                    continue

            # Nuclear option: hide the modal via JS if clicking fails
            await page.evaluate("""
                () => {
                    const modal = document.querySelector('#cookie-manager');
                    if (modal) {
                        modal.style.display = 'none';
                        modal.classList.remove('show');
                        document.body.classList.remove('modal-open');
                        const backdrop = document.querySelector('.modal-backdrop');
                        if (backdrop) backdrop.remove();
                    }
                }
            """)
            logger.debug(f"[{self.job_id}] Cookie modal force-hidden via JS")
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.debug(f"[{self.job_id}] Cookie dismiss error (non-fatal): {e}")

    async def scrape(self) -> AsyncGenerator[LeadRecord, None]:
        logger.info(f"[{self.job_id}] Aubi-Plus scrape: '{self.config.job_title}' in '{self.config.city or self.config.country}'")
        
        url = "https://www.aubi-plus.de/suchmaschine/suche/"
        
        page = await self.session.new_page()
        try:
            success = await self.session.navigate(page, url, wait_until="domcontentloaded")
            if not success:
                logger.error(f"[{self.job_id}] Failed to load Aubi-Plus search page")
                return

            # CRITICAL: Dismiss cookie modal FIRST before any other interaction
            # Log shows it was intercepting pointer events 54+ times
            await self._dismiss_cookie_modal(page)

            # Wait for page to settle after cookie dismissal
            await asyncio.sleep(0.3)

            # Step 1: Input search parameters
            location_query = self.config.city
            if not location_query and self.config.country and self.config.country != "Germany":
                location_query = self.config.country

            # Fill search inputs — use JS fill to avoid autocomplete dropdown interception
            filled = False
            for sel_m, sel_a in [("#mSuggest", "#aSuggest"), ("#mSuggestModal", "#aSuggestModal")]:
                try:
                    el_m = await page.query_selector(sel_m)
                    if el_m and await el_m.is_visible():
                        # JS fill bypasses autocomplete suggestion interception
                        await el_m.evaluate(f"el => {{ el.value = {repr(self.config.job_title)}; el.dispatchEvent(new Event('input')); }}")
                        await asyncio.sleep(0.3)
                        # Dismiss any autocomplete dropdown that appears
                        await page.evaluate("() => { const ac = document.querySelector('.autocomplete'); if (ac) ac.style.display = 'none'; }")
                        if location_query:
                            el_a = await page.query_selector(sel_a)
                            if el_a:
                                await el_a.evaluate(f"el => {{ el.value = {repr(location_query)}; el.dispatchEvent(new Event('input')); }}")
                                await asyncio.sleep(0.3)
                                await page.evaluate("() => { const ac = document.querySelector('.autocomplete'); if (ac) ac.style.display = 'none'; }")
                        filled = True
                        break
                except Exception as e:
                    logger.debug(f"[{self.job_id}] Input fill failed for {sel_m}: {e}")
                    continue

            # Verify we landed on the right page — not /lass-dich-finden/ or similar
            current_url = page.url
            logger.info(f"[{self.job_id}] Current URL after search: {current_url}")
            
            if "lass-dich-finden" in current_url or "register" in current_url or "login" in current_url:
                logger.error(f"[{self.job_id}] Landed on wrong page: {current_url}. Trying direct URL.")
                # Force navigate to results
                kw = self.config.job_title.replace(' ', '+')
                loc = (location_query or "").replace(' ', '+')
                fallback_url = f"https://www.aubi-plus.de/suchmaschine/suche/?what={kw}&where={loc}"
                await self.session.navigate(page, fallback_url, wait_until="domcontentloaded")
                await asyncio.sleep(0.3)
                logger.info(f"[{self.job_id}] Fallback URL: {page.url}")

            # Replaced UI click filtering with direct URL parameters to speed up search

            # Step 3: Build search URL using Aubi-Plus's INTERNAL parameter format.
            # ⚠ Critical:
            #   - Use mSuggest/aSuggest so pagination links carry the search context.
            #   - Resolve aSuggestLat/aSuggestLon via Nominatim geocoding so Aubi-Plus
            #     uses its geo-radius filter (fGeo). Without real coords it falls back to
            #     text-only city matching → ~6 results. With coords + fGeo=50 → 168+ results.
            from urllib.parse import quote_plus
            import json, urllib.request as _ureq

            per_page = min(max(self.config.max_results, 20), 50)
            loc = (location_query or "").strip()

            # Geocode the city name → lat/lon (Nominatim, no API key needed)
            lat, lon = 0.0, 0.0
            if loc:
                try:
                    geo_url = (
                        f"https://nominatim.openstreetmap.org/search"
                        f"?q={quote_plus(loc + ', Germany')}&format=json&limit=1"
                    )
                    geo_req = _ureq.Request(geo_url, headers={"User-Agent": "ZUGZWANG-LeadHunter/1.0"})
                    with _ureq.urlopen(geo_req, timeout=6) as _r:
                        geo_data = json.loads(_r.read().decode())
                    if geo_data:
                        lat = round(float(geo_data[0]["lat"]), 4)
                        lon = round(float(geo_data[0]["lon"]), 4)
                        logger.info(f"[{self.job_id}] Geocoded '{loc}' → lat={lat}, lon={lon}")
                    else:
                        logger.warning(f"[{self.job_id}] Nominatim returned no results for '{loc}', using text-only search")
                except Exception as _ge:
                    logger.warning(f"[{self.job_id}] Geocoding failed ({_ge}), falling back to text-only search")

            # Map offer_types to Aubi-Plus new array params (fTyp[])
            ftyp_params = []
            ot_lower = (self.config.offer_type or "").lower()
            
            if "ausbildung" in ot_lower:
                ftyp_params.append("ausbildung")
            if "studium" in ot_lower:
                ftyp_params.append("duales-studium")
                ftyp_params.append("studium")
            if "praktikum" in ot_lower:
                ftyp_params.append("schuelerpraktikum")
                ftyp_params.append("studentenpraktikum")
            if "werkstudent" in ot_lower:
                ftyp_params.append("werkstudent")
                
            ftyp_query = ""
            for typ in ftyp_params:
                ftyp_query += f"&fTyp%5B%5D={typ}"
                
            # Handle sorting
            sort_param = "aktualitaet" if self.config.latest_offers_only else "relevanz"

            # fGeo=100 → 100 km radius around the geocoded point
            fgeo_param = "&fGeo=100&fLand%5B0%5D=deutschland" if (lat and lon) else ""
            
            search_url = (
                "https://www.aubi-plus.de/suchmaschine/suche/?"
                f"mSuggest={quote_plus(self.config.job_title.strip())}"
                f"&aSuggest={quote_plus(loc)}"
                f"&aSuggestLat={lat}&aSuggestLon={lon}"
                f"{ftyp_query}"
                "&fBlitzbewerbung=0"
                f"&anzahl={per_page}"
                f"&s={sort_param}"
                + fgeo_param
            )
            logger.info(f"[{self.job_id}] Navigating directly to search URL: {search_url}")
            success = await self.session.navigate(page, search_url, wait_until="domcontentloaded")
            if not success:
                logger.error(f"[{self.job_id}] Failed to load search results page")
                return
            # Wait for results to load
            await asyncio.sleep(0.3)

            # Debug: log what's actually on the page
            page_url = page.url
            logger.info(f"[{self.job_id}] Current URL after search: {page_url}")
            
            # Count what cards exist on page for debugging
            try:
                card_counts = await page.evaluate("""
                    () => ({
                        card: document.querySelectorAll('.card').length,
                        myThree: document.querySelectorAll('.my-3.text-primary-dark').length,
                        full: document.querySelectorAll('.my-3.text-primary-dark.overflow-hidden.rounded-3').length,
                        jobCard: document.querySelectorAll('[class*="text-primary-dark"]').length,
                        article: document.querySelectorAll('article').length,
                        stretched: document.querySelectorAll('a.stretched-link').length,
                    })
                """)
                logger.info(f"[{self.job_id}] Card counts on page: {card_counts}")
            except Exception as e:
                logger.debug(f"[{self.job_id}] Card count debug failed: {e}")
            
            yielded_count = 0
            processed_urls = set()
            
            while not self._cancelled and yielded_count < self.config.max_results:
                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.5)
                if self._cancelled:
                    break
                
                # Exact selector from aubiplus_script.js line 107:
                # cards = docToSearch.querySelectorAll('.my-3.text-primary-dark.overflow-hidden.rounded-3')
                # Try multiple fallbacks in case class names changed
                job_cards = []
                for card_sel in [
                    ".my-3.overflow-hidden.rounded-3",                      # Matches both premium and standard cards
                    ".my-3.text-primary-dark.overflow-hidden.rounded-3",    # premium exact
                    ".my-3.text-primary-dark",                              # partial match
                    "article.job-card",                                     # semantic fallback
                    "a.stretched-link",                                     # direct link harvest
                ]:
                    job_cards = await page.query_selector_all(card_sel)
                    if job_cards:
                        logger.info(f"[{self.job_id}] Found {len(job_cards)} cards with selector: {card_sel}")
                        break

                if not job_cards:
                    # Last resort: grab ALL stretched-links on the page
                    job_cards = await page.query_selector_all("a.stretched-link")
                    logger.info(f"[{self.job_id}] Fallback: found {len(job_cards)} stretched-links")

                if not job_cards:
                    logger.info(f"[{self.job_id}] No cards found on page. Ending.")
                    break
                    
                items_to_visit = []
                for card in job_cards:
                    # If card is already an <a> tag (stretched-link fallback)
                    tag = await card.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "a":
                        href = await card.get_attribute("href")
                        title_text = await card.inner_text()
                        link_el = card
                    else:
                        # Find the correct link prioritizing stretched-link or heading link
                        link_el = await card.query_selector("a.stretched-link")
                        if not link_el:
                            link_el = await card.query_selector("h2 a, h3 a, h4 a, .card-title a")
                        if not link_el:
                            # Fallback: get first valid content link
                            links = await card.query_selector_all("a[href]")
                            for a in links:
                                h = await a.get_attribute("href")
                                if h and h != "#" and not h.startswith("javascript"):
                                    link_el = a
                                    break
                        if not link_el:
                            continue
                        href = await link_el.get_attribute("href")
                        title_text = ""
                        title_el = await card.query_selector("h2, .h4, .card-title")
                        if title_el:
                            title_text = (await title_el.inner_text()).strip()
                        if not title_text:
                            title_text = (await link_el.inner_text()).strip()

                    if not href or href == "#" or href.startswith("javascript"):
                        continue

                    full_url = urljoin("https://www.aubi-plus.de", href)
                    if full_url not in processed_urls:
                        processed_urls.add(full_url)
                        items_to_visit.append({"url": full_url, "title": title_text[:60]})
                
                # Visit the details — use parallel batch fetch like extension
                # Extension: sequential with 1s sleep
                # We do batches of 5 concurrent in-page fetches (5x faster)
                BATCH_SIZE = 5
                for batch_start in range(0, len(items_to_visit), BATCH_SIZE):
                    if self._cancelled or yielded_count >= self.config.max_results:
                        break
                    while self._paused and not self._cancelled:
                        await asyncio.sleep(0.5)

                    batch = items_to_visit[batch_start:batch_start + BATCH_SIZE]

                    # Fetch all in batch concurrently using semaphore
                    semaphore = asyncio.Semaphore(BATCH_SIZE)

                    async def fetch_one(item):
                        async with semaphore:
                            return await self._extract_job_detail(item["url"], page=page)

                    records = await asyncio.gather(*[fetch_one(item) for item in batch], return_exceptions=True)

                    for record in records:
                        if self._cancelled or yielded_count >= self.config.max_results:
                            break
                        if isinstance(record, Exception) or record is None:
                            continue
                        if not (record.company_name or record.email or record.address or record.phone):
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

                    # Polite delay between batches — mirrors extension's 1000ms sleep
                    await asyncio.sleep(0.3)
                
                if self._cancelled or yielded_count >= self.config.max_results:
                    break
                
                # Step 3: Pagination
                # Aubi-Plus uses a.page-link with href containing seite=N
                # The '>' arrow is the last a.page-link on the page.
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(0.5)

                next_page_url = await page.evaluate("""
                    () => {
                        const links = Array.from(document.querySelectorAll('a.page-link'));
                        if (!links.length) return null;

                        // Determine current page number from URL
                        const params = new URLSearchParams(window.location.search);
                        const currentSeite = parseInt(params.get('seite') || '1');
                        const nextSeite = currentSeite + 1;

                        // 1. Prefer an explicit seite=N+1 link
                        const explicitNext = links.find(
                            a => a.href.includes('seite=' + nextSeite) &&
                                 !a.closest('li')?.classList.contains('disabled')
                        );
                        if (explicitNext) return explicitNext.href;

                        // 2. Fallback: last page-link is the '>' arrow button
                        const lastLink = links[links.length - 1];
                        if (
                            lastLink &&
                            lastLink.href &&
                            lastLink.href !== '#' &&
                            lastLink.href !== window.location.href &&
                            !lastLink.closest('li')?.classList.contains('disabled') &&
                            !lastLink.href.includes('seite=' + currentSeite)
                        ) {
                            return lastLink.href;
                        }

                        return null;
                    }
                """)

                if next_page_url:
                    logger.info(f"[{self.job_id}] Next page: {next_page_url}")
                    success = await self.session.navigate(page, next_page_url, wait_until="domcontentloaded")
                    if not success:
                        break
                    await asyncio.sleep(0.5)
                    continue

                logger.info(f"[{self.job_id}] No more pages available.")
                break
                    
            logger.info(f"[{self.job_id}] Scrape finished. Yielded {yielded_count} records.")
            
        except Exception as e:
            logger.error(f"[{self.job_id}] Fatal error during scrape: {e}", exc_info=True)
            self._total_errors += 1
            event_bus.emit(event_bus.JOB_LOG, job_id=self.job_id, level="ERROR", message=f"Aubi-Plus scan aborted: {str(e)}")


    async def _fetch_html_in_page(self, page, url: str) -> str | None:
        """
        Fetch a URL using in-page fetch() — exactly like aubiplus_script.js line 138:
            const response = await fetch(href);
            const text = await response.text();
        
        No new tab opened. Runs inside the existing page context so CORS is
        bypassed (same origin as aubi-plus.de). ~100ms vs ~3s for new_page().
        """
        try:
            html = await page.evaluate("""
                async (url) => {
                    try {
                        const response = await fetch(url, {
                            headers: {
                                'Accept': 'text/html,application/xhtml+xml',
                                'Accept-Language': 'de-DE,de;q=0.9',
                            }
                        });
                        if (!response.ok) return null;
                        return await response.text();
                    } catch(e) {
                        return null;
                    }
                }
            """, url)
            return html
        except Exception as e:
            logger.debug(f"[{self.job_id}] In-page fetch failed for {url}: {e}")
            return None

    def _parse_detail_html(self, html: str, url: str) -> dict:
        """
        Parse Aubi-Plus detail page HTML.
        
        From screenshots:
        - Company: sidebar card top, bold name (.fs-6.mb-0.lh-1 or strong in Kontakt card)
        - Address: Kontakt section bottom (plain text block)
        - Phone: teal link a[href^='tel:'] in Kontakt card
        - Email: HIDDEN behind 'E-Mail anzeigen' link — NOT in static HTML
        - Website: check for company website link
        """
        from bs4 import BeautifulSoup
        doc = BeautifulSoup(html, "html.parser")

        # 1. Company Name
        company_name = ""
        for sel in [
            ".fs-6.mb-0.lh-1",          # sidebar company name
            "a[href*='/unternehmen/']",   # company profile link
            "h1.h2",                      # page title fallback
            "h1",
        ]:
            el = doc.select_one(sel)
            if el:
                company_name = re.sub(r'\s+', ' ', el.get_text()).strip()
                if company_name:
                    break

        # 2. Address — from Kontakt section bottom block (screenshot shows plain address)
        address = ""
        # Find Kontakt heading then grab address text below it
        for kontakt_hdr in doc.find_all(["h2", "h3", "h4", "h5"]):
            if "kontakt" in kontakt_hdr.get_text().lower():
                # Walk siblings/parent for address block
                parent = kontakt_hdr.find_parent(["div", "section", "aside"])
                if parent:
                    # Look for address-like text: street + city pattern
                    for p in parent.find_all(["p", "div", "span"]):
                        txt = p.get_text(separator=" ", strip=True)
                        if re.search(r'\d{5}', txt):  # German postal code
                            address = txt
                            break
                break

        # Fallback address: fa-location-dot sibling
        if not address:
            for icon in doc.select(".fa-location-dot, .fa-map-marker-alt"):
                sib = icon.find_next_sibling()
                if sib and len(sib.get_text(strip=True)) > 3:
                    address = sib.get_text(strip=True)
                    break

        # 3. Phone — teal tel: link in Kontakt card (screenshot shows +49 821...)
        phone = ""
        for a in doc.select("a[href^='tel:']"):
            phone = a.get_text(strip=True)
            if phone:
                break
        if not phone:
            el = doc.select_one(".phoneNumber")
            if el:
                phone = el.get_text(strip=True)

        # 4. Contact person — bold name in Kontakt card
        contact_person = ""
        for kontakt_hdr in doc.find_all(["h2", "h3", "h4", "h5"]):
            if "kontakt" in kontakt_hdr.get_text().lower():
                parent = kontakt_hdr.find_parent(["div", "section", "aside", "article"])
                if parent:
                    for el in parent.select("strong, b, .fw-bold, p strong"):
                        name = el.get_text(strip=True)
                        if name and len(name) > 3 and "@" not in name:
                            contact_person = name
                            break
                break

        # 5. Email — try static HTML first (most listings won't have it)
        # "E-Mail anzeigen" means it's JS-protected → _click_reveal_email handles it
        email = ""
        el = doc.select_one("#emailbewerbung")
        if el and el.get("href", "").startswith("mailto:"):
            email = el["href"].replace("mailto:", "").split("?")[0].strip()

        if not email:
            for a in doc.select('a[href^="mailto:"]'):
                candidate = a["href"].replace("mailto:", "").split("?")[0].strip()
                if "@" in candidate:
                    email = candidate
                    break

        # 6. Company website — for fallback scraping
        website = ""
        for a in doc.select("a[href^='http']"):
            href = a.get("href", "")
            if "aubi-plus" not in href and "google" not in href:
                txt = a.get_text(strip=True).lower()
                if any(w in txt for w in ["website", "homepage", "www", "zur website", "webseite"]):
                    website = href
                    break
        # Also check for explicit website field
        if not website:
            for icon in doc.select(".fa-globe, .fa-link"):
                sib = icon.find_next_sibling("a")
                if sib and sib.get("href", "").startswith("http"):
                    if "aubi-plus" not in sib["href"]:
                        website = sib["href"]
                        break

        # Fallback: Check 'Bewerben' or arbitrary external links if no website found
        if not website:
            for a in doc.select("a.btn[href^='http'], a.button[href^='http']"):
                href = a.get("href", "")
                if "aubi-plus" not in href and "google" not in href and "facebook" not in href:
                    website = href
                    break

        # Check if "E-Mail anzeigen" exists (tells us reveal click is needed)
        has_reveal_btn = bool(doc.find(
            lambda tag: tag.name in ("a", "button", "span", "div") and
            ("e-mail" in tag.get_text().lower() or "email" in tag.get_text().lower()) and 
            ("anzeigen" in tag.get_text().lower() or "zeigen" in tag.get_text().lower())
        ))

        return {
            "company_name":   company_name,
            "address":        address,
            "phone":          phone,
            "contact_person": contact_person,
            "email":          email,
            "website":        website,
            "has_reveal_btn": has_reveal_btn,
        }

    async def _click_reveal_email(self, url: str) -> str:
        """
        Step 5 from screenshot: click 'E-Mail anzeigen' teal link in Kontakt card.
        Opens a real browser tab, dismisses cookie modal, clicks the link,
        reads the revealed mailto href.
        """
        detail_page = None
        try:
            detail_page = await self.session.new_page()
            success = await self.session.navigate(
                detail_page, url,
                wait_until="domcontentloaded",
                timeout=30000
            )
            if not success:
                return ""

            # Dismiss cookie modal if it appears
            await self._dismiss_cookie_modal(detail_page)
            await asyncio.sleep(0.3)

            # Find "E-Mail anzeigen" — exact text from screenshot
            reveal_el = None
            for sel in [
                "a:has-text('E-Mail anzeigen')",
                "a:has-text('E-Mail zeigen')",
                "button:has-text('E-Mail anzeigen')",
                "a:has-text('Email anzeigen')",
                "[data-reveal-email]",
            ]:
                try:
                    el = await detail_page.query_selector(sel)
                    if el:
                        reveal_el = el
                        logger.debug(f"[{self.job_id}] Found reveal btn: {sel}")
                        break
                except Exception:
                    continue

            if not reveal_el:
                logger.debug(f"[{self.job_id}] No 'E-Mail anzeigen' button at {url}")
                return ""

            # Click and wait for JS to inject the mailto
            await reveal_el.evaluate("el => el.click()")
            await asyncio.sleep(0.5)

            # Read revealed email — check mailto links first
            for mail_sel in ["a[href^='mailto:']", "#emailbewerbung"]:
                el = await detail_page.query_selector(mail_sel)
                if el:
                    href = await el.get_attribute("href") or ""
                    if href.startswith("mailto:"):
                        email = href.replace("mailto:", "").split("?")[0].strip()
                        if "@" in email:
                            logger.info(f"[{self.job_id}] Reveal email: {email}")
                            return email
                    # Plain text fallback
                    text = (await el.inner_text()).strip()
                    if "@" in text:
                        logger.info(f"[{self.job_id}] Reveal email (text): {text}")
                        return text

            # Regex scan full page after reveal
            body_text = await detail_page.evaluate("document.body.innerText")
            match = _EMAIL_REGEX.search(body_text)
            if match:
                email = match.group(1).strip()
                logger.info(f"[{self.job_id}] Reveal email (regex): {email}")
                return email

            return ""

        except Exception as e:
            logger.debug(f"[{self.job_id}] Reveal click error: {e}")
            return ""
        finally:
            if detail_page:
                await detail_page.close()

    async def _scrape_company_website(self, website_url: str) -> str:
        """
        Fallback: if no email on Aubi-Plus page and no reveal button,
        fetch the company website and look for a contact email.
        Checks: homepage, /kontakt, /impressum pages.
        """
        if not website_url:
            return ""

        from urllib.parse import urlparse
        base = urlparse(website_url)
        base_url = f"{base.scheme}://{base.netloc}"

        pages_to_try = [
            website_url,
            base_url + "/kontakt",
            base_url + "/impressum",
            base_url + "/kontakt.html",
            base_url + "/contact",
        ]

        for page_url in pages_to_try:
            try:
                html = await self._fetch_html_in_page(None, page_url)
                if not html:
                    # Try via background fetch with aiohttp-style call
                    import urllib.request
                    req = urllib.request.Request(
                        page_url,
                        headers={"User-Agent": "Mozilla/5.0"}
                    )
                    with urllib.request.urlopen(req, timeout=8) as r:
                        html = r.read().decode("utf-8", errors="ignore")

                if not html:
                    continue

                from bs4 import BeautifulSoup
                doc = BeautifulSoup(html, "html.parser")

                # mailto links
                for a in doc.select('a[href^="mailto:"]'):
                    email = a["href"].replace("mailto:", "").split("?")[0].strip()
                    if "@" in email and "example" not in email:
                        logger.info(f"[{self.job_id}] Website email found: {email} at {page_url}")
                        return email

                # Regex scan
                match = _EMAIL_REGEX.search(doc.get_text())
                if match:
                    email = match.group(1).strip()
                    if "example" not in email:
                        logger.info(f"[{self.job_id}] Website email (regex): {email} at {page_url}")
                        return email

            except Exception as e:
                logger.debug(f"[{self.job_id}] Website fetch failed {page_url}: {e}")
                continue

        return ""

    async def _extract_job_detail(self, url: str, page=None) -> LeadRecord | None:
        """
        Exact flow from screenshots:

        1. Fetch HTML (in-page fetch — fast, no new tab)
        2. Parse: company, address, phone, contact person
        3. Check for email in static HTML (rarely present)
        4. If 'E-Mail anzeigen' button exists → click it (Step 5 from screenshot)
        5. If no Kontakt section or still no email → try company website
        6. Return record (even without email if other data exists)
        """
        try:
            # Step 1: Fast fetch — no new tab
            html = await self._fetch_html_in_page(page, url) if page else None

            if not html:
                # Fallback: real tab
                detail_page = None
                try:
                    detail_page = await self.session.new_page()
                    success = await self.session.navigate(
                        detail_page, url,
                        wait_until="domcontentloaded", timeout=30000
                    )
                    if not success:
                        return None
                    await asyncio.sleep(self.config.delay_min)
                    html = await detail_page.content()
                finally:
                    if detail_page:
                        await detail_page.close()

            if not html:
                return None

            # Step 2: Parse static HTML
            fields = self._parse_detail_html(html, url)
            logger.debug(
                f"[{self.job_id}] Parsed {url} — "
                f"company='{fields['company_name']}' "
                f"email='{fields['email']}' "
                f"has_reveal={fields['has_reveal_btn']} "
                f"website='{fields['website']}'"
            )

            # Step 3: Email already in HTML? Done.
            # Step 4: 'E-Mail anzeigen' button → click to reveal
            if not fields["email"] and fields["has_reveal_btn"]:
                logger.info(f"[{self.job_id}] Clicking 'E-Mail anzeigen' at {url}")
                fields["email"] = await self._click_reveal_email(url)

            # Step 5: No email + no reveal btn + has website → scrape website
            if not fields["email"] and fields["website"]:
                logger.info(f"[{self.job_id}] Trying website fallback: {fields['website']}")
                fields["email"] = await self._scrape_company_website(fields["website"])

            # Skip only if scrape_emails is ON and we have absolutely nothing
            if not fields["email"] and self.config.scrape_emails:
                logger.debug(f"[{self.job_id}] No email found, skipping: {url}")
                return None

            await asyncio.sleep(max(self.config.delay_min, 0.5))

            return LeadRecord(
                source_type=SourceType.AUBIPLUS_DE,
                source_url=url,
                search_query=self.config.job_title,
                city=self.config.city,
                company_name=fields["company_name"],
                address=fields["address"],
                email=fields["email"],
                phone=fields["phone"],
                contact_person=fields["contact_person"],
                job_title=self.config.job_title,
            ).normalize()

        except Exception as e:
            logger.warning(f"[{self.job_id}] Error extracting {url}: {e}")
            self._total_errors += 1
            return None
