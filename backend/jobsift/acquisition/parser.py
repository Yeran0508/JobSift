from datetime import datetime
from hashlib import sha256
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from jobsift.acquisition.models import ParseReport, RawJobPosting, SourceConfig


class ParserDriftError(ValueError):
    """Raised when configured selectors no longer produce trustworthy records."""


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
