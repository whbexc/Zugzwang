"""
ZUGZWANG - Email Extractor Service
Pure extraction/parsing logic for finding emails in HTML content.
All functions are side-effect-free and unit-testable.
"""

from __future__ import annotations
import html as html_lib
import re
from typing import Optional
from urllib.parse import unquote, urljoin, urlparse

from ..core.models import EmailSource
from ..core.logger import get_logger

logger = get_logger(__name__)

# RFC-5321 compliant email regex (practical subset)
EMAIL_PATTERN = re.compile(
    r"(?<![a-zA-Z0-9._%+\-])"
    r"([a-zA-Z0-9._%+\-]{1,64}@[a-zA-Z0-9\-]{1,63}(?:\.[a-zA-Z0-9\-]{1,63})*\.[a-zA-Z]{2,})"
    r"(?![a-zA-Z0-9._%+\-])",
    re.IGNORECASE,
)

# Domains to exclude from email results (common false positives / platforms)
EXCLUDED_EMAIL_DOMAINS = {
    # Generic / placeholder
    "example.com", "test.com", "domain.com", "email.com",
    "yourdomain.com", "yourcompany.com", "sample.com",
    # Cloud / hosting infrastructure
    "sentry.io", "amazonaws.com", "cloudfront.net",
    "herokuapp.com", "vercel.app", "netlify.app",
    # Website builders
    "wixpress.com", "squarespace.com", "wordpress.com",
    "shopify.com", "webflow.io", "jimdo.com",
    # Social / big tech (never real contact emails)
    "google.com", "facebook.com", "twitter.com", "instagram.com",
    "linkedin.com", "youtube.com", "github.com", "apple.com",
    # Standards / spec bodies
    "w3.org", "schema.org", "iana.org",
    # Common German false-positives from CMS footers
    "typo3.org", "contao.org", "joomla.org",
}

# Emails with these local-part prefixes are typically unmonitored
NOREPLY_PREFIXES = {
    "noreply", "no-reply", "no_reply",
    "donotreply", "do-not-reply", "do_not_reply",
    "mailer-daemon", "postmaster",
}

# File extensions that are definitely not valid TLDs (false positive emails)
FALSE_POSITIVE_TLDS = {
    "png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp", "tiff",
    "css", "js", "html", "htm", "php", "asp", "jsp",
    "pdf", "doc", "docx", "xls", "xlsx", "zip", "rar",
    "woff", "woff2", "ttf", "eot", "map",
}

# Obfuscation patterns in HTML — ordered from most specific to least
OBFUSCATION_PATTERNS = [
    (r"\[at\]", "@"),
    (r"\(at\)", "@"),
    (r"\{at\}", "@"),
    (r"\[ät\]", "@"),
    (r"\[dot\]", "."),
    (r"\(dot\)", "."),
    (r"\{dot\}", "."),
    # Unicode full-width characters
    (r"\uff20", "@"),   # ＠
    (r"\uff0e", "."),   # ．
    # Spaced versions (only between word-like chars to avoid over-matching)
    (r"(?<=\w)\s+@\s+(?=\w)", "@"),
    (r"(?<=\w)\s+\.\s+(?=\w)", "."),
    # Bare " at " / " dot " (last, most aggressive)
    (r"\s+at\s+", "@"),
    (r"\s+dot\s+", "."),
]

# Pre-compiled patterns for HTML extraction
_MAILTO_PATTERN = re.compile(r'mailto:([^"\'\s?&>]+)', re.IGNORECASE)
_JSONLD_EMAIL_PATTERN = re.compile(r'"email"\s*:\s*"([^"]+)"', re.IGNORECASE)
_JSONLD_CONTACT_PATTERN = re.compile(
    r'"contactPoint"[^}]*"email"\s*:\s*"([^"]+)"', re.IGNORECASE | re.DOTALL
)
_DATA_EMAIL_PATTERN = re.compile(
    r'data-(?:email|mail|contact)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE
)
_META_EMAIL_PATTERN = re.compile(
    r'<meta[^>]+content\s*=\s*["\']([^"\']*@[^"\']*)["\'][^>]*/?>',
    re.IGNORECASE,
)
_VCARD_EMAIL_PATTERN = re.compile(
    r'class\s*=\s*["\'][^"\']*\bemail\b[^"\']*["\'][^>]*>([^<]+)<',
    re.IGNORECASE,
)

