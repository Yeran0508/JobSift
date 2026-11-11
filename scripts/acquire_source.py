import argparse
import json
from pathlib import Path

import httpx
from jobsift.acquisition.adapters import HttpSourceAdapter, RateLimiter
from jobsift.acquisition.models import SourceConfig
from jobsift.acquisition.service import AcquisitionService
from jobsift.acquisition.storage import RawSnapshotStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire one reviewed public job source")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    arguments = parser.parse_args()

    config = SourceConfig.model_validate_json(arguments.config.read_text())
    config.assert_collection_allowed()
    assert config.http is not None
    with httpx.Client(follow_redirects=False) as client:
        adapter = HttpSourceAdapter(
            config,
            client=client,
            rate_limiter=RateLimiter(config.compliance.max_requests_per_minute),
        )
        run = AcquisitionService(RawSnapshotStore(arguments.output)).collect(adapter)

    print(
        json.dumps(
            {
                "source": config.source_id,
                "snapshot_sha256": run.snapshot.content_sha256,
                "snapshot_created": run.snapshot.created,
                "jobs": len(run.report.jobs),
                "missing_rates": run.report.missing_rates,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
