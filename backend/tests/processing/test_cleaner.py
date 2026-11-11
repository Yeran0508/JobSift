from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jobsift.acquisition.models import RawJobPosting, SourceConfig
from jobsift.acquisition.parser import HtmlJobParser
from jobsift.processing.cleaner import JobCleaner
from jobsift.processing.models import (
    CleaningPolicy,
    MissingValueStrategy,
    TransformationAction,
)

ACQUIRED_AT = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
REPOSITORY_ROOT = Path(__file__).parents[3]


def _raw(
    source_job_id: str,
    *,
    source: str = "source-a",
    title: str | None = "Backend Engineer",
    company: str | None = "Prairie Systems",
    location: str | None = "Chicago, il",
    description: str | None = "Build APIs.",
    url: str | None = None,
    posted_at_raw: str | None = "2026-11-10",
    salary_raw: str | None = "$100,000-$140,000 a year",
    acquired_at: datetime = ACQUIRED_AT,
) -> RawJobPosting:
    return RawJobPosting(
        source=source,
        source_job_id=source_job_id,
        title=title,
        company=company,
        location=location,
        description=description,
        url=url or f"https://jobs.example.test/{source_job_id}",
        posted_at_raw=posted_at_raw,
        salary_raw=salary_raw,
        acquired_at=acquired_at,
    )


def test_fixture_pipeline_normalizes_without_inventing_missing_salary() -> None:
    fixture_path = REPOSITORY_ROOT / "backend/tests/fixtures/example_jobs.html"
    config_path = REPOSITORY_ROOT / "config/sources/example-fixture.json"
    source_config = SourceConfig.model_validate_json(config_path.read_text())
    parsed = HtmlJobParser().parse(fixture_path.read_bytes(), source_config, ACQUIRED_AT)

    report = JobCleaner().clean(parsed.jobs)

    assert report.input_rows == 2
    assert report.output_rows == 2
    assert report.missingness_before["salary_raw"] == 0.5
    assert report.jobs[0].salary_min == 95_000
    assert report.jobs[0].salary_max == 120_000
    assert report.jobs[0].raw.salary_raw == "$95,000-$120,000"
    assert report.jobs[1].salary_min is None
    assert report.jobs[1].location == "Remote, US"
    assert report.jobs[0].posted_at == datetime(2026, 11, 10, tzinfo=UTC)
    salary_decision = next(item for item in report.decisions if item.field == "salary")
    assert salary_decision.strategy is MissingValueStrategy.NONE


def test_normalizes_unicode_whitespace_location_and_explicit_employment_type() -> None:
    raw = _raw(
        "unicode",
        title="  Ｆｕｌｌ－Ｔｉｍｅ   Engineer  ",
        company=" Prairie\ufffd   Systems ",
        location=None,
        description=" Ship   services ",
        posted_at_raw="not-a-date",
        salary_raw="USD 90k to 70k hourly",
    )

    job = JobCleaner().clean([raw]).jobs[0]

    assert job.title == "Full-Time Engineer"
    assert job.company == "Prairie Systems"
    assert job.location == "Unknown"
    assert job.description == "Ship services"
    assert job.posted_at is None
    assert job.employment_type == "Full-time"
    assert job.salary_min == 70_000
    assert job.salary_max == 90_000
    assert job.salary_currency == "USD"
    assert job.salary_period == "hour"
    actions = {(item.field, item.action) for item in job.transformations}
    assert ("title", TransformationAction.NORMALIZED) in actions
    assert ("location", TransformationAction.IMPUTED) in actions
    assert ("employment_type", TransformationAction.INFERRED) in actions


def test_drops_missing_identity_and_keeps_newest_stable_id() -> None:
    invalid = _raw("invalid", title="   ")
    old = _raw("same", description="old", acquired_at=ACQUIRED_AT)
    newest = _raw("same", description="new", acquired_at=ACQUIRED_AT + timedelta(hours=1))

    report = JobCleaner().clean([invalid, old, newest])

    assert [job.raw.description for job in report.jobs] == ["new"]
    assert report.output_rows == 1
    assert {item.source_job_id for item in report.dropped} == {"invalid", "same"}
    identity_decision = next(item for item in report.decisions if item.field == "title/company/url")
    assert identity_decision.missing_rate == 1 / 3
    duplicate = next(item for item in report.dropped if item.source_job_id == "same")
    assert duplicate.duplicate_of == "source-a:same"


