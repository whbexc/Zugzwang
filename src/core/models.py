"""
ZUGZWANG - Core Data Models
Normalized schema for all scraped lead records.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import hashlib
from typing import Optional
from urllib.parse import urlparse
import uuid


class SourceType(str, Enum):
    GOOGLE_MAPS = "google_maps"
    JOBSUCHE = "jobsuche"
    AUSBILDUNG_DE = "ausbildung_de"
    AUBIPLUS_DE = "aubiplus_de"
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
    proxy_url: Optional[str] = None
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

    # Email Sender persistence
    email_smtp_user: str = ""
    email_smtp_pass: str = ""
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: str = "587"
    email_smtp_ssl: bool = False
    email_smtp_tls: bool = True
    email_smtp_auth: bool = True
    email_from_name: str = ""
    email_from_email: str = ""
    email_reply_to: str = ""
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
    app_version: str = "1.0.0"

    # Free Trial Tracking
    trial_scraps_count: int = 0
    trial_last_reset_date: str = "" # ISO format date: YYYY-MM-DD