# ── Source classification keyword map ─────────────────────────────────────────

_SOURCE_KEYWORDS: list[tuple[str, EmailSource]] = [
    # German
    ("impressum", EmailSource.IMPRESSUM),
    ("kontakt", EmailSource.KONTAKT),
    ("karriere", EmailSource.KARRIERE),
    ("stellenangebote", EmailSource.JOBS_PAGE),
    ("bewerbung", EmailSource.JOBS_PAGE),
    ("ueber-uns", EmailSource.ABOUT_PAGE),
    ("datenschutz", EmailSource.DATENSCHUTZ),
    # English
    ("jobs", EmailSource.JOBS_PAGE),
    ("careers", EmailSource.JOBS_PAGE),
    ("hiring", EmailSource.JOBS_PAGE),
    ("work-with-us", EmailSource.JOBS_PAGE),
    ("join", EmailSource.JOBS_PAGE),
    ("about", EmailSource.ABOUT_PAGE),
    ("team", EmailSource.ABOUT_PAGE),
    ("about-us", EmailSource.ABOUT_PAGE),
    ("contact", EmailSource.CONTACT_PAGE),
    ("legal", EmailSource.LEGAL),
]


# ── Public API ────────────────────────────────────────────────────────────────

def extract_emails_from_text(text: str) -> list[str]:
    """Extract all valid, unique emails from a plain text string."""
    if not text:
        return []
    deobfuscated = _deobfuscate_text(text)
    found = EMAIL_PATTERN.findall(deobfuscated)
    seen: set[str] = set()
    result: list[str] = []
    for e in found:
        key = e.lower()
        if key not in seen and _is_valid_email(e):
            seen.add(key)
            result.append(key)
    return result


def extract_emails_from_html(html: str) -> list[str]:
    """Extract emails from HTML including mailto links, structured data,
    data-attributes, vCard markup, and text content."""
    if not html:
        return []

    emails: set[str] = set()

    # 1. mailto: links — highest confidence (also URL-decode %40 etc.)
    for match in _MAILTO_PATTERN.finditer(html):
        raw = unquote(match.group(1)).strip().lower()
        if _is_valid_email(raw):
            emails.add(raw)

    # 2. JSON-LD / structured data — "email" field
    for match in _JSONLD_EMAIL_PATTERN.finditer(html):
        email = match.group(1).strip().lower()
        if _is_valid_email(email):
            emails.add(email)

    # 3. JSON-LD contactPoint → email
    for match in _JSONLD_CONTACT_PATTERN.finditer(html):
        email = match.group(1).strip().lower()
        if _is_valid_email(email):
            emails.add(email)

    # 4. data-email / data-mail / data-contact attributes
    for match in _DATA_EMAIL_PATTERN.finditer(html):
        email = match.group(1).strip().lower()
        if _is_valid_email(email):
            emails.add(email)

    # 5. <meta> tags with email-like content
    for match in _META_EMAIL_PATTERN.finditer(html):
        for candidate in EMAIL_PATTERN.findall(match.group(1)):
            c = candidate.strip().lower()
            if _is_valid_email(c):
                emails.add(c)

    # 6. vCard / hCard microformat (class="email")
    for match in _VCARD_EMAIL_PATTERN.finditer(html):
        text_content = match.group(1).strip()
        for candidate in EMAIL_PATTERN.findall(text_content):
            c = candidate.strip().lower()
            if _is_valid_email(c):
                emails.add(c)

    # 7. General text extraction — strip HTML, decode entities, then regex
    text = _strip_html_tags(html)
    emails.update(extract_emails_from_text(text))

    return sorted(emails)


def classify_email_source(url: str) -> EmailSource:
    """Determine EmailSource enum from a URL path."""
    path = urlparse(url).path.lower()
    for keyword, source in _SOURCE_KEYWORDS:
        if keyword in path:
            return source
    return EmailSource.OTHER


def get_contact_page_urls(base_url: str, discovery_paths: list[str]) -> list[str]:
    """Generate candidate contact/legal page URLs for a given domain."""
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    urls = [base_url]  # Always include the home page
    for path in discovery_paths:
        urls.append(urljoin(base + "/", path))
    return urls


