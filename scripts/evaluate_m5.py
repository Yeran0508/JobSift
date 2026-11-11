"""Run the versioned M5 relevance and local latency baseline on real Elasticsearch."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from time import perf_counter
from uuid import uuid4

import httpx
from jobsift.config import Settings
from jobsift.demo import build_fixture_documents
from jobsift.evaluation.metrics import evaluate_suite, percentile
from jobsift.evaluation.models import RelevanceSuite
from jobsift.search.gateway import ElasticsearchGateway
from jobsift.search.service import JobIndexService, JobSearchService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        type=Path,
        default=Path("config/evaluation/m5-relevance-v1.json"),
    )
    parser.add_argument("--warmups", type=int, default=5)
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--k", type=int, default=1)
    args = parser.parse_args()
    if args.warmups < 0 or args.repetitions < 1:
        parser.error("warmups must be non-negative and repetitions must be positive")

    settings = Settings()
    suite = RelevanceSuite.model_validate_json(args.suite.read_text())
    documents = build_fixture_documents(
        Path("backend/tests/fixtures/example_jobs.html"),
        Path("config/sources/example-fixture.json"),
        Path("config/nlp/skills-v1.json"),
        acquired_at=datetime(2026, 11, 11, 12, 0, tzinfo=UTC),
    )
    suffix = uuid4().hex[:10]
    index_name = f"jobs-v1-m5-eval-{suffix}"
    alias = f"jobs-m5-eval-{suffix}"

    with httpx.Client(
        base_url=str(settings.elasticsearch_url),
        timeout=settings.elasticsearch_timeout_seconds,
    ) as client:
        gateway = ElasticsearchGateway(client)
        search = JobSearchService(gateway, alias=alias)
        try:
            JobIndexService(gateway, alias=alias).rebuild(index_name, documents)
            retrieved = {
                case.case_id: [
                    hit.document.source_job_id for hit in search.search(case.request).hits
                ]
                for case in suite.cases
            }
            report = evaluate_suite(suite, retrieved, k=args.k)

            latency_request = suite.cases[0].request
            for _ in range(args.warmups):
                search.search(latency_request)
            latencies = []
            for _ in range(args.repetitions):
                started = perf_counter()
                search.search(latency_request)
                latencies.append((perf_counter() - started) * 1000)

            output = {
                "environment": {
                    "elasticsearch": "8.17.4",
                    "dataset": suite.dataset,
                    "documents": len(documents),
                    "warmups": args.warmups,
                    "repetitions": args.repetitions,
                },
                "retrieval": report.model_dump(mode="json"),
                "latency_ms": {
                    "min": min(latencies),
                    "mean": fmean(latencies),
                    "p50": percentile(latencies, 50),
                    "p95": percentile(latencies, 95),
                    "max": max(latencies),
                },
                "analyzer": {
                    "index_JS": gateway.analyze(index_name, "JS", analyzer="jobs_index"),
                    "search_JS": gateway.analyze(index_name, "JS", analyzer="jobs_search"),
                },
            }
            print(json.dumps(output, indent=2, sort_keys=True))
        finally:
            gateway.delete_index(index_name, ignore_missing=True)


if __name__ == "__main__":
    main()
