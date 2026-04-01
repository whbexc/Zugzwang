from src.core.models import SearchConfig, SourceType
from unittest.mock import MagicMock
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.services.jobsuche_api import build_jobsuche_query, job_payload_to_record, resolve_offer_type_code
from src.services.jobsuche_scraper import JobsucheScraper
from src.services.website_crawler import WebsiteEmailCrawler


def test_resolve_offer_type_code_maps_jobsuche_modes():
    assert resolve_offer_type_code("Arbeit") == 1
    assert resolve_offer_type_code("Ausbildung/Duales Studium") == 4
    assert resolve_offer_type_code("Praktikum/Trainee/Werkstudent") == 34
    assert resolve_offer_type_code("Selbstständigkeit") == 2


def test_build_jobsuche_query_uses_location_and_offer_type():
    config = SearchConfig(
        job_title="Software Engineer",
        city="Berlin",
        country="Germany",
        offer_type="Ausbildung/Duales Studium",
        max_results=25,
    )

    query = build_jobsuche_query(config, page=2, page_size=25)

    assert query.params["was"] == "Software Engineer"
    assert query.params["wo"] == "Berlin"
    assert query.params["page"] == 2
    assert query.params["size"] == 25
    assert query.params["angebotsart"] == 4
    assert query.params["pav"] == "false"
    assert "page=2" in query.url
    assert "angebotsart=4" in query.url


def test_job_payload_to_record_normalizes_core_fields():
    config = SearchConfig(job_title="Data Analyst", city="Mannheim", country="Germany")
    payload = {
        "arbeitgeber": "Example GmbH",
        "beruf": "Data Analyst",
        "aktuelleVeroeffentlichungsdatum": "2026-03-31",
        "refnr": "10000-1234567890-S",
        "hashId": "abc123",
        "arbeitsort": {
            "plz": 68159,
            "ort": "Mannheim",
            "strasse": "Hauptstrasse 1",
            "region": "Baden-Wuerttemberg",
            "land": "Deutschland",
        },
    }

    record = job_payload_to_record(payload, config)

    assert record.source_type == SourceType.JOBSUCHE
    assert record.company_name == "Example GmbH"
    assert record.job_title == "Data Analyst"
    assert record.publication_date == "2026-03-31"
    assert record.city == "Mannheim"
    assert record.postal_code == "68159"
    assert record.address == "Hauptstrasse 1, 68159 Mannheim, Baden-Wuerttemberg, Deutschland"
    assert record.notes == "refnr=10000-1234567890-S | hashId=abc123"


def test_jobsuche_scraper_prefers_employer_site_over_job_portal():
    session = MagicMock()
    session.settings = SimpleNamespace(
        default_request_timeout=30,
        default_respect_robots=False,
        email_discovery_paths=[],
    )
    scraper = JobsucheScraper(session, SearchConfig(), "job-1")

    candidates = [
        "https://www.heyjobs.co/de-de/jobs/123",
        "https://www.example-employer.de/impressum",
    ]

    assert scraper._is_job_portal_domain(candidates[0]) is True
    assert scraper._choose_preferred_website(candidates) == candidates[1]


def test_jobsuche_scraper_rejects_untrusted_jobsuche_and_portal_candidates():
    session = MagicMock()
    session.settings = SimpleNamespace(
        default_request_timeout=30,
        default_respect_robots=False,
        email_discovery_paths=[],
    )
    scraper = JobsucheScraper(session, SearchConfig(), "job-1")

    assert scraper._is_untrusted_website_candidate(
        "https://www.kununu.com/de/bundesagentur-fuer-arbeit"
    ) is True
    assert scraper._is_untrusted_website_candidate(
        "https://www.arbeitsagentur.de/jobsuche/suche?kundennummer=abc"
    ) is True
    assert scraper._is_untrusted_website_candidate(
        "https://www.example-employer.de/karriere"
    ) is False


def test_jobsuche_scraper_keeps_no_website_when_only_portal_candidates_exist():
    session = MagicMock()
    session.settings = SimpleNamespace(
        default_request_timeout=30,
        default_respect_robots=False,
        email_discovery_paths=[],
    )
    scraper = JobsucheScraper(session, SearchConfig(), "job-1")

    candidates = [
        "https://www.kununu.com/de/bundesagentur-fuer-arbeit",
        "https://www.arbeitsagentur.de/jobsuche/suche?kundennummer=abc",
    ]

    assert scraper._choose_preferred_website(candidates) is None


def test_jobsuche_scraper_rejects_social_and_apply_hosts():
    session = MagicMock()
    session.settings = SimpleNamespace(
        default_request_timeout=30,
        default_respect_robots=False,
        email_discovery_paths=[],
    )
    scraper = JobsucheScraper(session, SearchConfig(), "job-1")

    assert scraper._is_untrusted_website_candidate(
        "https://www.instagram.com/bundesagenturfuerarbeit"
    ) is True
    assert scraper._is_untrusted_website_candidate(
        "https://bewerbung.drk-eisenach.de/de/jobposting/abc/apply?ref=homepage"
    ) is True
    assert scraper._is_untrusted_website_candidate(
        "https://web.arbeitsagentur.de/vermittlung/ag-darstellung-ui/anzeigen/abc"
    ) is True


def test_jobsuche_scraper_extracts_address_lines_from_panel_text():
    session = MagicMock()
    session.settings = SimpleNamespace(
        default_request_timeout=30,
        default_respect_robots=False,
        email_discovery_paths=[],
    )
    scraper = JobsucheScraper(session, SearchConfig(), "job-1")

    panel_text = (
        "Informationen zur Bewerbung\n"
        "Wohn und Pflegezentrum Sande GmbH\n"
        "Herr Martin Taubenheim\n"
        "Am Maddick 4\n"
        "26452 Sande, Kreis Friesl\n"
        "E-Mail: taubenheim@curaliving.de\n"
        "Bewerben Sie sich:\n"
        "per E-Mail\n"
    )

    assert scraper._extract_address_lines_from_panel_text(panel_text) == [
        "Wohn und Pflegezentrum Sande GmbH",
        "Herr Martin Taubenheim",
        "Am Maddick 4",
        "26452 Sande, Kreis Friesl",
    ]


def test_website_crawler_cache_key_includes_company_name():
    crawler = WebsiteEmailCrawler.__new__(WebsiteEmailCrawler)
    key_a = WebsiteEmailCrawler._cache_key(crawler, "https://www.kununu.com/de/foo", "Company A")
    key_b = WebsiteEmailCrawler._cache_key(crawler, "https://www.kununu.com/de/foo", "Company B")

    assert key_a != key_b


def test_jobsuche_scraper_extracts_mailto_from_simple_paragraph_html():
    session = MagicMock()
    session.settings = SimpleNamespace(
        default_request_timeout=30,
        default_respect_robots=False,
        email_discovery_paths=[],
    )
    scraper = JobsucheScraper(session, SearchConfig(), "job-1")

    async def fake_panel_html(_page):
        return '<p>per E-Mail an <a href="mailto:m.schiemann@pbe-vg.de" target="_blank" class="ba-link-secondary">m.schiemann@pbe-vg.de</a>.</p>'

    scraper._get_application_panel_html = fake_panel_html

    page = MagicMock()
    empty_locator = MagicMock()
    empty_locator.count = AsyncMock(return_value=0)
    page.locator.return_value.first = empty_locator

    result = asyncio.run(scraper._extract_application_email(page))

    assert result == "m.schiemann@pbe-vg.de"
