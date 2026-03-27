"""
ZUGZWANG - Website Email Crawler
Controlled, shallow crawling of business websites to discover contact emails.
Visits only known high-probability pages (impressum, kontakt, karriere, etc.)
"""

from __future__ import annotations
from typing import Optional
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import re

from .browser import BrowserSession
from .email_extractor import (
    extract_emails_from_text,
    extract_emails_from_html,
    classify_email_source,
    deduplicate_emails,
    normalize_website,
)
import re
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

    def __init__(self, session: BrowserSession, max_pages: int = 6):
        self.session = session
        self.max_pages = max_pages
        self.settings = session.settings
        self._result_cache: dict[str, tuple[Optional[str], Optional[str]]] = {}
        self._fast_timeout_ms = min(getattr(self.settings, "default_request_timeout", 30), 8) * 1000

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
        cache_key = self._cache_key(website)
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
        candidate_urls = self._build_candidate_urls(website, discovery_paths)
        logger.info(
            f"[{job_id}] Email crawl start for {website} across {min(len(candidate_urls), self.max_pages)} pages"
        )

        page = await self.session.new_page()
        try:
            for index, url in enumerate(candidate_urls[: self.max_pages]):
                logger.info(f"[{job_id}] Email crawl checking {url}")
                html, emails, source, found_socials = await self._crawl_page(
                    page,
                    url,
                    job_id,
                    prefer_fast_fetch=index > 0,
                    extract_social=extract_social,
                )
                if found_socials:
                    socials.update(found_socials)

                if emails:
                    best = emails[0]  # Already prioritized by deduplicate_emails
                    self._result_cache[cache_key] = (best, source)
                    logger.info(f"[{job_id}] Found email {best} at {source}")
                    return best, source, socials                
                # Performance Circuit Breaker: If the home page (index 0) fails to load entirely,
                # don't waste time checking sub-paths like /contact or /impressum on a dead domain.
                if index == 0 and not html and not emails:
                    logger.warning(f"[{job_id}] Domain {website} appears unreachable. Circuit breaker triggered.")
                    break
        finally:
            try:
                await page.close()
            except Exception:
                pass

        logger.debug(f"[{job_id}] No email found for {website}")
        self._result_cache[cache_key] = (None, None)
        return None, None, socials

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
                emails = deduplicate_emails(extract_emails_from_html(html))
                if extract_social:
                    socials = self._extract_socials(html)
                if emails or (extract_social and socials):
                    return html, emails, url, socials

        success = await self.session.navigate(page, url, timeout=self._timeout_for_url(url), retries=1)
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
            emails = deduplicate_emails(extract_emails_from_text(text))
            if emails:
                return "", emails, url, {}

        html = await self.session.get_page_content(page)
        if not html:
            return "", [], None, {}

        emails = extract_emails_from_html(html)
        emails = deduplicate_emails(emails)
        
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
            urls.append(urljoin(root + "/", clean_path + "/"))

        # Deduplicate while preserving order
        seen = set()
        result = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                result.append(u)
        return result

    def _prioritize_paths(self, paths: list[str]) -> list[str]:
        # User requested exact order: impressum, kontakt, karriere, stellenangebote, jobs, bewerbung, über uns, team, datenschutz, kontaktformular
        DISCOVERY_ORDER = [
            "impressum", "kontakt", "karriere", "stellenangebote", "jobs",
            "bewerbung", "über uns", "team", "datenschutz", "kontaktformular"
        ]
        
        def score(path: str) -> tuple[int, str]:
            p = path.strip("/").lower()
            if not p:
                return (99, p) # Home page handle separately in candidate_urls
                
            for i, token in enumerate(DISCOVERY_ORDER):
                if token in p:
                    return (i, p)
            
            # Secondary keywords (fallbacks for non-matching paths)
            if any(token in p for token in ("about", "contact", "legal", "about-us")):
                return (50, p)
                
            return (60, p)

        return sorted(paths, key=score)

    def _timeout_for_url(self, url: str) -> int:
        path = urlparse(url).path.lower()
        if path in ("", "/"):
            return self._fast_timeout_ms
        if any(token in path for token in ("impressum", "kontakt", "contact")):
            return self._fast_timeout_ms
        return min(self._fast_timeout_ms, 8_000)

    def _cache_key(self, website: str) -> str:
        parsed = urlparse(website)
        return f"{parsed.scheme}://{parsed.netloc.lower()}"

    async def _is_allowed_by_robots(self, url: str) -> bool:
        """Check if URL is allowed per robots.txt (minimal implementation)."""
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        # We don't want to re-fetch robots.txt constantly, but for a 
        # single job it's fine for now as it's cached by RobotFileParser?
        # Actually RobotFileParser is not async-friendly by default.
        # We'll just do a quick fetch.
        try:
            rp = RobotFileParser()
            # Since RobotFileParser.read() is blocking, and we are in async,
            # this is technically bad for the event loop, but for a scraper worker
            # which is likely in its own process/thread or just a few concurrent jobs
            # it's manageable. Better: use a faster check.
            content = await self.session.fetch_url_content_fast(robots_url, timeout=3000)
            if not content:
                return True # Assume allowed if no robots.txt
            
            rp.parse(content.splitlines())
            user_agent = self.settings.user_agents[0] if self.settings.user_agents else "*"
            return rp.can_fetch(user_agent, url)
        except Exception:
            return True # Fail open
