"""Reproducible synthetic-fixture pipeline used by the local M4 demo."""

from datetime import datetime
from pathlib import Path

from jobsift.acquisition.models import SourceConfig
from jobsift.acquisition.parser import HtmlJobParser
from jobsift.processing.cleaner import JobCleaner
from jobsift.processing.enricher import SpacyJobEnricher, load_skill_dictionary
from jobsift.search.models import SearchDocument


def build_fixture_documents(
    fixture_path: Path,
    source_config_path: Path,
    skill_dictionary_path: Path,
    *,
    acquired_at: datetime,
) -> list[SearchDocument]:
    config = SourceConfig.model_validate_json(source_config_path.read_text())
    parsed = HtmlJobParser().parse(fixture_path.read_bytes(), config, acquired_at)
    cleaned = JobCleaner().clean(parsed.jobs)
    dictionary = load_skill_dictionary(skill_dictionary_path)
    enriched = SpacyJobEnricher.from_model(dictionary).enrich(cleaned.jobs)
    return [
        SearchDocument.from_enriched(
            job,
            model_name=enriched.model_name,
            model_version=enriched.model_version,
            dictionary_version=enriched.dictionary_version,
        )
        for job in enriched.jobs
    ]
