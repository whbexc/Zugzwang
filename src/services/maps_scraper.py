"""

ZUGZWANG - Google Maps Scraper

Async Playwright scraper for Google Maps business listings.



Key points:

- Goes to google.com/maps and types in the search box (NOT /maps/search/ URL)

- Scrolls mouse wheel to load more results

- Clicks each listing's parent element to open detail panel

- Uses XPath selectors with multiple fallbacks

- headless mode supported, though visible mode is usually more reliable



Improvements over v1:

- Smart waits (waitForSelector) instead of hardcoded sleeps

- Navigation retries via BrowserSession.navigate()

- Business category/type extraction

- Robust review/rating selectors with fallbacks

- Enhanced address parsing (street, city, state, postal code)

- DRY listing collection (no duplicate code)

- "End of results" detection for early stop

- Error tracking with structured log events

- Configurable rate-limit delays via BrowserSession.rate_limiter

- Google consent banner dismissal

"""



from __future__ import annotations

import asyncio

import json

import re

from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional



if TYPE_CHECKING:

    from playwright.async_api import Page

else:

    Page = Any



from .browser import BrowserSession, BrowserError

from .website_crawler import WebsiteEmailCrawler

from .email_extractor import normalize_phone, normalize_website, deduplicate_emails

from ..core.events import event_bus
from ..core.logger import get_logger
from ..core.models import LeadRecord, SearchConfig, SourceType
from ..core.security import LicenseManager



logger = get_logger(__name__)



MAPS_HOME = "https://www.google.com/maps"

LISTING_XPATH = '//a[contains(@href, "https://www.google.com/maps/place")]'



CAPTCHA_SIGNALS = [

    "sicherheitsabfrage", "captcha", "ich bin kein roboter",

    "are you a robot", "bitte bestätigen", "verify you are human",

    "zugriff verweigert", "access denied", "bot-erkennung",

]



# Google Maps shows these when all results have been loaded

END_OF_LIST_SIGNALS = [

    "you've reached the end of the list",

    "ende der liste",

    "no more results",

    "keine weiteren ergebnisse",

]





