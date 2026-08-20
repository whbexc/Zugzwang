"""
ZUGZWANG - Email Extractor Service
Pure extraction/parsing logic for finding emails in HTML content.
All functions are side-effect-free and unit-testable.
"""

import html as html_lib
import re
from typing import Optional
from urllib.parse import unquote, urljoin, urlparse

from ..core.models import EmailSource
from ..core.logger import get_logger

logger = get_logger(__name__)
 
# Performance Hardening: Cap processing size for CPU-intensive regex.
# Most valid contact info lives at the head (meta/schema) and tail (footer/impressum).
MAX_PROCESS_SIZE  = 120_000   # 120 KB total
_HEAD_BYTES       =  80_000   # favour head where <meta> / JSON-LD live
_TAIL_BYTES       =  40_000   # footer / Impressum contact info


def _cap_html(html: str) -> str:
    """Trim oversized HTML to head+tail, preserving UTF-8 character boundaries."""
    encoded = html.encode("utf-8", errors="replace")
    if len(encoded) <= MAX_PROCESS_SIZE:
        return html
    head = encoded[:_HEAD_BYTES]
    tail = encoded[-_TAIL_BYTES:]
    return (head + tail).decode("utf-8", errors="replace")

# Robust email regex (handles encoded prefixes and common obfuscation)
# Design notes:
#   - Local part: explicit {1,64} length cap prevents catastrophic backtracking
#   - Primary domain label: [a-zA-Z0-9\-] only (no dot) avoids quadratic
#     backtracking when the dot-repeating group nests inside large HTML attributes
#   - TLD: alpha-only [a-zA-Z]{2,10} eliminates numeric/extension false positives
#   - Lookbehind/lookahead anchors reject embedded matches (e.g. CSS class names)
EMAIL_PATTERN = re.compile(
    r"(?:\\u[\d\w]{4}|\\x[\d\w]{2}|\\f)?"
    r"((?<![a-zA-Z0-9._%+\-])"
    r"[a-zA-Z0-9._%+\-]{1,64}"
    r"(?:@|\[at\]|\(at\)|\[ät\]|\[at\*\]|&#064;|&#x40;)"
    r"[a-zA-Z0-9\-]{1,63}"                     # primary domain label — NO dot allowed here
    r"(?:\.[a-zA-Z0-9\-]{1,63})*"              # optional sub-labels
    r"\.[a-zA-Z]{2,10}"                         # TLD — alpha only, bounded to 10 chars
    r"(?![a-zA-Z0-9._%+\-]))",
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
    "linkedin.com", "youtube.com", "github.com", "apple.com", "stock.adobe.com",
    "adobe.com", "microsoft.com", "amazon.com", "sentry.io",
    # Standards / spec bodies
    "w3.org", "schema.org", "iana.org",
    # Common German false-positives from CMS footers
    "typo3.org", "contao.org", "joomla.org",
    # Job Portals / Platforms (Do not want info@portal.de)
    "arbeitsagentur.de", "stepstone.de", "stepstone.at", "stepstone.ch",
    "heyjobs.co", "heyjobs.de", "indeed.com", "indeed.de", "monster.de", "monster.com",
    "jobware.de", "stellenanzeigen.de", "meinestadt.de", "yourfirm.de", "yourfirm.com",
    "absolventa.de", "azubi.de", "azubiyo.de", "ausbildung.de", "ausbildungsmarkt.de",
    "ausbildungsatlas.de", "praktikum.de", "berufsstart.de", "bewerber.de",
    "jobscout24.de", "kimeta.de", "joblift.de", "jobstairs.de", "jobmensa.de",
    "karriere.de", "karriere.at", "jobs.de", "jobsuche.de", "experteer.de",
    "softgarden.io", "softgarden.de", "personio.de", "personio.com",
    "rexx-systems.com", "d.vinci.de", "jobteaser.com", "whatchado.com",
}

