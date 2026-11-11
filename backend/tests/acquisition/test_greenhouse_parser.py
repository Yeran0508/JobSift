from datetime import UTC, datetime

import pytest
from jobsift.acquisition.models import SourceConfig
from jobsift.acquisition.parser import GreenhouseJobParser, ParserDriftError

ACQUIRED_AT = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def test_greenhouse_parser_maps_public_job_fields(
    greenhouse_fixture_path,
    greenhouse_config: SourceConfig,
) -> None:
    report = GreenhouseJobParser().parse(
        greenhouse_fixture_path.read_bytes(), greenhouse_config, ACQUIRED_AT
    )

    assert report.cards_seen == 2
    assert report.jobs[0].source_job_id == "101"
    assert report.jobs[0].company == "Anthropic"
    assert report.jobs[0].description == "Build Python services."
    assert report.jobs[1].description is None
    assert report.jobs[1].location == "Remote - US"
    assert report.missing_rates["description"] == 0.5
    assert report.missing_rates["salary_raw"] == 1.0


@pytest.mark.parametrize("content", [b"not-json", b"[]", b'{"meta": {}}'])
def test_greenhouse_parser_rejects_malformed_payloads(
    content: bytes,
    greenhouse_config: SourceConfig,
) -> None:
    with pytest.raises(ParserDriftError):
        GreenhouseJobParser().parse(content, greenhouse_config, ACQUIRED_AT)


def test_greenhouse_parser_accepts_a_valid_empty_board(
    greenhouse_config: SourceConfig,
) -> None:
    report = GreenhouseJobParser().parse(
        b'{"jobs": [], "meta": {"total": 0}}', greenhouse_config, ACQUIRED_AT
    )

    assert report.cards_seen == 0
    assert report.jobs == []
    assert set(report.missing_rates.values()) == {0.0}


def test_greenhouse_parser_rejects_non_object_and_missing_required_fields(
    greenhouse_config: SourceConfig,
) -> None:
    with pytest.raises(ParserDriftError, match="non-object job"):
        GreenhouseJobParser().parse(b'{"jobs": [1]}', greenhouse_config, ACQUIRED_AT)

    broken = b'{"jobs": [{"id": 1, "title": "Engineer"}]}'
    with pytest.raises(ParserDriftError, match="required-field threshold: url"):
        GreenhouseJobParser().parse(broken, greenhouse_config, ACQUIRED_AT)

    missing_id = b'{"jobs": [{"title": "Engineer", "absolute_url": "https://example.test"}]}'
    with pytest.raises(ParserDriftError, match="job without an ID"):
        GreenhouseJobParser().parse(missing_id, greenhouse_config, ACQUIRED_AT)
