from datetime import UTC, datetime
from pathlib import Path

from jobsift.demo import build_fixture_documents

REPOSITORY_ROOT = Path(__file__).parents[2]


def test_fixture_flows_through_parse_clean_enrich_and_search_document() -> None:
    documents = build_fixture_documents(
        REPOSITORY_ROOT / "backend/tests/fixtures/example_jobs.html",
        REPOSITORY_ROOT / "config/sources/example-fixture.json",
        REPOSITORY_ROOT / "config/nlp/skills-v1.json",
        acquired_at=datetime(2026, 11, 11, tzinfo=UTC),
    )

    assert len(documents) == 2
    assert documents[0].title == "Backend Engineer"
    assert "Python" in documents[0].skills
    assert documents[1].location == "Remote, US"
