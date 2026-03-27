"""
ZUGZWANG - Unit Tests
Tests for pure parsing/extraction functions — no browser required.
Run: pytest tests/ -v
"""

from types import SimpleNamespace

import pytest
from src.services.email_extractor import (
    extract_emails_from_text,
    extract_emails_from_html,
    classify_email_source,
    normalize_phone,
    normalize_website,
    deduplicate_emails,
    _is_valid_email,
    _deobfuscate_text,
)
from src.core.models import LeadRecord, SearchConfig, ScrapingStatus, SourceType, EmailSource
from src.services.orchestrator import ScrapingOrchestrator
from src.services.website_crawler import WebsiteEmailCrawler


# ── Email extraction ──────────────────────────────────────────────────────────

class TestEmailExtraction:

    def test_simple_email_from_text(self):
        assert "info@example.de" in extract_emails_from_text("Contact us at info@example.de")

    def test_multiple_emails(self):
        text = "info@company.de and jobs@company.de are valid"
        found = extract_emails_from_text(text)
        assert "info@company.de" in found
        assert "jobs@company.de" in found

    def test_deobfuscated_at(self):
        text = "info [at] company.de"
        found = extract_emails_from_text(text)
        assert len(found) >= 1

    def test_mailto_link_extraction(self):
        html = '<a href="mailto:jobs@firma.de">Kontakt</a>'
        found = extract_emails_from_html(html)
        assert "jobs@firma.de" in found

    def test_json_ld_email(self):
        html = '{"@type": "Organization", "email": "info@test.de"}'
        found = extract_emails_from_html(html)
        assert "info@test.de" in found

    def test_rejects_image_domain(self):
        assert not _is_valid_email("test@banner.png")
        assert not _is_valid_email("user@logo.jpg")

    def test_rejects_excluded_domains(self):
        assert not _is_valid_email("user@example.com")
        assert not _is_valid_email("x@test.com")

    def test_valid_german_email(self):
        assert _is_valid_email("bewerbung@pflegeheim-muenchen.de")

    def test_rejects_empty(self):
        assert not _is_valid_email("")
        assert not _is_valid_email("  ")

    def test_deobfuscation(self):
        result = _deobfuscate_text("info [at] company [dot] de")
        assert "@" in result

    def test_extract_from_empty_html(self):
        assert extract_emails_from_html("") == []

    def test_no_duplicates_returned(self):
        html = "info@test.de info@test.de INFO@TEST.DE"
        found = extract_emails_from_text(html)
        assert len(found) == 1

    def test_rejects_too_long_email(self):
        long = "a" * 250 + "@example.de"
        assert not _is_valid_email(long)

    # ── New: HTML entity decoding ─────────────────────────────────────────

    def test_html_entity_numeric_at_sign(self):
        """&#64; is a common way sites encode '@' to deter scraping."""
        html = "<p>info&#64;company.de</p>"
        found = extract_emails_from_html(html)
        assert "info@company.de" in found

    def test_html_entity_hex_at_sign(self):
        """&#x40; is the hex equivalent."""
        html = "<p>info&#x40;company.de</p>"
        found = extract_emails_from_html(html)
        assert "info@company.de" in found

    # ── New: URL-encoded mailto ───────────────────────────────────────────

    def test_url_encoded_mailto(self):
        """Some CMS encode the @ in mailto: as %40."""
        html = '<a href="mailto:info%40company.de">Email</a>'
        found = extract_emails_from_html(html)
        assert "info@company.de" in found

    # ── New: data-email attributes ────────────────────────────────────────

    def test_data_email_attribute(self):
        html = '<span data-email="jobs@firma.de">Contact</span>'
        found = extract_emails_from_html(html)
        assert "jobs@firma.de" in found

    def test_data_mail_attribute(self):
        html = '<div data-mail="hr@company.de"></div>'
        found = extract_emails_from_html(html)
        assert "hr@company.de" in found

    # ── New: obfuscation patterns ─────────────────────────────────────────

    def test_curly_brace_at_obfuscation(self):
        text = "info {at} company.de"
        found = extract_emails_from_text(text)
        assert "info@company.de" in found

    def test_curly_brace_dot_obfuscation(self):
        text = "info@company {dot} de"
        found = extract_emails_from_text(text)
        assert "info@company.de" in found

    # ── New: noreply rejection ────────────────────────────────────────────

    def test_rejects_noreply(self):
        assert not _is_valid_email("noreply@company.de")
        assert not _is_valid_email("no-reply@company.de")
        assert not _is_valid_email("donotreply@company.de")

    # ── New: file extension TLD rejection ─────────────────────────────────

    def test_rejects_css_extension(self):
        assert not _is_valid_email("style@main.css")

    def test_rejects_js_extension(self):
        assert not _is_valid_email("app@bundle.js")

    def test_rejects_jpeg_extension(self):
        assert not _is_valid_email("photo@hero.jpeg")

    # ── New: local-part validation ────────────────────────────────────────

    def test_rejects_leading_dot_in_local(self):
        assert not _is_valid_email(".user@company.de")

    def test_rejects_trailing_dot_in_local(self):
        assert not _is_valid_email("user.@company.de")

    def test_rejects_consecutive_dots_in_local(self):
        assert not _is_valid_email("user..name@company.de")

    # ── New: excluded platform domains ────────────────────────────────────

    def test_rejects_google(self):
        assert not _is_valid_email("user@google.com")

    def test_rejects_wordpress(self):
        assert not _is_valid_email("user@wordpress.com")

    def test_rejects_schema_org(self):
        assert not _is_valid_email("info@schema.org")

    # ── New: HTML comment stripping ───────────────────────────────────────

    def test_ignores_email_in_html_comment(self):
        html = "<!-- debug: test@internal.dev --><p>No emails here</p>"
        found = extract_emails_from_html(html)
        assert "test@internal.dev" not in found

    # ── New: contactPoint structured data ─────────────────────────────────

    def test_json_ld_contact_point_email(self):
        html = '{"@type": "Organization", "contactPoint": {"@type": "ContactPoint", "email": "support@firma.de"}}'
        found = extract_emails_from_html(html)
        assert "support@firma.de" in found