# Emails with these local-part prefixes are typically unmonitored
NOREPLY_PREFIXES = {
    "noreply", "no-reply", "no_reply",
    "donotreply", "do-not-reply", "do_not_reply",
    "mailer-daemon", "postmaster",
}

# Prefixes that indicate placeholder/fake emails
PLACEHOLDER_PREFIXES = {
    "johndoe", "john.doe", "jane.doe", "max", "mustermann", "max.mustermann",
    "youremail", "username", "example", "test", "demo", "placeholder",
    "user", "email", "mail", "contact_person",
}

# File extensions that are definitely not valid TLDs (false positive emails)
FALSE_POSITIVE_TLDS = {
    "png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp", "tiff",
    "css", "js", "html", "htm", "php", "asp", "jsp",
    "pdf", "doc", "docx", "xls", "xlsx", "zip", "rar",
    "woff", "woff2", "ttf", "eot", "map",
}

# Simplified obfuscation patterns for speed
OBFUSCATION_PATTERNS = [
    (r"\[at\]", "@"),
    (r"\(at\)", "@"),
    (r"\[ät\]", "@"),
    (r"\[dot\]", "."),
    (r"\(dot\)", "."),
    (r"\[punkt\]", "."),
    (r"\uff20", "@"),   # ＠
    (r"\uff0e", "."),   # ．
    # Compact spaced version
    (r"(?<=\w)\s*[\(\[]\s*at\s*[\)\]]\s*(?=\w)", "@"),
    (r"(?<=\w)\s+@\s+(?=\w)", "@"),
    (r"(?<=\w)\s+\.\s+(?=\w)", "."),
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
_ATTRIBUTE_EMAIL_PATTERN = re.compile(
    r'(?:aria-label|title|value|content|data-[\w:-]+)\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_META_EMAIL_PATTERN = re.compile(
    r'<meta[^>]+content\s*=\s*["\']([^"\']*@[^"\']*)["\'][^>]*/?>',
    re.IGNORECASE,
)
_VCARD_EMAIL_PATTERN = re.compile(
    r'class\s*=\s*["\'][^"\']*\bemail\b[^"\']*["\'][^>]*>([^<]+)<',
    re.IGNORECASE,
)
_CFEMAIL_PATTERN = re.compile(
    r'data-cfemail\s*=\s*["\']([a-fA-F0-9]+)["\']',
    re.IGNORECASE,
)

def _decode_cfemail(encoded: str) -> str:
    try:
        r = int(encoded[:2], 16)
        return "".join([chr(int(encoded[i:i+2], 16) ^ r) for i in range(2, len(encoded), 2)])
    except Exception:
        return ""


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

_CONTACT_STOPWORDS = {
    "und", "oder", "bitte", "sehr", "bewerbung", "bewerbungen", "kontakt", "telefon",
    "email", "mail", "gmbh", "ag", "ev", "e.v.", "straße", "str", "platz", "weg",
    "allee", "gasse", "berlin", "münchen", "hamburg", "köln", "frankfurt", "stuttgart",
    "düsseldorf", "leipzig", "dortmund", "essen", "bremen", "dresden", "hannover",
    "nürnberg", "duisburg", "bochum", "wuppertal", "bielefeld", "bonn", "münster",
    "uns", "wir", "ihre", "ihr", "unser", "unsere", "fragen", "ansprechpartner",
    "karriere", "stellenangebote", "job", "jobs", "team", "pflegedienstleitung",
}

def extract_contact_person_from_text(text: str) -> Optional[str]:
    """Extract HR contact (Frau / Herr or decision maker title) using NLP regex heuristics."""
    if not text:
        return None

    # 1. High-priority role titles (Ansprechpartner, PDL, HR Manager, etc.)
    role_pattern = re.compile(
        r'\b(?:Ansprechpartner(?:in)?|Pflegedienstleitung|PDL|Pflegedirektor(?:in)?|'
        r'Personalleitung|Personalabteilung|HR[\s-]*Manager(?:in)?|Einrichtungsleitung|'
        r'Heimleitung|Geschäftsführer(?:in)?|Geschäftsleitung|Bewerbung(?:en)?\s+(?:an|bei))'
        r'(?:\s*(?:\(PDL\)|/in|\s+für\s+[A-Za-zÄÖÜäöü]+))?\s*[:\-\s]\s*'
        r'(?:(Frau|Herr)\s+)?'
        r'((?:(?:[A-ZÄÖÜ][a-zA-Zäöüß\-]+|Dr\.|Prof\.|med\.|von|van|der|de|zu)\s*){2,4})',
        re.IGNORECASE
    )
    for match in role_pattern.finditer(text):
        salutation = (match.group(1) or "").capitalize()
        raw_name = re.sub(r'[\s,;:!\?]+$', '', match.group(2)).strip()
        words = raw_name.split()
        if len(words) >= 2 and not any(w.lower() in _CONTACT_STOPWORDS for w in words):
            if salutation in ("Frau", "Herr"):
                return f"{salutation} {raw_name}"
            return raw_name

    # 2. General salutation search (Frau / Herr + Name)
    pattern = re.compile(r'\b(Frau|Herr)\s+((?:(?:[A-ZÄÖÜ][a-zA-Zäöüß\-]+|Dr\.|Prof\.|med\.|von|van|der|de|zu)\s*){1,4})')
    matches = pattern.findall(text)
    
    for m in matches:
        salutation = m[0]
        name = re.sub(r'[\s,;:!\?]+$', '', m[1]).strip()
        words = name.split()
        if name and len(words) >= 1 and not any(w.lower() in _CONTACT_STOPWORDS for w in words):
            return f"{salutation} {name}"
            
    return None

def extract_contact_person_from_html(html: str) -> Optional[str]:
    """Extract HR contact from HTML by stripping tags and applying NLP regex."""
    if not html:
        return None
    text = _strip_html_tags(html)
    return extract_contact_person_from_text(text)


def verify_email_domain_dns(email: str, timeout: float = 3.0) -> bool:
    """
    Verify that an email address has valid syntax and is not in the excluded list.
    Note: Active DNS resolution was removed because macOS mDNSResponder rate-limits 
    tight loops of gethostbyname(), which caused false-positives (NXDOMAIN) on perfectly valid leads.
    """
    return _is_valid_email(email)

def extract_emails_from_text(text: str) -> list[str]:
    """Extract all valid, unique emails from a plain text string."""
    if not text:
        return []
        
    # Pre-process HTML entities if present in "plain" text
    text = html_lib.unescape(text)
    
    deobfuscated = _deobfuscate_text(text)
    found = EMAIL_PATTERN.findall(deobfuscated)
    seen: set[str] = set()
    result: list[str] = []
    for e in found:
        # If the regex matched a group (the email itself), e will be the group
        # If the regex has no groups, e will be the whole match
        email = e if isinstance(e, str) else e[0]
        # Final cleanup for the deobfuscated email
        email = email.replace("[at]", "@").replace("(at)", "@").replace("{at}", "@").replace("[ät]", "@")
        email = email.replace("[at*]", "@").replace("&#064;", "@").replace("&#x40;", "@")
        
        key = email.lower().strip()
        if key not in seen and _is_valid_email(key):
            seen.add(key)
            result.append(key)
    return result


def extract_emails_from_html(html: str) -> list[str]:
    """Extract emails from HTML including mailto links, structured data,
    data-attributes, vCard markup, and text content."""
    if not html:
        return []
        
    # Performance: Trim massive HTML to avoid GIL starvation during regex.
    # _cap_html() uses byte-safe slicing so we never split a multi-byte char.
    if len(html.encode('utf-8', errors='replace')) > MAX_PROCESS_SIZE:
        orig_len = len(html)
        html = _cap_html(html)
        logger.debug(f"Trimmed HTML payload from {orig_len} to {len(html)} chars")

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

    # 4b. Other common attribute payloads that often carry contact emails
    for match in _ATTRIBUTE_EMAIL_PATTERN.finditer(html):
        raw_value = html_lib.unescape(match.group(1).strip())
        for candidate in EMAIL_PATTERN.findall(_deobfuscate_text(raw_value)):
            email = candidate.strip().lower()
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

    # 6b. Cloudflare Email Obfuscation (data-cfemail)
    for match in _CFEMAIL_PATTERN.finditer(html):
        decoded = _decode_cfemail(match.group(1))
        if decoded and _is_valid_email(decoded):
            emails.add(decoded)

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
        "karriere@", "bewerbung@", "jobs@", "hr@", "personal@", 
        "recruiting@", "hiring@", "stellenangebote@",
        "kontakt@", "contact@", "info@", 
    ]
    result = []
    for email in emails:
        key = email.lower()
        if key not in seen and _is_valid_email(key):
            seen.add(key)
            result.append(email)
            
    # Sort by priority - higher precision (HR) first
    def _get_priority(e: str) -> int:
        lower = e.lower()
        for i, p in enumerate(priority_prefixes):
            if lower.startswith(p):
                return i
        return 999
        
    result.sort(key=_get_priority)
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
        
    try:
        idn_domain = domain.encode("idna").decode("ascii")
    except Exception:
        return False
        
    if not re.match(r"^[a-zA-Z0-9\-]+(\.[a-zA-Z0-9\-]+)*\.[a-zA-Z]{2,}$", idn_domain):
        return False

    # Reject file extensions masquerading as TLDs
    tld = domain.split(".")[-1].lower()
    if tld in FALSE_POSITIVE_TLDS:
        return False

    # Reject noreply / do-not-reply addresses (useless for lead gen)
    local_lower = local.lower()
    if local_lower in NOREPLY_PREFIXES:
        return False

    # Reject placeholder names (e.g. Max Mustermann, John Doe)
    if any(local_lower.startswith(p) for p in PLACEHOLDER_PREFIXES):
        return False
        
    # Also check if domain contains portal keywords
    portal_keywords = ("job", "karriere", "stellenanzeige", "bewerbung", "recruiting")
    if any(kw in domain.lower() for kw in portal_keywords):
        # Allow it only if it's not a known big portal (already handled by blocklist)
        # but be conservative: if it's info@somejobboard.com, we probably don't want it.
        if local_lower in ("info", "kontakt", "support", "office", "admin"):
             return False

    return True


