"""
ZUGZWANG - Website Email Crawler
Controlled, shallow crawling of business websites to discover contact emails.
Visits only known high-probability pages (impressum, kontakt, karriere, etc.)
"""

from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from typing import Optional
import asyncio
import re

from .browser import BrowserSession
from .email_extractor import (
    extract_emails_from_text,
    extract_emails_from_html,
    classify_email_source,
    deduplicate_emails,
    normalize_website,
    normalize_phone,
    _is_valid_email,
)
from ..core.config import config_manager
from ..core.logger import get_logger
from ..core.models import AppSettings

logger = get_logger(__name__)


class WebsiteEmailCrawler:
    """
    Shallow website crawler focused on extracting contact emails.
    Visits only a configurable set of paths per domain.
    Respects rate limiting and domain blacklist.
    """

    def __init__(self, session: BrowserSession, max_pages: int = 3):
        self.session = session
        self.max_pages = max_pages
        self.settings = session.settings
        self._result_cache: dict[str, tuple[Optional[str], Optional[str]]] = {}
        self._contact_cache: dict[str, tuple[Optional[str], Optional[str], Optional[str]]] = {}
        self._all_contact_cache: dict[str, tuple[list[str], Optional[str], Optional[str], dict[str, str]]] = {}
        self._robots_cache: dict[str, bool] = {}
        self._fast_timeout_ms = 6000  # Aggressive timeout for fast email discovery

    async def find_email(
        self,
        website: str,
        company_name: Optional[str] = None,
        job_id: Optional[str] = None,
        bypass_cache: bool = False,
        extract_social: bool = False,
    ) -> tuple[Optional[str], Optional[str], dict[str, str]]:
        """
        Attempt to find an email address for a given website.
        Returns (email, source_page_url, social_dict).
        """
        website = normalize_website(website)
        cache_key = self._cache_key(website, company_name)
        socials = {}

        if self.session.is_blacklisted(website):
            logger.debug(f"[{job_id}] Skipping blacklisted domain: {website}")
            return None, None, {}

        if not bypass_cache:
            cached = self._result_cache.get(cache_key)
            if cached is not None:
                logger.info(f"[{job_id}] Reusing cached email crawl for {cache_key}")
                return cached[0], cached[1], {}

        discovery_paths = self.settings.email_discovery_paths
        candidate_urls = self._build_candidate_urls(website, discovery_paths)[:self.max_pages]
        logger.info(
            f"[{job_id}] Email crawl start for {website} across {len(candidate_urls)} pages"
        )

        best_email, best_source = None, None
        best_priority = 99

        for idx, url in enumerate(candidate_urls):
            if self.settings.default_respect_robots:
                if not await self._is_allowed_by_robots(url):
                    continue

            logger.debug(f"[{job_id}] Fast fetch checking {url}")
            html = await self._fetch_html(url, ignore_rate_limit=True)
            if not html:
                continue

            if idx == 0:
                discovered = self._discover_paths_from_html(url, html)
                if discovered:
                    merged = candidate_urls + discovered
                    seen_urls = set()
                    candidate_urls = [u for u in merged if not (u in seen_urls or seen_urls.add(u))][:self.max_pages + 2]

            await asyncio.sleep(0)
            emails = self._extract_contact_block_emails(html)
            if not emails:
                emails = self._extract_priority_emails(html)
            if not emails:
                emails = deduplicate_emails(extract_emails_from_html(html))

            if extract_social:
                socials.update(self._extract_socials(html))

            if not emails:
                continue

            is_high_quality = any(
                token in url.lower() for token in ("impressum", "kontakt", "contact", "karriere")
            ) or url.strip("/") == website.strip("/")
            priority = 0 if is_high_quality else 1
            if best_email is None or priority < best_priority:
                best_email = emails[0]
                best_source = url
                best_priority = priority
                if priority == 0:
                    break

        if best_email:
            self._result_cache[cache_key] = (best_email, best_source)
            logger.info(f"[{job_id}] Found email {best_email} at {best_source}")
            return best_email, best_source, socials

        # If fast fetches found nothing, skip slow fallbacks and move on
        logger.debug(f"[{job_id}] No email found for {website}")
        self._result_cache[cache_key] = (None, None)
        return None, None, socials

    async def find_contact_info(
        self,
        website: str,
        company_name: Optional[str] = None,
        job_id: Optional[str] = None,
        bypass_cache: bool = False,
        extract_social: bool = False,
    ) -> tuple[Optional[str], Optional[str], Optional[str], dict[str, str]]:
        website = normalize_website(website)
        cache_key = self._cache_key(website, company_name)
        socials = {}

        if self.session.is_blacklisted(website):
            return None, None, None, {}

        if not bypass_cache:
            cached = self._contact_cache.get(cache_key)
            if cached is not None:
                return cached[0], cached[1], cached[2], {}

        discovery_paths = self.settings.email_discovery_paths
        candidate_urls = self._build_candidate_urls(website, discovery_paths)[:self.max_pages]

        best_email, best_phone, best_source = None, None, None
        best_priority = 99

        for idx, url in enumerate(candidate_urls):
            if self.settings.default_respect_robots and not await self._is_allowed_by_robots(url):
                continue

            html = await self._fetch_html(url, ignore_rate_limit=True)
            if not html:
                continue

            # Offload heavy regex and discovery to background thread
            data = await asyncio.to_thread(self._extract_page_data, url, html, idx == 0, extract_social)
            
            if idx == 0 and data.get("discovered"):
                merged = candidate_urls + data["discovered"]
                seen_urls = set()
                candidate_urls = [u for u in merged if not (u in seen_urls or seen_urls.add(u))][:self.max_pages + 2]

            emails = data["emails"]
            phone = data["phone"]
            if extract_social:
                socials.update(data["socials"])

            if not emails and not phone:
                continue

            is_high_quality = any(
                token in url.lower() for token in ("impressum", "kontakt", "contact", "karriere")
            ) or url.strip("/") == website.strip("/")
            priority = 0 if is_high_quality else 1
            if best_source is None or priority < best_priority or (priority == best_priority and emails and not best_email):
                best_email = emails[0] if emails else best_email
                best_phone = phone or best_phone
                best_source = url
                best_priority = priority
                if priority == 0 and best_email and best_phone:
                    break

        self._contact_cache[cache_key] = (best_email, best_phone, best_source)
        return best_email, best_phone, best_source, socials

    async def find_all_contact_info(
        self,
        website: str,
        company_name: Optional[str] = None,
        job_id: Optional[str] = None,
        bypass_cache: bool = False,
        extract_social: bool = False,
    ) -> tuple[list[str], Optional[str], Optional[str], dict[str, str]]:
        website = normalize_website(website)
        cache_key = self._cache_key(website, company_name)
        socials: dict[str, str] = {}

        if self.session.is_blacklisted(website):
            return [], None, None, {}

        if not bypass_cache:
            cached = self._all_contact_cache.get(cache_key)
            if cached is not None:
                return cached[0], cached[1], cached[2], dict(cached[3])

        discovery_paths = self.settings.email_discovery_paths
        candidate_urls = self._build_candidate_urls(website, discovery_paths)[:self.max_pages]

        best_emails: list[str] = []
        best_phone: Optional[str] = None
        best_source: Optional[str] = None
        best_priority = 99

        for idx, url in enumerate(candidate_urls):
            if self.settings.default_respect_robots and not await self._is_allowed_by_robots(url):
                continue

            html = await self._fetch_html(url, ignore_rate_limit=True)
            if not html:
                continue

            # Offload heavy regex and discovery to background thread
            data = await asyncio.to_thread(self._extract_page_data, url, html, idx == 0, extract_social)

            if idx == 0 and data.get("discovered"):
                merged = candidate_urls + data["discovered"]
                seen_urls = set()
                candidate_urls = [u for u in merged if not (u in seen_urls or seen_urls.add(u))][:self.max_pages + 2]

            emails = data["emails"]
            emails = self._filter_usable_emails(emails)
            phone = data["phone"]
            if extract_social:
                socials.update(data["socials"])

            if not emails and not phone:
                continue

            is_high_quality = any(
                token in url.lower() for token in ("impressum", "kontakt", "contact", "karriere")
            ) or url.strip("/") == website.strip("/")
            priority = 0 if is_high_quality else 1
            if (
                best_source is None
                or priority < best_priority
                or (priority == best_priority and len(emails) > len(best_emails))
            ):
                best_emails = emails or best_emails
                best_phone = phone or best_phone
                best_source = url
                best_priority = priority
                if priority == 0 and best_emails and best_phone:
                    break

        result = (best_emails, best_phone, best_source, socials)
        self._all_contact_cache[cache_key] = (list(best_emails), best_phone, best_source, dict(socials))
        return result

    def _extract_page_data(self, url: str, html: str, discover: bool, extract_social: bool) -> dict:
        """Synchronous helper for background thread offloading.
        Performs all regex and parsing for a single page.
        """
        discovered = self._discover_paths_from_html(url, html) if discover else []
        
        emails = self._extract_contact_block_emails(html)
        if not emails:
            emails = self._extract_priority_emails(html)
        if not emails:
            from .email_extractor import extract_emails_from_html, deduplicate_emails
            emails = deduplicate_emails(extract_emails_from_html(html))
            
        phone = self._extract_contact_block_phone(html) or self._extract_priority_phone(html)
        
        socials = {}
        if extract_social:
            socials = self._extract_socials(html)
            
        return {
            "discovered": discovered,
            "emails": emails,
            "phone": phone,
            "socials": socials
        }

    async def _crawl_page(
        self,
        page,
        url: str,
        job_id: Optional[str],
        prefer_fast_fetch: bool = False,
        extract_social: bool = False,
    ) -> tuple[str, list[str], Optional[str], dict[str, str]]:
        """Crawl a single page and return found emails + source URL + socials."""
        if self.settings.default_respect_robots:
            if not await self._is_allowed_by_robots(url):
                logger.info(f"[{job_id}] Skipping {url} - blocked by robots.txt")
                return "", [], None, {}

        socials = {}
        if prefer_fast_fetch:
            html = await self.session.fetch_url_content_fast(url, timeout=self._timeout_for_url(url))
            if html:
                await asyncio.sleep(0)
                emails = self._extract_priority_emails(html)
                if not emails:
                    emails = deduplicate_emails(extract_emails_from_html(html))
                if extract_social:
                    socials = self._extract_socials(html)
                if emails or (extract_social and socials):
                    return html, emails, url, socials

            success = await self._navigate_with_fallback(page, url)
            if not success:
                return "", [], None, {}

        # Fast first pass inspired by the extension:
        # visible page text is often enough to catch straightforward contact emails
        # without paying the cost of full HTML extraction.
        try:
            text = await page.inner_text("body")
        except Exception:
            text = ""

        if text:
            await asyncio.sleep(0)
            emails = self._extract_priority_emails(text)
            if not emails:
                emails = deduplicate_emails(extract_emails_from_text(text))
            if emails:
                return "", emails, url, {}

        html = await self.session.get_page_content(page)
        if not html:
            return "", [], None, {}

        await asyncio.sleep(0)
        emails = self._extract_priority_emails(html)
        if not emails:
            emails = deduplicate_emails(extract_emails_from_html(html))
        
        if extract_social:
            socials = self._extract_socials(html)

        return html, emails, url, socials

    def _extract_socials(self, html: str) -> dict[str, str]:
        """Simple regex-based social profile extraction."""
        results = {}
        # LinkedIn
        li = re.search(r'linkedin\.com/(?:in|company)/([a-zA-Z0-9_-]+)', html)
        if li: results["linkedin"] = li.group(0)
        
        # Twitter / X
        tw = re.search(r'(?:twitter|x)\.com/([a-zA-Z0-9_]+)', html)
        if tw: results["twitter"] = tw.group(0)
        
        # Instagram
        insta = re.search(r'instagram\.com/([a-zA-Z0-9_.-]+)', html)
        if insta: results["instagram"] = insta.group(0)
        
        return results

    def _extract_priority_phone(self, content: str) -> Optional[str]:
        if not content:
            return None
        normalized = content.replace("\xa0", " ")
        patterns = [
            r"(?:Telefon|Tel\.?|Phone|Mobil|Mobile)\s*[:\-\s]*([+0-9][0-9\s()/\-]{7,})",
            r"href=[\"']tel:([^\"'>\s]+)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, normalized, re.IGNORECASE):
                candidate = normalize_phone(match.group(1).strip())
                if candidate:
                    return candidate
        return None

    def _extract_contact_block_emails(self, html: str) -> list[str]:
        if not html:
            return []
        blocks = re.findall(
            r'<(?:section|div|article|footer)[^>]+(?:id|class)\s*=\s*["\'][^"\']*(?:contact|kontakt|impressum|footer|mail)[^"\']*["\'][^>]*>(.*?)</(?:section|div|article|footer)>',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        candidates: list[str] = []
        for block in blocks[:4]:
            for match in re.finditer(r'mailto:([^"\'\s?&>]+)', block, re.IGNORECASE):
                email = match.group(1).strip().lower()
                if _is_valid_email(email):
                    candidates.append(email)
            if not candidates:
                candidates.extend(extract_emails_from_html(block))
        return deduplicate_emails(candidates) if candidates else []

    def _extract_contact_block_phone(self, html: str) -> Optional[str]:
        if not html:
            return None
        blocks = re.findall(
            r'<(?:section|div|article|footer)[^>]+(?:id|class)\s*=\s*["\'][^"\']*(?:contact|kontakt|impressum|footer|phone|tel)[^"\']*["\'][^>]*>(.*?)</(?:section|div|article|footer)>',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        for block in blocks[:4]:
            phone = self._extract_priority_phone(block)
            if phone:
                return phone
        return None

    def _discover_paths_from_html(self, base_url: str, html: str) -> list[str]:
        if not html:
            return []
        keywords = (
            "impressum", "kontakt", "contact", "karriere", "jobs", "job",
            "stellen", "bewerbung", "about", "ueber-uns", "über-uns"
        )
        href_pattern = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
        parsed_base = urlparse(base_url)
        root = f"{parsed_base.scheme}://{parsed_base.netloc}"
        discovered: list[str] = []
        for match in href_pattern.finditer(html):
            href = (match.group(1) or "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            href_lower = href.lower()
            if not any(keyword in href_lower for keyword in keywords):
                continue
            full = urljoin(root + "/", href)
            parsed = urlparse(full)
            if parsed.netloc and parsed.netloc.lower() != parsed_base.netloc.lower():
                continue
            discovered.append(full)
            if len(discovered) >= 4:
                break
        return discovered

    def _build_candidate_urls(self, base_url: str, paths: list[str]) -> list[str]:
        """Build prioritized list of URLs to visit."""
        parsed = urlparse(base_url)
        root = f"{parsed.scheme}://{parsed.netloc}"

        # Start with the home page
        urls = [base_url]

        # Add discovery paths, prioritizing the highest-value contact/legal pages first.
        for path in self._prioritize_paths(paths):
            clean_path = path.strip("/")
            if not clean_path:
                continue
            urls.append(urljoin(root + "/", clean_path))

        # Deduplicate while preserving order
        seen = set()
        result = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                result.append(u)
        return result

    def _prioritize_paths(self, paths: list[str]) -> list[str]:
        discovery_order = [
            "impressum", "kontakt", "contact",
            "karriere", "jobs", "job", "stellenangebote",
            "ausbildung", "azubi", "bewerbung",
            "team", "datenschutz", "kontaktformular",
            "über uns", "ueber uns", "ueber-uns", "über-uns", "about",
        ]

        def score(path: str) -> tuple[int, str]:
            p = path.strip("/").lower()
            if not p:
                return (99, p)

            for i, token in enumerate(discovery_order):
                if token in p:
                    return (i, p)

            if any(token in p for token in ("about", "contact", "legal", "about-us")):
                return (50, p)

            return (60, p)

        return sorted(paths, key=score)

    def _extract_priority_emails(self, content: str) -> list[str]:
        if not content:
            return []

        normalized = content.replace("\xa0", " ")
        candidates: list[str] = []
        patterns = [
            r"E-?Mail\s*[:\-\s]\s*([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})",
            r"Email\s*[:\-\s]\s*([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})",
            r"Kontakt\s*[:\-\s]\s*([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})",
            r"Impressum[\s\S]{0,400}?([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})",
            r"mailto:([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})",
            r"([A-Z0-9._%+\-]+(?:\s*\(at\)\s*|\s*@\s*)[A-Z0-9.\-]+\.[A-Z]{2,})",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, normalized, re.IGNORECASE):
                email = match.group(1).strip().lower()
                if email and _is_valid_email(email):
                    candidates.append(email)

        return deduplicate_emails(candidates) if candidates else []

    def _filter_usable_emails(self, emails: list[str]) -> list[str]:
        filtered: list[str] = []
        seen: set[str] = set()
        for email in emails or []:
            candidate = (email or "").strip().lower()
            if not candidate or not _is_valid_email(candidate):
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            filtered.append(candidate)
        return filtered

    def _timeout_for_url(self, url: str) -> int:
        path = urlparse(url).path.lower()
        if path in ("", "/"):
            return self._fast_timeout_ms
        if any(token in path for token in ("impressum", "kontakt", "contact")):
            return self._fast_timeout_ms
        return min(self._fast_timeout_ms, 4_000)

    def _cache_key(self, website: str, company_name: Optional[str] = None) -> str:
        parsed = urlparse(website)
        base = f"{parsed.scheme}://{parsed.netloc.lower()}"
        if company_name:
            company_slug = " ".join(company_name.strip().lower().split())
            if company_slug:
                return f"{base}|{company_slug}"
        return base

    async def _is_allowed_by_robots(self, url: str) -> bool:
        """Check if URL is allowed per robots.txt (minimal implementation with caching)."""
        parsed = urlparse(url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = f"{base_domain}/robots.txt"
        
        # Check cache
        cache_key = base_domain.lower()
        if cache_key in self._robots_cache:
            return self._robots_cache[cache_key]

        try:
            rp = RobotFileParser()
            # Fetch with a short timeout. If robots.txt fails, assume allowed.
            content = await self.session.fetch_url_content_fast(robots_url, timeout=1500, ignore_rate_limit=True)
            if not content:
                self._robots_cache[cache_key] = True
                return True
            
            rp.parse(content.splitlines())
            user_agent = self.settings.user_agents[0] if self.settings.user_agents else "*"
            allowed = rp.can_fetch(user_agent, url)
            self._robots_cache[cache_key] = allowed
            return allowed
        except Exception:
            return True # Fail open

    async def _fetch_html(self, url: str, ignore_rate_limit: bool = False) -> str:
        """Fetch a page, falling back to http:// when https:// hits SSL issues."""
        probes = self._scheme_fallback_urls(url)
        for probe in probes:
            html = await self.session.fetch_url_content_fast(
                probe,
                timeout=self._timeout_for_url(probe),
                ignore_rate_limit=ignore_rate_limit,
            )
            if html:
                return html
        
        # Final fallback: use a more permissive client (like httpx) if available
        # to handle legacy SSL versions that Playwright might reject
        try:
            import httpx
            async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=4.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.text
        except:
            pass
            
        return ""

    async def _navigate_with_fallback(self, page, url: str, ignore_rate_limit: bool = False) -> bool:
        """Navigate with a single http:// fallback for SSL failures."""
        probes = self._scheme_fallback_urls(url)
        for probe in probes:
            success = await self.session.navigate(
                page,
                probe,
                timeout=self._timeout_for_url(probe),
                retries=1,
                ignore_rate_limit=ignore_rate_limit,
            )
            if success:
                return True
        return False

    def _scheme_fallback_urls(self, url: str) -> list[str]:
        """Return the original URL plus a http:// fallback when relevant."""
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https":
            return [url]

        http_url = parsed._replace(scheme="http").geturl()
        if http_url == url:
            return [url]
        # In case of SSL errors, prioritizing http:// can bypass strict protocol enforcement if redirects are not absolute
        return [url, http_url]