# ── Email source classification ───────────────────────────────────────────────

class TestEmailSourceClassification:

    def test_impressum(self):
        assert classify_email_source("https://company.de/impressum") == EmailSource.IMPRESSUM

    def test_kontakt(self):
        assert classify_email_source("https://company.de/kontakt/") == EmailSource.KONTAKT

    def test_karriere(self):
        assert classify_email_source("https://company.de/karriere") == EmailSource.KARRIERE

    def test_about(self):
        assert classify_email_source("https://company.de/about-us") == EmailSource.ABOUT_PAGE

    def test_unknown(self):
        assert classify_email_source("https://company.de/blog/post/1") == EmailSource.OTHER

    # ── New: expanded keywords ────────────────────────────────────────────

    def test_team_page(self):
        assert classify_email_source("https://company.de/team") == EmailSource.ABOUT_PAGE

    def test_stellenangebote(self):
        assert classify_email_source("https://company.de/stellenangebote") == EmailSource.JOBS_PAGE

    def test_bewerbung(self):
        assert classify_email_source("https://company.de/bewerbung") == EmailSource.JOBS_PAGE

    def test_careers(self):
        assert classify_email_source("https://company.de/careers") == EmailSource.JOBS_PAGE

    def test_ueber_uns(self):
        assert classify_email_source("https://company.de/ueber-uns") == EmailSource.ABOUT_PAGE


# ── Normalization ─────────────────────────────────────────────────────────────

class TestNormalization:

    def test_phone_strips_chars(self):
        assert normalize_phone("+49 (089) 123-456") == "+49 (089) 123-456"

    def test_website_adds_https(self):
        assert normalize_website("company.de") == "https://company.de"

    def test_website_strips_trailing_slash(self):
        assert normalize_website("https://company.de/") == "https://company.de"

    def test_website_preserves_existing_scheme(self):
        assert normalize_website("http://old-site.de") == "http://old-site.de"

    # ── New: German phone normalization ───────────────────────────────────

    def test_phone_0049_to_plus49(self):
        result = normalize_phone("0049 89 1234567")
        assert result.startswith("+49")

    def test_phone_removes_cosmetic_zero(self):
        result = normalize_phone("+49 (0)89 1234567")
        assert "(0)" not in result


