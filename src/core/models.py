"""
ZUGZWANG - Core Data Models
Normalized schema for all scraped lead records.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import hashlib
import re
from typing import Optional
from urllib.parse import urlparse
import uuid


class SourceType(str, Enum):
    GOOGLE_MAPS = "google_maps"
    JOBSUCHE = "jobsuche"
    AUSBILDUNG_DE = "ausbildung_de"
    AUBIPLUS_DE = "aubiplus_de"
    AZUBIYO = "azubiyo"
    MANUAL = "manual"


class ScrapingStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EmailSource(str, Enum):
    MAPS_LISTING = "maps_listing"
    JOB_LISTING = "job_listing"
    IMPRESSUM = "impressum"
    KONTAKT = "kontakt"
    KARRIERE = "karriere"
    JOBS_PAGE = "jobs_page"
    ABOUT_PAGE = "about_page"
    CONTACT_PAGE = "contact_page"
    DATENSCHUTZ = "datenschutz"
    LEGAL = "legal"
    FOOTER = "footer"
    OTHER = "other"


@dataclass
class LeadRecord:
    """Normalized lead record - the primary data unit of the application."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_type: SourceType = SourceType.GOOGLE_MAPS
    source_url: Optional[str] = None
    search_query: Optional[str] = None

    # Company info
    company_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None

    # Job info (Jobsuche)
    job_title: Optional[str] = None
    publication_date: Optional[str] = None

    # Contact
    website: Optional[str] = None
    email: Optional[str] = None
    email_source_page: Optional[str] = None
    email_source_type: Optional[EmailSource] = None
    phone: Optional[str] = None
    contact_person: Optional[str] = None
    
    # Social 
    linkedin: Optional[str] = None
    twitter: Optional[str] = None
    instagram: Optional[str] = None

    # Location
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None

    # Google Maps specific
    rating: Optional[float] = None
    review_count: Optional[int] = None
    maps_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Meta
    notes: Optional[str] = None
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    is_duplicate: bool = False

    def normalize(self) -> "LeadRecord":
        """Clean and standardize all fields in the record. Call before yielding/saving."""
        # 1. Company Name - Strip "Arbeitgeber:" and generic prefixes
        if self.company_name:
            lines = [line.strip() for line in str(self.company_name).splitlines() if line.strip()]
            if lines and re.fullmatch(r"(?i)arbeitgeber\s*[:\-]?", lines[0]):
                lines = lines[1:]
            if lines:
                self.company_name = " ".join(lines).strip()

            # Handle "Arbeitgeber:" on same line or separated by colon/dash
            self.company_name = re.sub(r'(?i)arbeitgeber\s*[:\-]?\s*', '', self.company_name).strip()
            # Remove trailing ellipses
            self.company_name = re.sub(r'\.{3}$', '', self.company_name).strip()
            # Generic cleanup
            self.company_name = self.company_name.strip()

        # 2. Location (City/Zip) - Extract from address if city is generic or missing
        # We also want to capitalize city names nicely
        if self.address:
            # Try to find "12345 City" pattern
            plz_match = re.search(r"\b(\d{5})\b", self.address)
            if plz_match and not self.postal_code:
                self.postal_code = plz_match.group(1)
            
            city_match = re.search(r"\d{5}\s+([A-ZÄÖÜa-zäöüß][^\n,]{2,})", self.address)
            if city_match and (not self.city or self.city.lower() in ["", "ort", "standort"]):
                self.city = city_match.group(1).strip()
            elif not self.city or self.city.lower() in ["", "ort", "standort"]:
                 # Fallback: Street, City
                 if "," in self.address:
                     self.city = self.address.split(",")[-1].strip()

        if self.city:
            self.city = self.city.strip()
            if self.city.lower() in ["", "ort", "standort", "location", "arbeitsort", "arbeitsplatz"]:
                self.city = None
            else:
                # If city was extracted from search query (config), sometimes it's like "berlin"
                if self.city.islower():
                    self.city = self.city.title()

        # 3. Phone - Standard formatting
        if self.phone:
            cleaned = self.phone.strip()
            cleaned = cleaned.replace("\xa0", " ")
            # German international prefix: 0049 -> +49
            cleaned = re.sub(r"^0049\s*", "+49 ", cleaned)
            # Remove cosmetic (0) in area codes: +49 (0)89 -> +49 89
            cleaned = re.sub(r"\(0\)\s*", "", cleaned)
            # Strip everything except digits, +, parentheses, slash, dash, space
            cleaned = re.sub(r"[^\d+\(\)\-/\s]", "", cleaned)
            cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
            digits = re.sub(r"\D", "", cleaned)
            def _looks_suspicious(national: str) -> bool:
                return (
                    not national
                    or len(national) < 9
                    or len(national) > 12
                    or national.startswith("00")
                    or re.fullmatch(r"0+\d+", national) is not None
                )

            if len(digits) < 10 or re.fullmatch(r"\d{8}", digits):
                self.phone = None
            elif cleaned.startswith("+49"):
                national = digits[2:]
                if _looks_suspicious(national):
                    self.phone = None
                else:
                    suffix = cleaned[3:].strip()
                    suffix = re.sub(r"^0+\b", "", suffix).strip()
                    suffix = re.sub(r"\s{2,}", " ", suffix)
                    self.phone = f"+49 {suffix}".strip()
            elif digits.startswith("49"):
                national = digits[2:]
                self.phone = None if _looks_suspicious(national) else f"+49 {national}"
            elif digits.startswith("0") and len(digits) >= 10:
                national = digits[1:]
                if _looks_suspicious(national):
                    self.phone = None
                else:
                    suffix = cleaned[1:].strip()
                    suffix = re.sub(r"\s{2,}", " ", suffix)
                    self.phone = f"+49 {suffix}".strip()
            else:
                self.phone = None

        # 4. Website - Ensure scheme
        if self.website:
            self.website = self.website.strip().rstrip("/")
            if self.website.lower().startswith("mailto:"):
                self.website = None
            elif self.website and not self.website.startswith(("http://", "https://")):
                self.website = "https://" + self.website

        # 5. Email - Force lower case
        if self.email:
            self.email = self.email.strip().lower()

        # 6. Job Title - Strip screen-reader artifacts
        if self.job_title:
            self.job_title = re.sub(r'(?i)^\d+\.\s*ergebnis\s*[:\-]?\s*', '', self.job_title).strip()
            if self.job_title.startswith("***"):
                self.job_title = self.job_title.lstrip("* ").strip()

        return self

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source_type"] = self.source_type.value if self.source_type else None
        d["email_source_type"] = self.email_source_type.value if self.email_source_type else None
        return d

    def has_email(self) -> bool:
        return bool(self.email)

    def has_website(self) -> bool:
        return bool(self.website)

    def display_name(self) -> str:
        return self.company_name or self.job_title or "Unknown"

    def dedupe_key(self) -> str:
        primary_url = self.maps_url or self.source_url or self.website or ""
        parsed = urlparse(str(primary_url).strip()) if primary_url else None
        normalized_url = ""
        if parsed:
            normalized_url = f"{parsed.netloc.lower()}{parsed.path.rstrip('/').lower()}"

        parts = [
            self.source_type.value if self.source_type else "",
            normalized_url,
            self._normalize_key_part(self.company_name),
            self._normalize_key_part(self.job_title),
            self._normalize_key_part(self.email),
            self._normalize_key_part(self.phone),
            self._normalize_key_part(self.contact_person),
            self._normalize_key_part(self.address),
            self._normalize_key_part(self.city),
        ]
        return "|".join(parts)

    def stable_id(self) -> str:
        return hashlib.sha1(self.dedupe_key().encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_key_part(value: Optional[str]) -> str:
        if value is None:
            return ""
        return " ".join(str(value).strip().lower().split())

    @classmethod
    def from_dict(cls, d: dict) -> "LeadRecord":
        d = d.copy()
        if "source_type" in d and d["source_type"]:
            d["source_type"] = SourceType(d["source_type"])
        if "email_source_type" in d and d["email_source_type"]:
            d["email_source_type"] = EmailSource(d["email_source_type"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class SearchConfig:
    """Configuration for a single scraping job."""

    job_title: str = ""
    country: str = "Germany"
    city: str = ""
    region: str = ""
    source_type: SourceType = SourceType.GOOGLE_MAPS
    max_results: int = 100
    scrape_emails: bool = True
    offer_type: str = "Arbeit"  # Jobsuche mode: Arbeit, Ausbildung, etc.
    latest_offers_only: bool = False  # Jobsuche mode
    headless: bool = True
    delay_min: float = 1.5
    delay_max: float = 4.0
    request_timeout: int = 30
    max_email_crawl_depth: int = 3
    respect_robots: bool = True
    bypass_cache: bool = False
    extract_social_profiles: bool = False
    proxy: Optional[str] = None


@dataclass
class ScrapingJob:
    """Represents a single scraping task with full lifecycle tracking."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config: SearchConfig = field(default_factory=SearchConfig)
    status: ScrapingStatus = ScrapingStatus.PENDING
    results: list = field(default_factory=list)

    total_found: int = 0
    total_emails: int = 0
    total_websites: int = 0
    total_errors: int = 0

    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    error_message: Optional[str] = None
    log_entries: list = field(default_factory=list)

    def start(self):
        self.status = ScrapingStatus.RUNNING
        self.started_at = datetime.utcnow().isoformat()

    def complete(self):
        self.status = ScrapingStatus.COMPLETED
        self.completed_at = datetime.utcnow().isoformat()
        self._update_stats()

    def fail(self, error: str):
        self.status = ScrapingStatus.FAILED
        self.error_message = error
        self.completed_at = datetime.utcnow().isoformat()

    def _update_stats(self):
        self.total_found = len(self.results)
        self.total_emails = sum(1 for r in self.results if r.has_email())
        self.total_websites = sum(1 for r in self.results if r.has_website())

    @property
    def completion_rate(self) -> float:
        if self.config.max_results <= 0:
            return 0.0
        return min(1.0, len(self.results) / self.config.max_results)

    @property
    def query_label(self) -> str:
        parts = [self.config.job_title]
        if self.config.city:
            parts.append(self.config.city)
        if self.config.country:
            parts.append(self.config.country)
        return " · ".join(filter(None, parts))


@dataclass
class AppSettings:
    """Persistent application-level settings."""

    # Scraping defaults
    default_delay_min: float = 1.5
    default_delay_max: float = 4.0
    default_max_results: int = 100
    default_headless: bool = True
    default_scrape_emails: bool = True
    default_request_timeout: int = 30
    default_respect_robots: bool = True
    default_bypass_cache: bool = False
    default_extract_social_profiles: bool = False
    browser_channel: Optional[str] = "chrome"  # Default to chrome as requested

    # Email discovery keywords (editable in UI)
    email_discovery_paths: list = field(default_factory=lambda: [
        "impressum", "kontakt", "karriere", "stellenangebote", "jobs",
        "bewerbung", "über uns", "team", "datenschutz", "kontaktformular"
    ])

    # Domain filter
    blacklisted_domains: list = field(default_factory=list)
    whitelisted_domains: list = field(default_factory=list)

    # User agents
    user_agents: list = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    ])

    # Proxy
    proxies: list[str] = field(default_factory=list)
    proxy_enabled: bool = False

    # Debug
    debug_screenshots: bool = False
    log_level: str = "INFO"

    # Remember recent export/save locations
    last_xlsx_export_path: str = ""

    # Remember the latest search form values
    last_search_job_title: str = ""
    last_search_country: str = "Germany"
    last_search_city: str = ""
    last_search_source: str = "maps"
    last_search_offer_type: str = "Arbeit"
    last_search_max_results: int = 100
    last_search_delay_min: float = 1.5
    last_search_delay_max: float = 4.0
    last_search_scrape_emails: bool = True
    last_search_headless: bool = True
    last_search_latest_offers_only: bool = False
    last_search_respect_robots: bool = True
    last_search_bypass_cache: bool = False
    last_search_social_profiles: bool = False

    # UI
    theme: str = "dark"
    results_per_page: int = 50
    app_language: str = "en"
    column_visibility: str = ""       # JSON: ResultsPage column visibility
    last_seen_version: str = ""       # For "What's New" popup trigger

    email_smtp_host: str = ""
    email_smtp_port: str = "587"
    email_smtp_user: str = ""
    email_smtp_pass: str = ""
    email_from_name: str = ""
    email_reply_to: str = ""
    email_smtp_auth: bool = True
    email_smtp_ssl: bool = False
    email_smtp_tls: bool = True
    email_subject: str = ""
    email_body: str = ""
    email_body_html: bool = False
    email_interval: str = "5"
    email_recipients: str = ""

    # Security & Licensing
    security_pin: str = ""
    security_enabled: bool = False
    license_key: str = ""
    is_activated: bool = False

    # Update Sync
    git_repo_url: str = "https://github.com/whbexc/Zugzwang"
    auto_update_enabled: bool = True
    app_version: str = "1.0.4"

    # Free Trial Tracking
    trial_scraps_count: int = 0
    trial_last_reset_date: str = "" # ISO format date: YYYY-MM-DD
