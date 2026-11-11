import json
from datetime import datetime
from hashlib import sha256
from typing import Protocol
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from jobsift.acquisition.models import ParseReport, RawJobPosting, SourceConfig


class ParserDriftError(ValueError):
    """Raised when configured selectors no longer produce trustworthy records."""


class JobContentParser(Protocol):
    def parse(
        self,
        content: bytes,
        config: SourceConfig,
        acquired_at: datetime,
    ) -> ParseReport: ...


class HtmlJobParser:
    _tracked_fields = (
        "title",
        "company",
        "location",
        "description",
        "url",
        "posted_at_raw",
        "salary_raw",
    )
    _required_fields = ("title", "company", "url")

    def parse(
        self,
        html: bytes,
        config: SourceConfig,
        acquired_at: datetime,
    ) -> ParseReport:
        if config.selectors is None:
            raise ValueError(f"source {config.source_id} has no HTML selectors")
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(config.selectors.card)
        if not cards:
            raise ParserDriftError(
                f"source {config.source_id} produced no cards for {config.selectors.card!r}"
            )

        jobs = [self._parse_card(card, config, acquired_at) for card in cards]
        missing_rates = {
            field: sum(getattr(job, field) is None for job in jobs) / len(jobs)
            for field in self._tracked_fields
        }
        failed_required = [
            field
            for field in self._required_fields
            if missing_rates[field] > config.required_field_missing_threshold
        ]
        if failed_required:
            fields = ", ".join(failed_required)
            raise ParserDriftError(
                f"source {config.source_id} exceeded its required-field threshold: {fields}"
            )

        return ParseReport(
            source=config.source_id,
            cards_seen=len(cards),
            jobs=jobs,
            missing_rates=missing_rates,
        )

    def _parse_card(
        self,
        card: Tag,
        config: SourceConfig,
        acquired_at: datetime,
    ) -> RawJobPosting:
        selectors = config.selectors
        raw_url = self._attribute(card, selectors.url, "href")
        absolute_url = urljoin(str(config.base_url), raw_url) if raw_url else None
        source_job_id = card.get(selectors.source_id_attribute)
        if not isinstance(source_job_id, str) or not source_job_id.strip():
            identity = absolute_url or card.get_text(" ", strip=True)
            source_job_id = sha256(
                f"{config.source_id}:{identity}".encode()
            ).hexdigest()[:20]

        return RawJobPosting(
            source=config.source_id,
            source_job_id=source_job_id.strip(),
            title=self._text(card, selectors.title),
            company=self._text(card, selectors.company),
            location=self._text(card, selectors.location),
            description=self._text(card, selectors.description),
            url=absolute_url,
            posted_at_raw=self._text(card, selectors.posted_at),
            salary_raw=self._text(card, selectors.salary),
            acquired_at=acquired_at,
        )

    @staticmethod
    def _text(card: Tag, selector: str | None) -> str | None:
        if selector is None:
            return None
        element = card.select_one(selector)
        if element is None:
            return None
        value = element.get_text(" ", strip=True)
        return value or None

    @staticmethod
    def _attribute(card: Tag, selector: str, attribute: str) -> str | None:
        element = card.select_one(selector)
        if element is None:
            return None
        value = element.get(attribute)
        return value.strip() if isinstance(value, str) and value.strip() else None


class GreenhouseJobParser:
    _tracked_fields = (
        "title",
        "company",
        "location",
        "description",
        "url",
        "posted_at_raw",
        "salary_raw",
    )
    _required_fields = ("title", "company", "url")

    def parse(
        self,
        content: bytes,
        config: SourceConfig,
        acquired_at: datetime,
    ) -> ParseReport:
        try:
            payload = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ParserDriftError(
                f"source {config.source_id} returned invalid JSON"
            ) from error
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ParserDriftError(f"source {config.source_id} returned no jobs array")

        raw_jobs = payload["jobs"]
        jobs = [self._parse_job(raw_job, config, acquired_at) for raw_job in raw_jobs]
        missing_rates = {
            field: (sum(getattr(job, field) is None for job in jobs) / len(jobs) if jobs else 0.0)
            for field in self._tracked_fields
        }
        failed_required = [
            field
            for field in self._required_fields
            if missing_rates[field] > config.required_field_missing_threshold
        ]
        if failed_required:
            fields = ", ".join(failed_required)
            raise ParserDriftError(
                f"source {config.source_id} exceeded its required-field threshold: {fields}"
            )
        return ParseReport(
            source=config.source_id,
            cards_seen=len(jobs),
            jobs=jobs,
            missing_rates=missing_rates,
        )

    @staticmethod
    def _parse_job(
        raw_job: object,
        config: SourceConfig,
        acquired_at: datetime,
    ) -> RawJobPosting:
        if not isinstance(raw_job, dict):
            raise ParserDriftError(f"source {config.source_id} returned a non-object job")
        location = raw_job.get("location")
        location_name = location.get("name") if isinstance(location, dict) else None
        content = raw_job.get("content")
        description = None
        if isinstance(content, str) and content.strip():
            description = BeautifulSoup(content, "html.parser").get_text(" ", strip=True) or None
        job_id = raw_job.get("id")
        if job_id is None:
            raise ParserDriftError(f"source {config.source_id} returned a job without an ID")
        return RawJobPosting(
            source=config.source_id,
            source_job_id=str(job_id),
            title=GreenhouseJobParser._string(raw_job.get("title")),
            company=config.display_name,
            location=GreenhouseJobParser._string(location_name),
            description=description,
            url=GreenhouseJobParser._string(raw_job.get("absolute_url")),
            posted_at_raw=GreenhouseJobParser._string(raw_job.get("updated_at")),
            salary_raw=None,
            acquired_at=acquired_at,
        )

    @staticmethod
    def _string(value: object) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None
