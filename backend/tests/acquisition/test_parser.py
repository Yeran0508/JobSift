from datetime import UTC, datetime

import pytest
from jobsift.acquisition.models import SourceConfig
from jobsift.acquisition.parser import HtmlJobParser, ParserDriftError

ACQUIRED_AT = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def test_parser_extracts_configured_fields_and_stable_ids(
    fixture_path,
    source_config: SourceConfig,
) -> None:
    report = HtmlJobParser().parse(fixture_path.read_bytes(), source_config, ACQUIRED_AT)

    assert report.cards_seen == 2
    assert [job.title for job in report.jobs] == ["Backend Engineer", "Software Engineer I"]
    assert report.jobs[0].source_job_id == "eng-101"
    assert len(report.jobs[1].source_job_id) == 20
    assert str(report.jobs[1].url) == "https://jobs.example.test/jobs/eng-102"
    assert report.missing_rates["salary_raw"] == 0.5
    assert report.missing_rates["title"] == 0.0


def test_parser_rejects_missing_job_cards(source_config: SourceConfig) -> None:
    with pytest.raises(ParserDriftError, match="produced no cards"):
        HtmlJobParser().parse(b"<html></html>", source_config, ACQUIRED_AT)


def test_parser_rejects_required_field_drift(source_config: SourceConfig) -> None:
    html = b"""
        <article class="job-card" data-job-id="broken-1">
          <p class="company">Example</p>
          <a class="job-link" href="/jobs/broken-1">View</a>
        </article>
    """

    with pytest.raises(ParserDriftError, match="required-field threshold: title"):
        HtmlJobParser().parse(html, source_config, ACQUIRED_AT)


def test_parser_rejects_missing_required_link(source_config: SourceConfig) -> None:
    html = b"""
        <article class="job-card" data-job-id="broken-2">
          <h2 class="job-title">Engineer</h2>
          <p class="company">Example</p>
        </article>
    """

    with pytest.raises(ParserDriftError, match="required-field threshold: url"):
        HtmlJobParser().parse(html, source_config, ACQUIRED_AT)


def test_parser_tracks_optional_selector_absence(source_config: SourceConfig) -> None:
    selectors = source_config.selectors.model_copy(update={"location": None})
    config = source_config.model_copy(update={"selectors": selectors})
    html = b"""
        <article class="job-card" data-job-id="eng-1">
          <h2 class="job-title">Engineer</h2>
          <p class="company">Example</p>
          <a class="job-link" href="/jobs/eng-1">View</a>
        </article>
    """

    report = HtmlJobParser().parse(html, config, ACQUIRED_AT)

    assert report.jobs[0].location is None
    assert report.missing_rates["location"] == 1.0