# ── Deduplication ─────────────────────────────────────────────────────────────

class TestDeduplication:

    def test_deduplicates(self):
        emails = ["info@test.de", "info@test.de", "jobs@test.de"]
        result = deduplicate_emails(emails)
        assert result.count("info@test.de") == 1

    def test_prefers_info_prefix(self):
        emails = ["z_other@test.de", "info@test.de"]
        result = deduplicate_emails(emails)
        assert result[0] == "info@test.de"

    def test_empty_list(self):
        assert deduplicate_emails([]) == []

    # ── New: German HR prefixes ───────────────────────────────────────────

    def test_prefers_karriere_prefix(self):
        emails = ["z_random@test.de", "karriere@test.de"]
        result = deduplicate_emails(emails)
        assert result[0] == "karriere@test.de"

    def test_prefers_bewerbung_prefix(self):
        emails = ["z_random@test.de", "bewerbung@test.de"]
        result = deduplicate_emails(emails)
        assert result[0] == "bewerbung@test.de"

    def test_prefers_personal_prefix(self):
        emails = ["z_random@test.de", "personal@test.de"]
        result = deduplicate_emails(emails)
        assert result[0] == "personal@test.de"


# ── Data models ───────────────────────────────────────────────────────────────

class TestLeadRecord:

    def test_default_id_generated(self):
        r = LeadRecord()
        assert r.id and len(r.id) == 36  # UUID4

    def test_has_email(self):
        r = LeadRecord(email="test@test.de")
        assert r.has_email()

    def test_no_email(self):
        r = LeadRecord()
        assert not r.has_email()

    def test_to_dict(self):
        r = LeadRecord(company_name="Test GmbH", email="info@test.de")
        d = r.to_dict()
        assert d["company_name"] == "Test GmbH"
        assert d["email"] == "info@test.de"

    def test_roundtrip(self):
        r = LeadRecord(
            company_name="Klinikum München",
            email="jobs@klinikum.de",
            source_type=SourceType.GOOGLE_MAPS,
        )
        d = r.to_dict()
        r2 = LeadRecord.from_dict(d)
        assert r2.company_name == r.company_name
        assert r2.email == r.email
        assert r2.source_type == SourceType.GOOGLE_MAPS

    def test_display_name_company(self):
        r = LeadRecord(company_name="Klinikum")
        assert r.display_name() == "Klinikum"

    def test_display_name_fallback(self):
        r = LeadRecord(job_title="Pflegefachmann")
        assert r.display_name() == "Pflegefachmann"


# ── SearchConfig ──────────────────────────────────────────────────────────────

class TestSearchConfig:

    def test_defaults(self):
        c = SearchConfig()
        assert c.max_results == 100
        assert c.scrape_emails is True
        assert c.headless is True

    def test_custom_values(self):
        c = SearchConfig(job_title="Pflegeheim", city="München", max_results=50)
        assert c.job_title == "Pflegeheim"
        assert c.city == "München"
        assert c.max_results == 50


class TestOrchestrator:

    def test_build_export_job_uses_selected_records_for_sqlite(self):
        orchestrator = ScrapingOrchestrator()
        selected = [LeadRecord(company_name="Visible GmbH")]
        hidden = LeadRecord(company_name="Hidden GmbH")
        orchestrator._current_job = SimpleNamespace(
            id="job-123",
            config=SearchConfig(job_title="Pflege"),
            status=ScrapingStatus.RUNNING,
            created_at="2026-01-01T00:00:00",
            started_at="2026-01-01T00:05:00",
            completed_at=None,
            error_message=None,
            log_entries=["started"],
            total_errors=2,
            results=[selected[0], hidden],
        )

        export_job = orchestrator._build_export_job(selected)

        assert export_job.results == selected
        assert export_job.total_found == 1
        assert export_job.total_errors == 2
        assert export_job.id == "job-123"

    def test_build_export_job_creates_snapshot_without_current_job(self):
        orchestrator = ScrapingOrchestrator()
        record = LeadRecord(company_name="Standalone GmbH", email="info@example.de")

        export_job = orchestrator._build_export_job([record])

        assert export_job.results == [record]
        assert export_job.status == ScrapingStatus.COMPLETED
        assert export_job.total_found == 1
        assert export_job.total_emails == 1


