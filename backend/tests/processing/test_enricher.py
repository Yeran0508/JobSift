from datetime import UTC, datetime
from pathlib import Path

import pytest
import spacy
from jobsift.acquisition.models import RawJobPosting
from jobsift.processing.cleaner import JobCleaner
from jobsift.processing.enricher import SpacyJobEnricher, load_skill_dictionary
from jobsift.processing.enrichment_models import (
    EntityKind,
    SkillDictionary,
)

REPOSITORY_ROOT = Path(__file__).parents[3]
ACQUIRED_AT = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def _dictionary() -> SkillDictionary:
    return SkillDictionary.model_validate(
        {
            "version": "test-v1",
            "entries": [
                {"canonical": "Python", "aliases": []},
                {"canonical": "JavaScript", "aliases": ["JS"]},
                {"canonical": "Docker", "aliases": []},
            ],
        }
    )


def _pipeline():
    nlp = spacy.blank("en")
    nlp.meta["name"] = "deterministic-test-pipeline"
    nlp.meta["version"] = "1.0.0"
    ruler = nlp.add_pipe("entity_ruler")
    ruler.add_patterns(
        [
            {"label": "ORG", "pattern": "Prairie Systems"},
            {"label": "GPE", "pattern": "Chicago"},
            {"label": "LOC", "pattern": "Lake Michigan"},
            {"label": "PERSON", "pattern": "Ada Lovelace"},
        ]
    )
    return nlp


def _clean_job(
    source_job_id: str = "job-1",
    *,
    description: str | None = (
        "Build Python and JS services with Docker for Prairie Systems in Chicago. "
        "Work near Lake Michigan. Python mentors include Ada Lovelace."
    ),
):
    raw = RawJobPosting(
        source="example",
        source_job_id=source_job_id,
        title="Backend Engineer",
        company="Prairie Systems",
        location="Chicago, IL",
        description=description,
        url=f"https://jobs.example.test/{source_job_id}",
        posted_at_raw="2026-11-11",
        salary_raw=None,
        acquired_at=ACQUIRED_AT,
    )
    return JobCleaner().clean([raw]).jobs[0]


def test_enricher_extracts_model_entities_and_dictionary_skills() -> None:
    report = SpacyJobEnricher(_pipeline(), _dictionary(), batch_size=2).enrich([_clean_job()])
    enriched = report.jobs[0]

    assert report.input_rows == 1
    assert report.output_rows == 1
    assert report.model_name == "deterministic-test-pipeline"
    assert report.model_version == "1.0.0"
    assert report.dictionary_version == "test-v1"
    assert len(report.dictionary_sha256) == 64
    assert [(entity.text, entity.kind) for entity in enriched.organizations] == [
        ("Prairie Systems", EntityKind.ORGANIZATION)
    ]
    assert [entity.text for entity in enriched.locations] == ["Chicago", "Lake Michigan"]
    assert [skill.canonical for skill in enriched.skills] == [
        "Python",
        "JavaScript",
        "Docker",
    ]
    assert enriched.skills[1].matched_text == "JS"
    assert report.organizations_total == 1
    assert report.locations_total == 2
    assert report.skills_total == 3
    assert len(enriched.nlp_text_sha256) == 64


def test_enricher_deduplicates_repeated_entities_and_skills() -> None:
    description = "Prairie Systems uses Python. Prairie Systems also teaches python and PYTHON."

    enriched = SpacyJobEnricher(_pipeline(), _dictionary()).enrich(
        [_clean_job(description=description)]
    ).jobs[0]

    assert [entity.normalized for entity in enriched.organizations] == ["prairie systems"]
    assert [skill.canonical for skill in enriched.skills] == ["Python"]
    assert enriched.skills[0].matched_text == "Python"


def test_enricher_handles_empty_jobs_and_missing_optional_text() -> None:
    enricher = SpacyJobEnricher(_pipeline(), _dictionary())

    empty = enricher.enrich([])
    missing_description = enricher.enrich([_clean_job(description=None)])

    assert empty.input_rows == 0
    assert empty.jobs == []
    assert empty.skills_total == 0
    assert missing_description.output_rows == 1
    assert missing_description.jobs[0].skills == []


def test_enricher_requires_entity_pipeline_and_positive_batch_size() -> None:
    blank = spacy.blank("en")

    with pytest.raises(ValueError, match="ner or entity_ruler"):
        SpacyJobEnricher(blank, _dictionary())
    with pytest.raises(ValueError, match="batch_size"):
        SpacyJobEnricher(_pipeline(), _dictionary(), batch_size=0)


def test_dictionary_loader_and_validation() -> None:
    path = REPOSITORY_ROOT / "config/nlp/skills-v1.json"

    dictionary = load_skill_dictionary(path)

    assert dictionary.version == "skills-v1-2026-11-11"
    assert any(entry.canonical == "Elasticsearch" for entry in dictionary.entries)
    aliases = {entry.canonical: entry.aliases for entry in dictionary.entries}
    assert "Node" not in aliases["Node.js"]
    assert "Spark" not in aliases["Apache Spark"]
    with pytest.raises(ValueError, match="visible character"):
        SkillDictionary.model_validate(
            {"version": "bad", "entries": [{"canonical": "Python", "aliases": ["  "]}]}
        )
    with pytest.raises(ValueError, match="is shared"):
        SkillDictionary.model_validate(
            {
                "version": "bad",
                "entries": [
                    {"canonical": "JavaScript", "aliases": ["JS"]},
                    {"canonical": "Other", "aliases": ["js"]},
                ],
            }
        )


def test_from_model_loads_the_pinned_pretrained_pipeline() -> None:
    enricher = SpacyJobEnricher.from_model(_dictionary())

    report = enricher.enrich([_clean_job(description="Build Python services in Chicago.")])

    assert report.model_name == "core_web_sm"
    assert report.model_version == "3.8.0"
    assert report.jobs[0].skills[0].canonical == "Python"
