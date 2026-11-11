import json
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from pydantic import HttpUrl


@dataclass(frozen=True)
class StoredSnapshot:
    content_sha256: str
    content_path: Path
    metadata_path: Path
    created: bool


class RawSnapshotStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def save(
        self,
        *,
        source_id: str,
        source_url: HttpUrl,
        content: bytes,
        content_type: str,
        fetched_at: datetime,
    ) -> StoredSnapshot:
        digest = sha256(content).hexdigest()
        source_directory = self._root / source_id
        source_directory.mkdir(parents=True, exist_ok=True)
        extension = ".json" if "application/json" in content_type.lower() else ".html"
        content_path = source_directory / f"{digest}{extension}"
        metadata_path = source_directory / f"{digest}.metadata.json"

        created = self._write_once(content_path, content)
        metadata = {
            "source_id": source_id,
            "source_url": str(source_url),
            "content_type": content_type,
            "content_sha256": digest,
            "fetched_at": fetched_at.isoformat(),
        }
        self._write_once(
            metadata_path,
            json.dumps(metadata, indent=2, sort_keys=True).encode(),
        )
        return StoredSnapshot(
            content_sha256=digest,
            content_path=content_path,
            metadata_path=metadata_path,
            created=created,
        )

    @staticmethod
    def _write_once(path: Path, content: bytes) -> bool:
        try:
            with path.open("xb") as stream:
                stream.write(content)
        except FileExistsError:
            return False
        return True
