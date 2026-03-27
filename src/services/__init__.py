"""ZUGZWANG - Services package."""
from .orchestrator import orchestrator, ScrapingOrchestrator
from .export_service import ExportService
from .email_extractor import (
    extract_emails_from_text,
    extract_emails_from_html,
    classify_email_source,
    normalize_phone,
    normalize_website,
    deduplicate_emails,
)

__all__ = [
    "orchestrator",
    "ScrapingOrchestrator",
    "ExportService",
    "extract_emails_from_text",
    "extract_emails_from_html",
    "classify_email_source",
    "normalize_phone",
    "normalize_website",
    "deduplicate_emails",
]