class GoogleMapsScraper:



    def __init__(self, session: BrowserSession, config: SearchConfig, job_id: str):

        self.session = session

        self.config = config

        self.job_id = job_id

        self.crawler = WebsiteEmailCrawler(session) if config.scrape_emails else None

        self._cancelled = False

        self._paused = False

        self._total_errors = 0

        self._feed_candidates: list[dict[str, Any]] = []

        self._feed_candidate_ids: set[str] = set()

        self._interaction_queue = asyncio.Queue()
        self._captcha_lock = asyncio.Lock()
        event_bus.subscribe(event_bus.CAPTCHA_INTERACTION, self._on_interaction_received)



    def cancel(self):  self._cancelled = True

    def pause(self):   self._paused = True

    def resume(self):  self._paused = False

    def _on_interaction_received(self, job_id: str, interaction: dict, **kw):
        if job_id == self.job_id:
            logger.info(f"[{self.job_id}] Maps user interaction received")
            self._interaction_queue.put_nowait(interaction)

    def _on_solver_completed(self, job_id: str, cookies: list, **kw):
        if job_id == self.job_id:
            logger.info(f"[{self.job_id}] Maps solver reported completion, syncing cookies...")
            self._interaction_queue.put_nowait({"type": "solver_complete", "cookies": cookies})



    # ── Main scrape loop ──────────────────────────────────────────────────



    async def scrape(self) -> AsyncGenerator[LeadRecord, None]:

        query = self._build_query()

        logger.info(f"[{self.job_id}] Google Maps scrape: {query}")



        page = await self.session.new_page()

        page.set_default_timeout(120_000)



        try:

            self._install_search_feed_listener(page)

            logger.info(f"[{self.job_id}] Opening google.com/maps ...")

            success = await self.session.navigate(

                page, MAPS_HOME, timeout=60_000, retries=3,

                wait_until="domcontentloaded",

            )

            if not success:

                raise BrowserError("Failed to load Google Maps after retries")



            await self._wait_for_page_ready(page)

            await self._dismiss_consent_banner(page)



            logger.info(f"[{self.job_id}] Typing search: {query}")

            try:

                search_input = page.locator(

                    '//input[@id="searchboxinput"] | //input[@role="combobox"]'

                ).first

                await search_input.wait_for(state="visible", timeout=15_000)

                await search_input.fill(query)

                await asyncio.sleep(3.0)

                await page.keyboard.press("Enter")

                await asyncio.sleep(5.0)

            except Exception as e:

                raise BrowserError(f"Could not interact with Maps search box: {e}")



            await self._wait_for_listings(page)

            async with self._captcha_lock:
                await self._handle_captcha(page)



            try:

                await page.hover(LISTING_XPATH)

            except Exception:

                pass



            listings = await self._scroll_and_collect_listings(page)

            logger.info(f"[{self.job_id}] Total listings collected: {len(listings)}")



            results_count = 0

            emitted_keys: set[str] = set()



            feed_records = self._build_records_from_feed(query)

            if feed_records:

                logger.info(

                    f"[{self.job_id}] Fast feed parser produced {len(feed_records)} Maps candidates"

                )



            for record in feed_records:

                if self._cancelled or results_count >= self.config.max_results:

                    break



                dedupe_key = record.stable_id()

                if dedupe_key in emitted_keys:

                    continue



                if self.crawler and record.website and not record.email:

                    email, source, socials = await self.crawler.find_email(

                        record.website, record.company_name, self.job_id,
                        bypass_cache=self.config.bypass_cache,
                        extract_social=self.config.extract_social_profiles
                    )

                    if email:

                        record.email = email

                        record.email_source_page = source
                    if socials:
                        record.linkedin = socials.get("linkedin")
                        record.twitter = socials.get("twitter")
                        record.instagram = socials.get("instagram")



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
                emitted_keys.add(dedupe_key)
                logger.info(
                    f"[{self.job_id}] [{results_count}] {record.company_name} "
                    f"| {record.city or ''} | email={'yes' if record.email else 'no'} | feed"
                )
                event_bus.emit(
                    event_bus.JOB_RESULT,
                    job_id=self.job_id,
                    record=record,
                    count=results_count,
                )
                LicenseManager.record_extraction()
                yield record

                await self.session.rate_limiter.wait()



            for i, listing in enumerate(listings):

                if self._cancelled or results_count >= self.config.max_results:

                    break

                while self._paused and not self._cancelled:

                    await asyncio.sleep(0.5)



                try:

                    record = await self._extract_listing(page, listing, query)

                    if not record:

                        continue



                    dedupe_key = record.stable_id()

                    if dedupe_key in emitted_keys:

                        continue



                    if self.crawler and record.website and not record.email:

                        email, source, socials = await self.crawler.find_email(

                            record.website, record.company_name, self.job_id,
                            bypass_cache=self.config.bypass_cache,
                            extract_social=self.config.extract_social_profiles
                        )

                        if email:

                            record.email = email

                            record.email_source_page = source
                        if socials:
                            record.linkedin = socials.get("linkedin")
                            record.twitter = socials.get("twitter")
                            record.instagram = socials.get("instagram")



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
                    emitted_keys.add(dedupe_key)
                    logger.info(
                        f"[{self.job_id}] [{results_count}] {record.company_name} "
                        f"| {record.city or ''} | email={'yes' if record.email else 'no'} | click"
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

                    logger.warning(f"[{self.job_id}] Error on listing {i+1}: {e}")

                    event_bus.emit(

                        event_bus.JOB_LOG,

                        job_id=self.job_id,

                        message=f"Error extracting listing {i+1}: {e}",

                        level="WARNING",

                    )



                await self.session.rate_limiter.wait()

        except BrowserError:

            raise

        except Exception as e:

            if "Target page, context or browser has been closed" in str(e):

                logger.info(f"[{self.job_id}] Browser or page was closed manually. Stopping job gracefully.")

                return

            logger.error(f"[{self.job_id}] Scraper crashed: {e}", exc_info=True)

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



    # ── Listing extraction ────────────────────────────────────────────────



    async def _extract_listing(

        self, page: Page, listing, query: str

    ) -> Optional[LeadRecord]:

        """Click a listing card and extract all business data."""



        # Click the card and wait for the detail panel to load

        await listing.click()

        await self._wait_for_detail_panel(page)

        async with self._captcha_lock:
            await self._handle_captcha(page)



        record = LeadRecord(

            source_type=SourceType.GOOGLE_MAPS,

            search_query=query,

            country=self.config.country,

        )



        # ── Name ──────────────────────────────────────────────────

        try:

            name = await listing.get_attribute("aria-label")

            if name and len(name.strip()) >= 1:

                record.company_name = name.strip()

        except Exception:

            pass



        # Fallback: extract from detail panel header

        if not record.company_name:

            record.company_name = await self._extract_text_with_fallbacks(page, [

                '//h1[contains(@class, "fontHeadlineLarge")]',

                '//h1',

                '//div[@role="main"]//span[contains(@class, "fontHeadline")]',

            ]) or ""



        # ── Category / Business type ──────────────────────────────

        record.category = await self._extract_text_with_fallbacks(page, [

            '//button[contains(@jsaction, "category")]//span',

            '//button[@data-item-id="authority"]/..//span[contains(@class, "fontBodyMedium")]',

            '//div[contains(@class, "fontBodyMedium")]/span[contains(@class, "DkEaL")]',

            '//span[contains(@class, "mgr77e")]',

        ])



        # ── Address ───────────────────────────────────────────────

        try:

            addr = page.locator(

                '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'

            )

            if await addr.count() > 0:

                record.address = (await addr.first.inner_text()).strip()

        except Exception:

            pass



        # Fallback address: aria-label on the address button

        if not record.address:

            try:

                addr_btn = page.locator('//button[@data-item-id="address"]')

                if await addr_btn.count() > 0:

                    label = await addr_btn.first.get_attribute("aria-label")

                    if label:

                        # aria-label is typically "Address: <address>"

                        clean = re.sub(r"^(?:Address|Adresse)\s*:\s*", "", label, flags=re.IGNORECASE)

                        if clean:

                            record.address = clean.strip()

            except Exception:

                pass



        # ── Website ───────────────────────────────────────────────

        try:

            site = page.locator(

                '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'

            )

            if await site.count() > 0:

                raw = (await site.first.inner_text()).strip()

                if raw:

                    record.website = normalize_website(raw)

        except Exception:

            pass



        # Fallback: get the href directly

        if not record.website:

            try:

                site_link = page.locator('//a[@data-item-id="authority"]')

                if await site_link.count() > 0:

                    href = await site_link.first.get_attribute("href")

                    if href and "google" not in href:

                        record.website = normalize_website(href)

            except Exception:

                pass



        # ── Phone ─────────────────────────────────────────────────

        try:

            phone = page.locator(

                '//button[contains(@data-item-id, "phone:tel:")]'

                '//div[contains(@class, "fontBodyMedium")]'

            )

            if await phone.count() > 0:

                record.phone = normalize_phone(

                    (await phone.first.inner_text()).strip()

                )

        except Exception:

            pass



        # Fallback: from aria-label

        if not record.phone:

            try:

                phone_btn = page.locator('//button[contains(@data-item-id, "phone:tel:")]')

                if await phone_btn.count() > 0:

                    label = await phone_btn.first.get_attribute("aria-label")

                    if label:

                        clean = re.sub(r"^(?:Phone|Telefon)\s*:\s*", "", label, flags=re.IGNORECASE)

                        if clean:

                            record.phone = normalize_phone(clean.strip())

            except Exception:

                pass



        # ── Review count ──────────────────────────────────────────

        record.review_count = await self._extract_review_count(page)



        # ── Rating ────────────────────────────────────────────────

        record.rating = await self._extract_rating(page)



        # ── Coordinates from URL ──────────────────────────────────

        try:

            if "/@" in page.url:

                record.maps_url = page.url

                record.source_url = page.url

                coords = page.url.split("/@")[1].split("/")[0].split(",")

                if len(coords) >= 2:

                    record.latitude = float(coords[0])

                    record.longitude = float(coords[1])

        except Exception:

            pass



        # ── Parse city/postal code from address ───────────────────

        if record.address:

            self._parse_address(record)



        return record if record.company_name else None



    # ── Scrolling & listing collection ────────────────────────────────────



    async def _scroll_and_collect_listings(self, page: Page) -> list:

        """Scroll the results sidebar and collect listing card handles."""

        previously_counted = 0

        stall_count = 0

        max_stalls = 1



        while not self._cancelled:

            while self._paused and not self._cancelled:

                await asyncio.sleep(0.5)



            await page.mouse.wheel(0, 10000)

            await asyncio.sleep(3.0)



            count = await page.locator(LISTING_XPATH).count()

            logger.info(f"[{self.job_id}] Listings visible: {count}")



            # Check if we've reached the target

            if count >= self.config.max_results:

                logger.info(f"[{self.job_id}] Reached target: {self.config.max_results}")

                break



            # Detect "end of list" signal

            if await self._is_end_of_list(page):

                logger.info(f"[{self.job_id}] End of results list detected. Total: {count}")

                break



            # Stall detection

            if count == previously_counted:

                stall_count += 1

                if stall_count >= max_stalls:

                    logger.info(

                        f"[{self.job_id}] No new listings after {max_stalls} scrolls. "

                        f"Total: {count}"

                    )

                    break

            else:

                stall_count = 0



            previously_counted = count



        return await self._get_listing_handles(page)



    async def _get_listing_handles(self, page: Page) -> list:

        """Convert listing links to clickable parent card handles."""

        all_items = await page.locator(LISTING_XPATH).all()

        all_items = all_items[: self.config.max_results]



        listings = []

        for item in all_items:

            try:

                parent = item.locator("xpath=..")

                listings.append(parent)

            except Exception:

                listings.append(item)

        return listings



    # ── Review & rating extraction with fallbacks ─────────────────────────



    async def _extract_review_count(self, page: Page) -> Optional[int]:

        """Extract review count from the detail panel with multiple fallbacks."""

        # Strategy 1: jsaction selector

        try:

            rc = page.locator(

                '//button[@jsaction="pane.reviewChart.moreReviews"]//span'

            )

            if await rc.count() > 0:

                txt = (await rc.first.inner_text()).split()[0]

                txt = txt.replace(",", "").replace(".", "")

                return int(txt)

        except Exception:

            pass



        # Strategy 2: aria-label containing review count

        try:

            review_btn = page.locator('//button[contains(@aria-label, "review")]')

            if await review_btn.count() > 0:

                label = await review_btn.first.get_attribute("aria-label")

                if label:

                    m = re.search(r"([\d,.]+)\s*(?:review|Rezension|Bewertung)", label, re.IGNORECASE)

                    if m:

                        num = m.group(1).replace(",", "").replace(".", "")

                        return int(num)

        except Exception:

            pass



        # Strategy 3: text near "reviews" / "Rezensionen"

        try:

            spans = page.locator(

                '//span[contains(text(), "review") or contains(text(), "Rezension") '

                'or contains(text(), "Bewertung")]'

            )

            if await spans.count() > 0:

                txt = (await spans.first.inner_text()).strip()

                m = re.search(r"([\d,.]+)", txt)

                if m:

                    num = m.group(1).replace(",", "").replace(".", "")

                    return int(num)

        except Exception:

            pass



        return None



    async def _extract_rating(self, page: Page) -> Optional[float]:

        """Extract star rating from the detail panel with multiple fallbacks."""

        # Strategy 1: div[role="img"] inside review chart

        try:

            ra = page.locator(

                '//div[@jsaction="pane.reviewChart.moreReviews"]//div[@role="img"]'

            )

            if await ra.count() > 0:

                val = await ra.first.get_attribute("aria-label")

                if val:

                    m = re.search(r"([\d]+[.,][\d])", val)

                    if m:

                        return float(m.group(1).replace(",", "."))

        except Exception:

            pass



        # Strategy 2: any element with aria-label mentioning stars/Sterne

        try:

            star_el = page.locator(

                '//*[contains(@aria-label, "star") or contains(@aria-label, "Stern")]'

            )

            if await star_el.count() > 0:

                label = await star_el.first.get_attribute("aria-label")

                if label:

                    m = re.search(r"([\d]+[.,][\d])", label)

                    if m:

                        return float(m.group(1).replace(",", "."))

        except Exception:

            pass



        # Strategy 3: text-based from detail panel header area

        try:

            header_area = page.locator('//div[@role="main"]')

            if await header_area.count() > 0:

                text = (await header_area.first.inner_text())[:500]

                m = re.search(r"(\d[.,]\d)\s*(?:star|Stern|\u2605)", text, re.IGNORECASE)

                if m:

                    return float(m.group(1).replace(",", "."))

        except Exception:

            pass



        return None



    # ── Helper methods ────────────────────────────────────────────────────



    async def _wait_for_page_ready(self, page: Page, timeout: int = 10_000) -> None:

        """Wait for page to be reasonably loaded."""

        try:

            await page.wait_for_load_state("networkidle", timeout=timeout)

        except Exception:

            await asyncio.sleep(0.75)



    async def _wait_for_listings(self, page: Page) -> None:

        """Wait for first listing link to appear after search."""

        try:

            await page.wait_for_selector(

                LISTING_XPATH, state="attached", timeout=20_000,

            )

        except Exception:

            # Results might take longer on slow connections

            await asyncio.sleep(1.5)



    async def _wait_for_detail_panel(self, page: Page) -> None:

        """Wait for the detail panel to load after clicking a listing."""

        try:

            # Wait for the address or phone button — indicates detail loaded

            await page.wait_for_selector(

                '//button[@data-item-id="address"], '

                '//button[contains(@data-item-id, "phone:tel:")]',

                state="attached", timeout=8_000,

            )

        except Exception:

            # Fallback: short sleep if detail panel takes a different form

            await asyncio.sleep(1.0)



    async def _dismiss_consent_banner(self, page: Page) -> None:

        """Dismiss Google's GDPR / consent banner if present."""

        consent_selectors = [

            # Google consent dialog buttons

            '//button[contains(., "Accept all")]',

            '//button[contains(., "Alle akzeptieren")]',

            '//button[contains(., "Reject all")]',

            '//button[contains(., "Alle ablehnen")]',

            'button[aria-label="Accept all"]',

            'button[aria-label="Alle akzeptieren"]',

            # Generic consent form

            'form[action*="consent"] button',

        ]

        for sel in consent_selectors:

            try:

                btn = page.locator(sel).first

                if await btn.is_visible(timeout=3_000):

                    await btn.click()

                    await asyncio.sleep(1.0)

                    logger.info(f"[{self.job_id}] Dismissed consent banner")

                    return

            except Exception:

                continue



    async def _is_end_of_list(self, page: Page) -> bool:

        """Check if Google Maps shows an 'end of results' indicator."""

        try:

            body_text = (await page.inner_text("body")).lower()

            return any(sig in body_text for sig in END_OF_LIST_SIGNALS)

        except Exception:

            return False



    async def _extract_text_with_fallbacks(

        self, page: Page, selectors: list[str],

    ) -> Optional[str]:

        """Try multiple selectors and return the first non-empty text found."""

        for sel in selectors:

            try:

                loc = page.locator(sel).first

                if await loc.count() > 0:

                    text = (await loc.inner_text()).strip()

                    if text:

                        return text

            except Exception:

                continue

        return None



    async def _handle_captcha(self, page: Page) -> None:
        """Detect and handle CAPTCHAs via Headed-on-Demand solver."""
        if self._captcha_lock.locked() and not page.is_closed():
             # If someone else is solving it, wait for browser to sync cookies
             await asyncio.sleep(2.0)

        try:
            body_text = (await page.inner_text("body", timeout=1000)).lower()
        except Exception: return

        if "google.com/sorry" not in page.url and "consent.google.com" not in page.url:
            return

        logger.warning(f"[{self.job_id}] CAPTCHA detected — requesting Headed-on-Demand solver...")
        
        # Subscribe to completion signal
        event_bus.subscribe(event_bus.SOLVER_COMPLETED, self._on_solver_completed)
        
        # Clear interaction queue
        while not self._interaction_queue.empty():
            try: self._interaction_queue.get_nowait()
            except asyncio.QueueEmpty: break

        try:
            # 1. Capture current session state
            cookies = await page.context.cookies()
            
            # 2. Emit solver request
            event_bus.emit(
                event_bus.SOLVER_REQUESTED, 
                job_id=self.job_id, 
                url=page.url, 
                cookies=cookies
            )
            
            # 3. Wait for solver completion (10 minute limit)
            try:
                msg = await asyncio.wait_for(self._interaction_queue.get(), timeout=600.0)
                if msg.get("type") == "solver_complete":
                    new_cookies = msg.get("cookies", [])
                    if new_cookies:
                        await page.context.add_cookies(new_cookies)
                    
                    logger.info(f"[{self.job_id}] Maps solver bridge successful, reloading and resuming...")
                    try:
                        await page.reload(timeout=10000)
                    except: pass
                    
                    await asyncio.sleep(2.0) # Settle time
                    return
            except asyncio.TimeoutError:
                logger.warning(f"[{self.job_id}] Headed solver timed out after 10m")
        except Exception as e:
            logger.error(f"[{self.job_id}] Headed solver bridge error: {e}")
        finally:
            event_bus.unsubscribe(event_bus.SOLVER_COMPLETED, self._on_solver_completed)
        return

    async def _capture_search_response(self, response: Any) -> None:

        try:

            payload = await response.text()

            self._ingest_search_payload(payload)

        except Exception:

            pass



    def _ingest_search_payload(self, payload: str) -> None:

        if not payload or len(payload) < 10:

            return

        try:

            outer = json.loads(payload.replace('/*""*/', ''))

            inner = outer.get("d")

            if not isinstance(inner, str) or len(inner) < 6:

                return

            parsed = json.loads(inner[5:])

            feed = parsed[64]

        except Exception:

            return



        if not isinstance(feed, list):

            return



        added = 0

        for item in feed:

            candidate = self._parse_feed_item(item)

            if not candidate:

                continue

            place_id = candidate.get("place_id") or candidate.get("dedupe_key")

            if not place_id or place_id in self._feed_candidate_ids:

                continue

            self._feed_candidate_ids.add(place_id)

            self._feed_candidates.append(candidate)

            added += 1



        if added:

            logger.info(f"[{self.job_id}] Search feed captured {added} new Maps candidates")



    def _parse_feed_item(self, item: Any) -> Optional[dict[str, Any]]:

        try:

            entry = item[item.__len__() - 1]

            name = entry[11] or ""

            if not name:

                return None



            website = ""

            phone = ""

            review_count = None

            rating = None

            category = ""

            place_id = ""

            cid = ""

            address_parts = []

            latitude = None

            longitude = None



            try:

                website = entry[7][0] or ""

            except Exception:

                pass

            try:

                phone = entry[178][0][0] or ""

            except Exception:

                pass

            try:

                review_count = entry[4][8]

            except Exception:

                pass

            try:

                rating = entry[4][7]

            except Exception:

                pass

            try:

                category = "; ".join(entry[13])

            except Exception:

                pass

            try:

                place_id = entry[78] or ""

            except Exception:

                pass

            try:

                cid = entry[37][0][0][29][1] or ""

            except Exception:

                pass

            try:

                address_parts = entry[2] or []

            except Exception:

                pass

            try:

                latitude = entry[9][2]

                longitude = entry[9][3]

            except Exception:

                pass



            address = ", ".join([part for part in address_parts if part])

            dedupe_key = place_id or cid or f"{name}|{address}"

            return {

                "dedupe_key": str(dedupe_key),

                "place_id": str(place_id) if place_id else "",

                "cid": str(cid) if cid else "",

                "name": str(name).strip(),

                "website": str(website).strip(),

                "phone": str(phone).strip(),

                "address": address.strip(),

                "category": str(category).strip(),

                "review_count": review_count,

                "rating": rating,

                "latitude": latitude,

                "longitude": longitude,

            }

        except Exception:

            return None



    def _install_search_feed_listener(self, page: Page) -> None:
        """Hook into the search feed responses to capture business data JSON."""
        page.on("response", self._capture_search_response)

    def _build_records_from_feed(self, query: str) -> list[LeadRecord]:

        records: list[LeadRecord] = []

        for candidate in self._feed_candidates[: self.config.max_results]:

            record = self._record_from_feed_candidate(candidate, query)

            if record:

                records.append(record)

        return records



    def _record_from_feed_candidate(

        self, candidate: dict[str, Any], query: str,

    ) -> Optional[LeadRecord]:

        name = (candidate.get("name") or "").strip()

        if not name:

            return None



        record = LeadRecord(

            source_type=SourceType.GOOGLE_MAPS,

            search_query=query,

            company_name=name,

            category=(candidate.get("category") or None),

            address=(candidate.get("address") or None),

            country=self.config.country,

        )



        website = (candidate.get("website") or "").strip()

        if website:

            record.website = normalize_website(website)



        phone = (candidate.get("phone") or "").strip()

        if phone:

            record.phone = normalize_phone(phone)



        try:

            if candidate.get("review_count") not in (None, ""):

                record.review_count = int(str(candidate["review_count"]).replace(",", "").replace(".", ""))

        except Exception:

            pass



        try:

            if candidate.get("rating") not in (None, ""):

                record.rating = float(str(candidate["rating"]).replace(",", "."))

        except Exception:

            pass



        try:

            if candidate.get("latitude") not in (None, ""):

                record.latitude = float(candidate["latitude"])

            if candidate.get("longitude") not in (None, ""):

                record.longitude = float(candidate["longitude"])

        except Exception:

            pass



        place_id = (candidate.get("place_id") or "").strip()

        if place_id:

            record.maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"

            record.source_url = record.maps_url

        elif record.latitude is not None and record.longitude is not None:

            record.maps_url = f"https://www.google.com/maps/@{record.latitude},{record.longitude},17z"

            record.source_url = record.maps_url



        if record.address:

            self._parse_address(record)



        return record

    def _build_query(self) -> str:

        return " ".join(filter(None, [

            self.config.job_title,

            self.config.city or self.config.region,

            self.config.country,

        ]))



    def _parse_address(self, record: LeadRecord) -> None:

        """Parse structured address fields from raw address text."""

        addr = record.address

        if not addr:

            return



        # German postal code (5 digits)

        m = re.search(r"\b(\d{5})\b", addr)

        if m:

            record.postal_code = m.group(1)



        # City name after postal code

        m2 = re.search(r"\d{5}\s+([A-ZÄÖÜa-zäöüß][^\n,]{2,})", addr)

        if m2 and not record.city:

            record.city = m2.group(1).strip()



        # Region / state: try to extract from comma-separated parts

        # Format: "Street 123, 12345 City, State" or "Street 123, City, State"

        parts = [p.strip() for p in addr.split(",")]

        if len(parts) >= 3:

            # Last part is often the country/state

            last = parts[-1].strip()

            if last and not last.isdigit() and last.lower() != record.city.lower() if record.city else True:

                record.region = last

        elif len(parts) == 2 and not record.city:

            # "Street, City" format

            candidate = parts[-1].strip()

            # Extract city after removing postal code

            city_m = re.sub(r"\d{5}\s*", "", candidate).strip()

            if city_m:

                record.city = city_m

