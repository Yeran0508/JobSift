import argparse
import json
from pathlib import Path

import httpx
from jobsift.acquisition.adapters import HttpSourceAdapter, RateLimiter
from jobsift.acquisition.audit import RunManifestStore, aggregate_source_metrics
from jobsift.acquisition.models import SourceConfig
from jobsift.acquisition.service import AcquisitionService
from jobsift.acquisition.storage import RawSnapshotStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire one reviewed public job source")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    parser.add_argument("--manifest-output", type=Path, default=Path("data/manifests"))
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
        manifest_store = RunManifestStore(arguments.manifest_output)
        run = AcquisitionService(
            RawSnapshotStore(arguments.output), manifest_store=manifest_store
        ).collect(adapter)
    metrics = aggregate_source_metrics(manifest_store.load_all())[config.source_id]

    print(
        json.dumps(
            {
                "source": config.source_id,
                "run_id": run.manifest.run_id,
                "manifest_path": str(run.stored_manifest.path) if run.stored_manifest else None,
                "snapshot_sha256": run.snapshot.content_sha256,
                "snapshot_created": run.snapshot.created,
                "jobs": len(run.report.jobs),
                "missing_rates": run.report.missing_rates,
                "fetch_stats": run.manifest.fetch_stats.model_dump(),
                "source_metrics": metrics.model_dump(),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