def test_deduplicates_normalized_content_across_sources() -> None:
    first = _raw("one", source="source-a", acquired_at=ACQUIRED_AT)
    newest = _raw(
        "two",
        source="source-b",
        acquired_at=ACQUIRED_AT + timedelta(minutes=1),
        url="https://other.example.test/two",
    )

    report = JobCleaner().clean([first, newest])

    assert [(job.source, job.source_job_id) for job in report.jobs] == [("source-b", "two")]
    assert report.dropped[0].duplicate_of == "source-b:two"
    assert report.dropped[0].reason == "duplicate normalized content fingerprint"


def test_median_salary_imputation_requires_low_missingness_and_compatible_units() -> None:
    jobs = [
        _raw("one", salary_raw="$80,000-$100,000 per year", description="one"),
        _raw("two", salary_raw="$100,000-$120,000 per year", description="two"),
        _raw("three", salary_raw="$120,000-$140,000 per year", description="three"),
        _raw("missing", salary_raw=None, description="different content"),
    ]
    policy = CleaningPolicy(
        salary_strategy=MissingValueStrategy.MEDIAN,
        salary_median_max_missing_rate=0.25,
    )

    report = JobCleaner(policy).clean(jobs)
    imputed = next(job for job in report.jobs if job.source_job_id == "missing")

    assert imputed.salary_min == 100_000
    assert imputed.salary_max == 120_000
    assert imputed.salary_currency == "USD"
    assert imputed.salary_period == "year"
    assert report.missingness_after["salary_min"] == 0.0
    decision = next(item for item in report.decisions if item.field == "salary")
    assert decision.strategy is MissingValueStrategy.MEDIAN
    assert imputed.transformations[-1].action is TransformationAction.IMPUTED


def test_rejects_median_when_missingness_is_high_or_units_differ() -> None:
    policy = CleaningPolicy(
        salary_strategy=MissingValueStrategy.MEDIAN,
        salary_median_max_missing_rate=0.5,
    )
    high_missingness = JobCleaner(policy).clean(
        [
            _raw("observed", salary_raw="$50 per hour"),
            _raw("missing-1", salary_raw=None, description="one"),
            _raw("missing-2", salary_raw=None, description="two"),
        ]
    )
    mixed_units = JobCleaner(policy).clean(
        [
            _raw("hour", salary_raw="$50 per hour"),
            _raw("year", salary_raw="$100,000 per year", description="annual"),
            _raw("missing", salary_raw=None, description="missing"),
        ]
    )

    assert high_missingness.jobs[1].salary_min is None
    assert high_missingness.decisions[-1].strategy is MissingValueStrategy.NONE
    assert mixed_units.jobs[2].salary_min is None
    assert mixed_units.decisions[-1].strategy is MissingValueStrategy.NONE


@pytest.mark.parametrize(
    ("field", "strategy", "message"),
    [
        ("missing_marker", "   ", "missing marker"),
        ("location_strategy", MissingValueStrategy.MEDIAN, "location strategy"),
        ("employment_type_strategy", MissingValueStrategy.DROP_ROW, "employment type strategy"),
        ("salary_strategy", MissingValueStrategy.MARKER, "salary strategy"),
    ],
)
def test_cleaning_policy_rejects_incompatible_strategies(
    field: str,
    strategy: str | MissingValueStrategy,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CleaningPolicy(**{field: strategy})


def test_none_marker_policy_preserves_unknowns_and_empty_input_is_valid() -> None:
    policy = CleaningPolicy(
        location_strategy=MissingValueStrategy.NONE,
        employment_type_strategy=MissingValueStrategy.NONE,
    )
    report = JobCleaner(policy).clean(
        [
            _raw(
                "unknowns",
                location=None,
                description=None,
                posted_at_raw=None,
                salary_raw="Competitive",
            )
        ]
    )
    empty = JobCleaner().clean([])

    assert report.jobs[0].location is None
    assert report.jobs[0].employment_type is None
    assert report.jobs[0].salary_min is None
    assert report.missingness_after["description"] == 1.0
    assert empty.input_rows == 0
    assert empty.output_rows == 0
    assert empty.jobs == []
    assert all(value == 0.0 for value in empty.missingness_before.values())
