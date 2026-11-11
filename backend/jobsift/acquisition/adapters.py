from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, HttpUrl

from jobsift.acquisition.models import AcquisitionMethod, SourceConfig


class FetchedPage(BaseModel):
    source_url: HttpUrl
    content: bytes
    content_type: str
    fetched_at: datetime


class SourceAdapter(Protocol):
    @property
    def config(self) -> SourceConfig: ...

    def fetch(self) -> FetchedPage: ...


class FixtureSourceAdapter:
    def __init__(self, config: SourceConfig, fixture_path: Path) -> None:
        if config.method is not AcquisitionMethod.FIXTURE:
            raise ValueError("FixtureSourceAdapter requires method=fixture")
        self._config = config
        self._fixture_path = fixture_path

    @property
    def config(self) -> SourceConfig:
        return self._config

    def fetch(self) -> FetchedPage:
        return FetchedPage(
            source_url=self._config.base_url,
            content=self._fixture_path.read_bytes(),
            content_type="text/html; charset=utf-8",
            fetched_at=datetime.now(UTC),
        )
