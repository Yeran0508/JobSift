from collections.abc import Mapping
from dataclasses import dataclass, field

from jobsift.acquisition.adapters import SourceAdapter
from jobsift.acquisition.models import ParseReport, ParserKind
from jobsift.acquisition.parser import GreenhouseJobParser, HtmlJobParser, JobContentParser
from jobsift.acquisition.storage import RawSnapshotStore, StoredSnapshot


@dataclass(frozen=True)
class AcquisitionRun:
    snapshot: StoredSnapshot
    report: ParseReport


@dataclass
class BatchAcquisitionResult:
    successes: dict[str, AcquisitionRun] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)


class AcquisitionService:
    def __init__(
        self,
        snapshot_store: RawSnapshotStore,
        parsers: Mapping[ParserKind, JobContentParser] | None = None,
    ) -> None:
        self._snapshot_store = snapshot_store
        self._parsers = (
            parsers
            if parsers is not None
            else {
                ParserKind.HTML: HtmlJobParser(),
                ParserKind.GREENHOUSE: GreenhouseJobParser(),
            }
        )

    def collect(self, adapter: SourceAdapter) -> AcquisitionRun:
        adapter.config.assert_collection_allowed()
        page = adapter.fetch()
        snapshot = self._snapshot_store.save(
            source_id=adapter.config.source_id,
            source_url=page.source_url,
            content=page.content,
            content_type=page.content_type,
            fetched_at=page.fetched_at,
        )
        parser = self._parsers.get(adapter.config.parser_kind)
        if parser is None:
            raise ValueError(f"no parser registered for {adapter.config.parser_kind}")
        report = parser.parse(page.content, adapter.config, page.fetched_at)
        return AcquisitionRun(snapshot=snapshot, report=report)

    def collect_many(self, adapters: list[SourceAdapter]) -> BatchAcquisitionResult:
        result = BatchAcquisitionResult()
        for adapter in adapters:
            try:
                result.successes[adapter.config.source_id] = self.collect(adapter)
            except Exception as error:
                result.failures[adapter.config.source_id] = f"{type(error).__name__}: {error}"
        return result
