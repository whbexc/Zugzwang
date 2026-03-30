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
                        await asyncio.sleep(1.5)
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
            if self._cancelled: return
            success = await self.session.navigate(page, url, wait_until="domcontentloaded")
            if not success or self._cancelled:
                logger.error(f"[{self.job_id}] Failed to load Aubi-Plus search page")
                return

            # CRITICAL: Dismiss cookie modal FIRST before any other interaction
            await self._dismiss_cookie_modal(page)
            if self._cancelled: return

            # Wait for page to settle after cookie dismissal
            await asyncio.sleep(1)

            # Step 1: Input search parameters
            location_query = self.config.city
            if not location_query and self.config.country and self.config.country != "Germany":
                location_query = self.config.country

            # Fill search inputs using type + autocomplete selection (critical for results)
            # This avoids the redirect to /lass-dich-finden/
            for sel_m, sel_a in [("#mSuggest", "#aSuggest"), ("#mSuggestModal", "#aSuggestModal")]:
                try:
                    el_m = await page.query_selector(sel_m)
                    if el_m and await el_m.is_visible():
                        # Fill Beruf (Job)
                        await el_m.click()
                        await el_m.fill("") # Clear first
                        await el_m.type(self.config.job_title, delay=50)
                        await asyncio.sleep(1.5) # Wait for dropdown
                        
                        # Click the first matching dropdown item
                        dropdown = await page.query_selector(".dropdown-menu, .autocomplete")
                        if dropdown and await dropdown.is_visible():
                            suggestion = await dropdown.query_selector(".dropdown-item, .autocomplete-suggestion")
                            if suggestion:
                                await suggestion.click()
                                await asyncio.sleep(0.5)

                        # Fill Ort (Location)
                        if location_query:
                            el_a = await page.query_selector(sel_a)
                            if el_a:
                                await el_a.click()
                                await el_a.fill("")
                                await el_a.type(location_query, delay=50)
                                await asyncio.sleep(1.5)
                                
                                dropdown = await page.query_selector(".dropdown-menu, .autocomplete")
                                if dropdown and await dropdown.is_visible():
                                    suggestion = await dropdown.query_selector(".dropdown-item, .autocomplete-suggestion")
                                    if suggestion:
                                        await suggestion.click()
                                        await asyncio.sleep(0.5)
                        break
                except Exception as e:
                    logger.debug(f"[{self.job_id}] Autocomplete selection failed: {e}")
                    continue

            if self._cancelled: return
            # Step 2: Apply filters
            if self.config.offer_type or self.config.latest_offers_only:
                logger.info(f"[{self.job_id}] Applying search filters for: {self.config.job_title or 'Latest Offers'}")
                await self._apply_filters(page)
            
            if self._cancelled: return

            # Step 3: Trigger search via JS click (avoids interception issues)
            searched = False
            for btn_sel in [".btn-info", "button.btn-info", "button[type='submit']", "button:has-text('STELLEN FINDEN')"]:
                try:
                    if self._cancelled: break
                    btn = await page.query_selector(btn_sel)
                    if btn and await btn.is_visible():
                        # JS click is more reliable against overlays
                        await btn.evaluate("el => el.click()")
                        searched = True
                        logger.debug(f"[{self.job_id}] Search triggered with: {btn_sel}")
                        break
                except Exception:
                    continue

            if not searched and not self._cancelled:
                try:
                    await page.keyboard.press("Enter")
                except Exception:
                    pass

            if self._cancelled: return

            # Wait for results to load
            await asyncio.sleep(5)

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
                    ".my-3.text-primary-dark.overflow-hidden.rounded-3",  # exact from extension
                    ".my-3.text-primary-dark",                              # partial match
                    "article",                                             # generic container
                    "a.stretched-link",                                     # direct link harvest
                    "[class*='text-primary-dark']",                         # broad matching
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
                        link_el = await card.query_selector("a.stretched-link, h2 a, a:not([href='#'])")
                        if not link_el:
                            continue
                        href = await link_el.get_attribute("href")
                        title_text = ""
                        title_el = await card.query_selector("h2, .h4, .card-title")
                        if title_el:
                            title_text = (await title_el.inner_text()).strip()
                        if not title_text:
                            title_text = (await link_el.inner_text()).strip()

                    if not href or href == "#":
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
                    await asyncio.sleep(1.0)
                
                if self._cancelled or yielded_count >= self.config.max_results:
                    break
                
                # Step 3: Pagination
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)

                # Debug: log pagination HTML
                try:
                    pagination_html = await page.evaluate("""
                        () => {
                            const pag = document.querySelector('.pagination, nav[aria-label*="pagination"], ul.pagination');
                            return pag ? pag.outerHTML.substring(0, 500) : 'NO PAGINATION FOUND';
                        }
                    """)
                    logger.debug(f"[{self.job_id}] Pagination HTML: {pagination_html}")
                except Exception:
                    pass

                next_btn = await page.query_selector(
                    'li.page-item a[rel="next"], '
                    'a.page-link[aria-label*="Next"], '
                    'a.page-link[aria-label*="Weiter"], '
                    'a.page-link[title*="Nächste"], '
                    'a.page-link[title*="Weiter"], '
                    'a[rel="next"], '
                    '.pagination a:last-child'
                )
                            
                if next_btn:
                    next_url = await next_btn.get_attribute("href")
                    if next_url and next_url != "#":
                        full_next = urljoin("https://www.aubi-plus.de", next_url)
                        logger.info(f"[{self.job_id}] Next page: {full_next}")
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
        """Map UI offer types to Aubi-Plus specific checkboxes."""
        try:
            ot = self.config.offer_type or ""
            targets = []
            
            if "Ausbildung" in ot or "Studium" in ot:
                targets.extend(["fTyp_ausbildung", "fTyp_duales-studium", "fTyp_studium"])
            if "Praktikum" in ot or "Werkstudent" in ot:
                targets.extend(["fTyp_schuelerpraktikum", "fTyp_studentenpraktikum", "fTyp_werkstudent"])
            
            if self.config.latest_offers_only:
                targets.append("s_aktualitaet")
            
            if not targets:
                return

            # Open filter dropdown
            filter_btn = await page.query_selector(".btn-filter")
            if filter_btn:
                # Check if it's already open by looking for 'show' class
                is_open = await filter_btn.evaluate("el => el.classList.contains('show')")
                if not is_open:
                    logger.debug(f"[{self.job_id}] Opening filter dropdown")
                    await filter_btn.click()
                    await asyncio.sleep(1)
                
            # Select target checkboxes
            for target_id in targets:
                # Re-query filter button each time to handle potential DOM updates
                filter_btn = await page.query_selector(".btn-filter")
                if not filter_btn:
                    break

                # Re-open dropdown if it closed
                is_open = await filter_btn.evaluate("el => el.classList.contains('show')")
                if not is_open:
                    await filter_btn.click()
                    await asyncio.sleep(1)

                checkbox = await page.query_selector(f"#{target_id}")
                if checkbox:
                    is_checked = await checkbox.is_checked()
                    if not is_checked:
                        # Click the label to toggle checkbox (JS click is safer here)
                        label = await page.query_selector(f'label[for="{target_id}"]')
                        if label:
                            await label.evaluate("el => el.click()")
                            # Dropdown usually closes here, so we wait for dynamic updates
                            await asyncio.sleep(1.5)
            
            # Close dropdown if still open
            filter_btn = await page.query_selector(".btn-filter")
            if filter_btn:
                is_open = await filter_btn.evaluate("el => el.classList.contains('show')")
                if is_open:
                    await filter_btn.click()
                    await asyncio.sleep(0.5)
                
        except Exception as e:
            logger.warning(f"[{self.job_id}] Could not apply filters: {e}")

    async def _fetch_html_in_page(self, page, url: str) -> str | None:
        r"""
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
        r"""
        Parse detail page HTML using same field extraction logic as aubiplus_script.js.
        
        JS reference (lines 144-178):
            const companyNameEl = doc.querySelector('.fs-6.mb-0.lh-1');
            const locationIcons = doc.querySelectorAll('.fa-location-dot');
            const emailBewerbung = doc.querySelector('#emailbewerbung');
            const mailtoLinks = Array.from(doc.querySelectorAll('a[href^="mailto:"]'));
            regex: ([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\\.[a-zA-Z0-9_-]+)
        """
        from bs4 import BeautifulSoup
        doc = BeautifulSoup(html, "html.parser")

        # 1. Company Name — mirrors JS: doc.querySelector('.fs-6.mb-0.lh-1')
        company_name = ""
        for sel in [".fs-6.mb-0.lh-1", "a[href*='/unternehmen/']", "h2.h4 a"]:
            el = doc.select_one(sel)
            if el:
                company_name = re.sub(r'\s+', ' ', el.get_text()).strip()
                break

        # 2. Address — mirrors JS: locationIcons[i].nextElementSibling (SPAN)
        address = ""
        for icon in doc.select(".fa-location-dot"):
            sib = icon.find_next_sibling()
            if sib and sib.name in ("span", "div") and len(sib.get_text(strip=True)) > 3:
                address = sib.get_text(strip=True)
                break

        # 3. Phone
        phone = ""
        phone_el = doc.select_one(".phoneNumber, a[href^='tel:']")
        if phone_el:
            phone = phone_el.get_text(strip=True)

        # 4. Contact person
        contact_person = ""
        for hdr in doc.select("h3, h4"):
            if "kontakt" in hdr.get_text().lower() or "ansprechpartner" in hdr.get_text().lower():
                container = hdr.find_parent(class_="card-body") or hdr.parent
                if container:
                    name_el = container.select_one("strong, b, p.fw-bold, .h5")
                    if name_el:
                        contact_person = name_el.get_text(strip=True)
                break

        # 5. Email — mirrors JS 3-tier logic (lines 158-178):
        #    Tier 1: #emailbewerbung
        #    Tier 2: any a[href^="mailto:"] with @
        #    Tier 3: regex on .card-body text
        email = ""

        # Tier 1: #emailbewerbung (JS line 158)
        el = doc.select_one("#emailbewerbung")
        if el and el.get("href", "").startswith("mailto:"):
            email = el["href"].replace("mailto:", "").split("?")[0].strip()

        # Tier 2: any mailto link (JS lines 162-166)
        if not email:
            for a in doc.select('a[href^="mailto:"]'):
                candidate = a["href"].replace("mailto:", "").split("?")[0].strip()
                if "@" in candidate:
                    email = candidate
                    break

        # Tier 3: regex fallback on card bodies (JS lines 167-176)
        if not email:
            for cb in doc.select(".card-body.p-4, .card-body"):
                match = _EMAIL_REGEX.search(cb.get_text())
                if match:
                    email = match.group(1).strip()
                    break

        # Final full-page regex fallback
        if not email:
            match = _EMAIL_REGEX.search(doc.get_text())
            if match:
                email = match.group(1).strip()

        return {
            "company_name": company_name,
            "address":      address,
            "phone":        phone,
            "contact_person": contact_person,
            "email":        email,
        }

    async def _click_reveal_email(self, url: str) -> str:
        """
        Handle 'E-Mail anzeigen' button — requires actual browser click.
        
        The Kontakt card hides the email behind a JS-triggered reveal.
        Static fetch() returns the button but NOT the email.
        We must open a real page, click the button, then read the revealed email.
        
        Selectors to try (in order):
          1. a:has-text('E-Mail anzeigen')   ← the teal link in Kontakt card
          2. button:has-text('E-Mail')        ← button variant
          3. .reveal-email, [data-reveal]     ← generic reveal patterns
          4. After click: a[href^='mailto:']  ← revealed mailto link
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

            # Wait for Kontakt section to load
            await asyncio.sleep(1.5)

            # Find the "E-Mail anzeigen" link/button
            reveal_selectors = [
                "a:has-text('E-Mail anzeigen')",
                "a:has-text('E-Mail zeigen')",
                "a:has-text('Email anzeigen')",
                "button:has-text('E-Mail anzeigen')",
                "button:has-text('E-Mail')",
                ".reveal-email",
                "[data-reveal-email]",
                "a[href*='reveal'], a[href*='email-show']",
            ]

            reveal_el = None
            for sel in reveal_selectors:
                try:
                    reveal_el = await detail_page.query_selector(sel)
                    if reveal_el:
                        logger.debug(f"[{self.job_id}] Found reveal button with selector: {sel}")
                        break
                except:
                    continue

            if not reveal_el:
                logger.debug(f"[{self.job_id}] No reveal button found at {url}")
                return ""

            # Click it and wait for the email to appear
            await reveal_el.click(force=True)
            await asyncio.sleep(1.5)  # Wait for JS to inject the email

            # Strategy 1: mailto link appeared after click
            for mail_sel in [
                "a[href^='mailto:']",
                "#emailbewerbung",
                ".kontakt-email",
                ".email-revealed",
            ]:
                el = await detail_page.query_selector(mail_sel)
                if el:
                    href = await el.get_attribute("href") or ""
                    text = await el.inner_text()
                    if href.startswith("mailto:"):
                        email = href.replace("mailto:", "").split("?")[0].strip()
                        if "@" in email:
                            logger.info(f"[{self.job_id}] Revealed email (mailto): {email}")
                            return email
                    # Sometimes it's plain text in the element
                    if "@" in text:
                        email = text.strip()
                        logger.info(f"[{self.job_id}] Revealed email (text): {email}")
                        return email

            # Strategy 2: regex scan the full page after reveal
            body_text = await detail_page.evaluate("document.body.innerText")
            match = _EMAIL_REGEX.search(body_text)
            if match:
                email = match.group(1).strip()
                logger.info(f"[{self.job_id}] Revealed email (regex): {email}")
                return email

            # Strategy 3: check if the reveal link itself became a mailto
            try:
                href_after = await reveal_el.get_attribute("href") or ""
                if href_after.startswith("mailto:"):
                    email = href_after.replace("mailto:", "").split("?")[0].strip()
                    if "@" in email:
                        return email
            except:
                pass

            logger.debug(f"[{self.job_id}] Reveal clicked but no email found at {url}")
            return ""

        except Exception as e:
            logger.debug(f"[{self.job_id}] Reveal click failed for {url}: {e}")
            return ""
        finally:
            if detail_page:
                await detail_page.close()

    async def _extract_job_detail(self, url: str, page=None) -> LeadRecord | None:
        """
        Fast detail extraction using in-page fetch() — matches aubiplus_script.js approach.
        
        Flow:
          1. In-page fetch() for HTML — no new tab, ~100ms
          2. Parse with BeautifulSoup — 3-tier email extraction
          3. If no email found → click 'E-Mail anzeigen' button in real browser tab
          4. Fallback: open new_page() if fetch fails entirely
        """
        try:
            # Step 1: In-page fetch — fast path, no new tab
            html = await self._fetch_html_in_page(page, url) if page else None

            # Fallback: if in-page fetch fails open a real tab for HTML
            if not html:
                logger.debug(f"[{self.job_id}] In-page fetch failed, falling back to new_page for {url}")
                detail_page = None
                try:
                    detail_page = await self.session.new_page()
                    success = await self.session.navigate(detail_page, url, wait_until="domcontentloaded", timeout=30000)
                    if not success:
                        return None
                    await asyncio.sleep(self.config.delay_min)
                    html = await detail_page.content()
                finally:
                    if detail_page:
                        await detail_page.close()

            if not html:
                return None

            # Step 2: Parse static HTML in memory
            fields = self._parse_detail_html(html, url)

            # Step 3: If no email in static HTML → need real browser click
            # The "E-Mail anzeigen" button requires JS execution
            if not fields["email"] and self.config.scrape_emails:
                logger.debug(f"[{self.job_id}] No email in static HTML, trying reveal click for {url}")
                revealed_email = await self._click_reveal_email(url)
                if revealed_email:
                    fields["email"] = revealed_email
                else:
                    # Still no email after reveal attempt — skip
                    return None

            # Polite delay — matches extension's 1000ms sleep
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
            )

        except Exception as e:
            logger.warning(f"[{self.job_id}] Error extracting {url}: {e}")
            self._total_errors += 1
            return None
