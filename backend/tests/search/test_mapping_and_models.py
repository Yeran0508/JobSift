from datetime import UTC, datetime

import pytest
from jobsift.acquisition.models import RawJobPosting
from jobsift.processing.enrichment_models import (
    EnrichedJobPosting,
    EntityKind,
    ExtractedEntity,
    SkillMatch,
)
from jobsift.processing.models import CleanJobPosting
from jobsift.search.mapping import job_index_definition
from jobsift.search.models import JobSearchRequest, SearchDocument


def test_mapping_is_strict_and_separates_text_from_keyword() -> None:
    definition = job_index_definition()
    mappings = definition["mappings"]
    properties = mappings["properties"]

    assert mappings["dynamic"] == "strict"
    assert properties["description"]["type"] == "text"
    assert properties["title"]["fields"]["keyword"]["type"] == "keyword"
    assert properties["skills"]["type"] == "keyword"
    assert properties["posted_at"]["type"] == "date"
    analyzers = definition["settings"]["analysis"]["analyzer"]
    assert analyzers["jobs_index"]["tokenizer"] == "standard"
    assert "jobs_tech_synonyms" in analyzers["jobs_search"]["filter"]


def test_search_document_preserves_enrichment_provenance() -> None:
    acquired_at = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    raw = RawJobPosting(
        source="source-a",
        source_job_id="job-1",
        title="Backend Engineer",
        company="Prairie Systems",
        location="Chicago, IL",
        description="Build Python services.",
        url="https://jobs.example.test/job-1",
        posted_at_raw="2026-11-10",
        salary_raw=None,
        acquired_at=acquired_at,
    )
    clean = CleanJobPosting(
        source="source-a",
        source_job_id="job-1",
        title="Backend Engineer",
        company="Prairie Systems",
        location="Chicago, IL",
        description="Build Python services.",
        url=raw.url,
        posted_at=datetime(2026, 11, 10, tzinfo=UTC),
        employment_type="Full-time",
        acquired_at=acquired_at,
        content_fingerprint="a" * 64,
        transformations=[],
        raw=raw,
    )
    enriched = EnrichedJobPosting(
        clean=clean,
        nlp_text_sha256="b" * 64,
        organizations=[
            ExtractedEntity(
                text="Prairie Systems",
                normalized="prairie systems",
                kind=EntityKind.ORGANIZATION,
                spacy_label="ORG",
                start_char=0,
                end_char=15,
            )
        ],
        locations=[],
        skills=[
            SkillMatch(
                canonical="Python",
                matched_text="Python",
                start_char=20,
                end_char=26,
                dictionary_version="skills-v1",
            )
        ],
    )

    document = SearchDocument.from_enriched(
        enriched,
        model_name="core_web_sm",
        model_version="3.8.0",
        dictionary_version="skills-v1",
    )

    assert len(document.document_id) == 64
    assert document.skills == ["Python"]
    assert document.organizations == ["prairie systems"]
    assert document.nlp_model_version == "3.8.0"
    assert document.skill_dictionary_version == "skills-v1"


def test_search_request_normalizes_blank_query_and_validates_date_range() -> None:
    request = JobSearchRequest(query="   ")

    assert request.query is None
    with pytest.raises(ValueError, match="posted_from"):
        JobSearchRequest(
            posted_from=datetime(2026, 11, 11, tzinfo=UTC),
            posted_to=datetime(2026, 11, 10, tzinfo=UTC),
        )


def test_search_document_accepts_optional_fields_omitted_from_sparse_source(
    search_document_factory,
) -> None:
    sparse_source = search_document_factory().model_dump()
    for field in (
        "location",
        "description",
        "posted_at",
        "employment_type",
        "salary_min",
        "salary_max",
        "salary_currency",
        "salary_period",
    ):
        sparse_source.pop(field)

    restored = SearchDocument.model_validate(sparse_source)

    assert restored.location is None
    assert restored.salary_min is None