class TestWebsiteEmailCrawler:

    def test_cache_key_includes_company_identity(self):
        crawler = WebsiteEmailCrawler(SimpleNamespace(settings=SimpleNamespace()))

        assert crawler._cache_key("https://example.com/jobs", "Alpha Pflege GmbH") == "https://example.com|alpha-pflege"
        assert crawler._cache_key("https://EXAMPLE.com/contact", "Beta Pflege GmbH") == "https://example.com|beta-pflege"

    def test_website_matches_company_when_domain_contains_name(self):
        crawler = WebsiteEmailCrawler(SimpleNamespace(settings=SimpleNamespace()))

        assert crawler._website_matches_company(
            "https://alpha-pflege.de",
            "Alpha Pflege GmbH",
            "<html><title>Welcome</title></html>",
        )

    def test_website_rejects_intermediate_portal_for_other_company(self):
        crawler = WebsiteEmailCrawler(SimpleNamespace(settings=SimpleNamespace()))

        assert not crawler._website_matches_company(
            "https://jobs.portal-example.de",
            "Alpha Pflege GmbH",
            "<html><title>Portal Example</title><body>Karriereportal fuer viele Firmen</body></html>",
        )

    def test_prioritize_paths_prefers_contact_pages(self):
        crawler = WebsiteEmailCrawler(SimpleNamespace(settings=SimpleNamespace(default_request_timeout=30)))

        ordered = crawler._prioritize_paths([
            "about",
            "jobs",
            "kontakt",
            "datenschutz",
            "impressum",
        ])

        assert ordered[:2] == ["impressum", "kontakt"]

    def test_timeout_for_deeper_pages_is_shorter(self):
        crawler = WebsiteEmailCrawler(SimpleNamespace(settings=SimpleNamespace(default_request_timeout=30)))

        assert crawler._timeout_for_url("https://alpha.de") == 12_000
        assert crawler._timeout_for_url("https://alpha.de/impressum") == 12_000
        assert crawler._timeout_for_url("https://alpha.de/team") == 8_000

    @pytest.mark.asyncio
    async def test_crawl_page_uses_visible_text_before_html(self):
        class FakePage:
            async def inner_text(self, selector):
                assert selector == "body"
                return "Kontakt: jobs@alpha-pflege.de"

        class FakeSession:
            settings = SimpleNamespace()

            async def navigate(self, page, url, timeout=0, retries=0):
                return True

            async def fetch_url_content_fast(self, url, timeout=0):
                return ""

            async def get_page_content(self, page):
                raise AssertionError("HTML fetch should be skipped when visible text already contains an email")

        crawler = WebsiteEmailCrawler(FakeSession())

        html, emails, source = await crawler._crawl_page(FakePage(), "https://alpha-pflege.de", "job-1")

        assert html == ""
        assert emails == ["jobs@alpha-pflege.de"]
        assert source == "https://alpha-pflege.de"

    @pytest.mark.asyncio
    async def test_crawl_page_can_use_fast_fetch_for_secondary_urls(self):
        class FakePage:
            async def inner_text(self, selector):
                raise AssertionError("Browser page should not be used when fast fetch already succeeded")

        class FakeSession:
            settings = SimpleNamespace(default_request_timeout=30)

            async def navigate(self, page, url, timeout=0, retries=0):
                raise AssertionError("Navigation should be skipped when fast fetch finds the email")

            async def fetch_url_content_fast(self, url, timeout=0):
                return '<a href="mailto:kontakt@alpha-pflege.de">Email</a>'

            async def get_page_content(self, page):
                raise AssertionError("HTML fetch from page should not be used")

        crawler = WebsiteEmailCrawler(FakeSession())

        html, emails, source = await crawler._crawl_page(
            FakePage(),
            "https://alpha-pflege.de/kontakt",
            "job-1",
            prefer_fast_fetch=True,
        )

        assert "kontakt@alpha-pflege.de" in emails
        assert source == "https://alpha-pflege.de/kontakt"