def _strip_html_tags(html: str) -> str:
    """Remove HTML tags and decode entities.

    The input must already be capped by _cap_html() before calling this
    function — we do NOT re-cap here to avoid a second encode/decode pass.
    All patterns use explicit length bounds or [^<]+ guards so there is no
    unbounded .*? with re.DOTALL that could stall the GIL on large inputs.
    """
    if not html:
        return ""

    # 1. Remove HTML comments (bounded: stop at first "-->")
    text = re.sub(r"<!--[\s\S]{0,65536}?-->", " ", html)

    # 2. Remove known zero-text block elements.
    #    We match the opening tag then consume content as [^<]* runs separated
    #    by non-closing tags, which avoids unbounded .*? with DOTALL.
    _BLOCK_RE = re.compile(
        r"<(script|style|noscript|svg|canvas|video|audio|iframe|object|embed)"
        r"(?:[^>]*)>[\s\S]{0,200000}?</\1>",
        re.IGNORECASE,
    )
    text = _BLOCK_RE.sub(" ", text)

    # 3. Strip remaining HTML tags — [^>]+ is already non-catastrophic
    text = re.sub(r"<[^>]{0,2048}>", " ", text)

    # 4. Decode HTML entities and normalise whitespace
    text = html_lib.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# 1.1.0 Beta5.1
