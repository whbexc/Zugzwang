"""
ZUGZWANG - Jobsuche API client
Lightweight client for the Arbeitsagentur Jobsuche JSON endpoints.

This client is intentionally small:
- fetches structured search results directly from the API
- converts them into the app's LeadRecord shape
- leaves browser detail crawling to the existing scraper as fallback
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from ..core.logger import get_logger
from ..core.models import LeadRecord, SearchConfig, SourceType

logger = get_logger(__name__)

API_BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
API_SEARCH_PATH = "/pc/v4/app/jobs"
DEFAULT_API_KEY = "jobboerse-jobsuche"
DEFAULT_USER_AGENT = (
    "Jobsuche/2.9.2 (de.arbeitsagentur.jobboerse; build:1077; iOS 15.1.0) "
    "Alamofire/5.4.4"
)


class JobsucheAPIError(RuntimeError):
    """Raised when the Jobsuche API request fails or returns malformed data."""


@dataclass(frozen=True)
class JobsucheQuery:
    params: dict[str, Any]
    url: str


def resolve_offer_type_code(offer_type: str) -> Optional[int]:
    mapping = {
        "arbeit": 1,
        "ausbildung/duales studium": 4,
        "praktikum/trainee/werkstudent": 34,
        "selbstständigkeit": 2,
        "selbstaendigkeit": 2,
        "selbststÃ¤ndigkeit": 2,
    }
    return mapping.get((offer_type or "").strip().lower())


def build_jobsuche_query(config: SearchConfig, page: int, page_size: int) -> JobsucheQuery:
    location = config.city or config.region
    if not location and config.country and config.country != "Germany":
        location = config.country

    params: dict[str, Any] = {
        "page": page,
        "size": page_size,
        "pav": "false",
    }

    if config.job_title:
        params["was"] = config.job_title
    if location:
        params["wo"] = location

    offer_code = resolve_offer_type_code(config.offer_type)
    if offer_code is not None:
        params["angebotsart"] = offer_code

    query_string = urlencode(params, doseq=True)
    return JobsucheQuery(
        params=params,
        url=f"{API_BASE_URL}{API_SEARCH_PATH}?{query_string}",
    )


def _format_address(arbeitsort: dict[str, Any]) -> str:
    parts: list[str] = []

    street = str(arbeitsort.get("strasse") or "").strip()
    postal = str(arbeitsort.get("plz") or "").strip()
    city = str(arbeitsort.get("ort") or "").strip()
    region = str(arbeitsort.get("region") or "").strip()
    country = str(arbeitsort.get("land") or "").strip()

    if street:
        parts.append(street)
    line_two_bits = " ".join(part for part in [postal, city] if part)
    if line_two_bits:
        parts.append(line_two_bits)
    if region and region not in {city, postal}:
        parts.append(region)
    if country and country not in {city, region}:
        parts.append(country)

    return ", ".join(parts)


def job_payload_to_record(payload: dict[str, Any], config: SearchConfig) -> LeadRecord:
    arbeitsort = payload.get("arbeitsort") or {}
    city = str(arbeitsort.get("ort") or arbeitsort.get("region") or "").strip()
    postal_code = str(arbeitsort.get("plz") or "").strip() or None
    region = str(arbeitsort.get("region") or "").strip() or None
    country = str(arbeitsort.get("land") or config.country or "").strip() or None

    record = LeadRecord(
        source_type=SourceType.JOBSUCHE,
        source_url=None,
        search_query=" · ".join(filter(None, [config.job_title, config.city or config.region, config.country])),
        company_name=str(payload.get("arbeitgeber") or "").strip() or None,
        job_title=str(payload.get("beruf") or payload.get("titel") or "").strip() or None,
        publication_date=str(payload.get("aktuelleVeroeffentlichungsdatum") or "").strip() or None,
        address=_format_address(arbeitsort) or None,
        city=city or None,
        region=region,
        country=country,
        postal_code=postal_code,
        notes=_build_notes(payload),
    )
    return record.normalize()


def _build_notes(payload: dict[str, Any]) -> Optional[str]:
    notes: list[str] = []
    if payload.get("refnr"):
        notes.append(f"refnr={payload['refnr']}")
    if payload.get("hashId"):
        notes.append(f"hashId={payload['hashId']}")
    if payload.get("eintrittsdatum"):
        notes.append(f"eintrittsdatum={payload['eintrittsdatum']}")
    if payload.get("modifikationsTimestamp"):
        notes.append(f"modifikationsTimestamp={payload['modifikationsTimestamp']}")
    return " | ".join(notes) if notes else None


class JobsucheAPIClient:
    """Small async client for Jobsuche listing requests."""

    def __init__(self, api_key: Optional[str] = None, verify: bool = False):
        self.api_key = api_key or os.getenv("JOBSUCHE_API_KEY") or DEFAULT_API_KEY
        self.verify = verify
        self._headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Host": "rest.arbeitsagentur.de",
            "X-API-Key": self.api_key,
            "Connection": "keep-alive",
            "Accept": "application/json",
        }

    async def fetch_records(self, config: SearchConfig) -> list[LeadRecord]:
        records: list[LeadRecord] = []
        seen: set[str] = set()
        max_results = max(1, int(config.max_results or 100))
        page_size = min(100, max_results)
        page = 1

        async with httpx.AsyncClient(
            base_url=API_BASE_URL,
            headers=self._headers,
            timeout=30.0,
            verify=self.verify,
        ) as client:
            while len(records) < max_results:
                query = build_jobsuche_query(config, page=page, page_size=page_size)
                response = await client.get(API_SEARCH_PATH, params=query.params)
                response.raise_for_status()

                payload = response.json()
                items = payload.get("stellenangebote") or []
                if not isinstance(items, list):
                    raise JobsucheAPIError("Unexpected Jobsuche API response: 'stellenangebote' is not a list")

                if not items:
                    break

                for item in items:
                    if not isinstance(item, dict):
                        continue

                    record = job_payload_to_record(item, config)
                    record.source_url = query.url
                    dedupe_key = record.stable_id()
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    records.append(record)
                    if len(records) >= max_results:
                        break

                if len(items) < page_size:
                    break
                page += 1

        if config.latest_offers_only:
            records.sort(
                key=_publication_sort_key,
                reverse=True,
            )

        logger.info("Jobsuche API returned %s structured records", len(records))
        return records


def _publication_sort_key(record: LeadRecord) -> tuple[int, str]:
    if not record.publication_date:
        return (0, "")

    value = record.publication_date.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            dt = datetime.strptime(value, fmt)
            return (1, dt.isoformat())
        except ValueError:
            continue

    return (1, value)
