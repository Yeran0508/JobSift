"""Build the complete local demo index from an approved synthetic HTML fixture."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from jobsift.config import Settings
from jobsift.demo import build_fixture_documents
from jobsift.search.gateway import ElasticsearchGateway
from jobsift.search.service import JobIndexService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("backend/tests/fixtures/example_jobs.html"),
    )
    parser.add_argument(
        "--source-config",
        type=Path,
        default=Path("config/sources/example-fixture.json"),
    )
    parser.add_argument("--skills", type=Path, default=Path("config/nlp/skills-v1.json"))
    parser.add_argument("--index", default=f"jobs-v1-demo-{datetime.now(UTC):%Y%m%d%H%M%S}")
    args = parser.parse_args()

    settings = Settings()
    documents = build_fixture_documents(
        args.fixture,
        args.source_config,
        args.skills,
        acquired_at=datetime.now(UTC),
    )
    with httpx.Client(
        base_url=str(settings.elasticsearch_url),
        timeout=settings.elasticsearch_timeout_seconds,
    ) as client:
        result = JobIndexService(
            ElasticsearchGateway(client), alias=settings.elasticsearch_alias
        ).rebuild(args.index, documents)
    print(json.dumps(result.model_dump(), sort_keys=True))


if __name__ == "__main__":
    main()