def deduplicate_emails(emails: list[str]) -> list[str]:
    """Return unique emails, sorted by relevance for lead generation.
    Prefers HR/career/contact prefixes over generic ones."""
    seen: set[str] = set()
    priority_prefixes = [
        "info@", "contact@", "kontakt@",
        "jobs@", "karriere@", "bewerbung@",
        "hr@", "personal@", "stellenangebote@",
        "recruiting@", "hiring@",
    ]
    result = []
    for email in emails:
        key = email.lower()
        if key not in seen:
            seen.add(key)
            result.append(email)
    result.sort(key=lambda e: next(
        (i for i, p in enumerate(priority_prefixes) if e.lower().startswith(p)), 999
    ))
    return result


def normalize_phone(phone: str) -> str:
    """Normalize phone number to consistent format."""
    if not phone:
        return phone
    cleaned = phone.strip()
    cleaned = cleaned.replace("\xa0", " ")
    # German international prefix: 0049 -> +49
    cleaned = re.sub(r"^0049\s*", "+49 ", cleaned)
    # Remove cosmetic (0) in area codes: +49 (0)89 -> +49 89
    cleaned = re.sub(r"\(0\)\s*", "", cleaned)
    # Strip everything except digits, +, parentheses, slash, dash, space
    cleaned = re.sub(r"[^\d+\(\)\-/\s]", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 10:
        return ""
    if re.fullmatch(r"\d{8}", digits):
        return ""

    def _looks_suspicious(national: str) -> bool:
        return (
            not national
            or len(national) < 9
            or len(national) > 12
            or national.startswith("00")
            or re.fullmatch(r"0+\d+", national) is not None
        )

    if cleaned.startswith("+49"):
        national = digits[2:]
        if _looks_suspicious(national):
            return ""
        suffix = cleaned[3:].strip()
        suffix = re.sub(r"^0+\b", "", suffix).strip()
        suffix = re.sub(r"\s{2,}", " ", suffix)
        return f"+49 {suffix}".strip()

    if digits.startswith("49"):
        national = digits[2:]
        if _looks_suspicious(national):
            return ""
        return f"+49 {national}"

    if digits.startswith("0"):
        national = digits[1:]
        if _looks_suspicious(national):
            return ""
        suffix = cleaned[1:].strip()
        suffix = re.sub(r"\s{2,}", " ", suffix)
        return f"+49 {suffix}".strip()

    return ""


def normalize_website(url: str) -> str:
    """Ensure website URL has a scheme."""
    if not url:
        return url
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


# ── Internal helpers ──────────────────────────────────────────────────────────

def _deobfuscate_text(text: str) -> str:
    """Replace common email obfuscation patterns with their real characters."""
    for pattern, replacement in OBFUSCATION_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _is_valid_email(email: str) -> bool:
    """Validate that a candidate string is a real, useful email address."""
    if not email or not email.strip():
        return False
    email = email.strip()
    if len(email) > 254:
        return False

    parts = email.split("@")
    if len(parts) != 2:
        return False

    local, domain = parts
    if not local or not domain:
        return False

    # Local-part sanity: reject leading/trailing dots and consecutive dots
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False

    # Domain validation
    if domain.lower() in EXCLUDED_EMAIL_DOMAINS:
        return False
    if not re.match(r"^[a-zA-Z0-9\-]+(\.[a-zA-Z0-9\-]+)*\.[a-zA-Z]{2,}$", domain):
        return False

    # Reject file extensions masquerading as TLDs
    tld = domain.split(".")[-1].lower()
    if tld in FALSE_POSITIVE_TLDS:
        return False

    # Reject noreply / do-not-reply addresses (useless for lead gen)
    local_lower = local.lower()
    if local_lower in NOREPLY_PREFIXES:
        return False

    return True


def _strip_html_tags(html: str) -> str:
    """Remove HTML tags and decode entities to get clean, searchable text."""
    # Remove comments (may contain false-positive addresses)
    text = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    # Remove <style> blocks
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove <script> blocks
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove <noscript> blocks (often tracking pixels with email-like URLs)
    text = re.sub(r"<noscript[^>]*>.*?</noscript>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode HTML entities (&#64; → @, &#x40; → @, &amp; → &, etc.)
    text = html_lib.unescape(text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()
