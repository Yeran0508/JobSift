import json
from datetime import UTC, datetime

from jobsift.acquisition.storage import RawSnapshotStore


def test_snapshot_store_is_content_addressed_and_idempotent(tmp_path) -> None:
    store = RawSnapshotStore(tmp_path)
    fetched_at = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    arguments = {
        "source_id": "example-fixture",
        "source_url": "https://jobs.example.test/",
        "content": b"<html>same content</html>",
        "content_type": "text/html",
        "fetched_at": fetched_at,
    }

    first = store.save(**arguments)
    second = store.save(**arguments)

    assert first.created is True
    assert second.created is False
    assert first.content_path == second.content_path
    assert first.content_path.read_bytes() == arguments["content"]
    metadata = json.loads(first.metadata_path.read_text())
    assert metadata["content_sha256"] == first.content_sha256
    assert metadata["fetched_at"] == fetched_at.isoformat()


def test_different_content_creates_a_new_immutable_snapshot(tmp_path) -> None:
    store = RawSnapshotStore(tmp_path)
    common = {
        "source_id": "example-fixture",
        "source_url": "https://jobs.example.test/",
        "content_type": "text/html",
        "fetched_at": datetime(2026, 11, 11, 12, 0, tzinfo=UTC),
    }

    first = store.save(content=b"first", **common)
    second = store.save(content=b"second", **common)

    assert first.content_path != second.content_path
    assert first.content_path.read_bytes() == b"first"
    assert second.content_path.read_bytes() == b"second"
