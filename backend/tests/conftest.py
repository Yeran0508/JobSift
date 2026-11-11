from datetime import UTC, datetime

import pytest
from jobsift.search.models import SearchDocument


@pytest.fixture
def search_document_factory():
    def factory(
        source_job_id: str = "job-1",
        *,
        title: str = "Backend Engineer",
        location: str | None = "Chicago, IL",
        description: str | None = "Build Python search services.",
        skills: list[str] | None = None,
        posted_at: datetime | None = datetime(2026, 11, 10, tzinfo=UTC),
    ) -> SearchDocument:
        suffix = source_job_id.encode().hex().ljust(64, "0")[:64]
        return SearchDocument(
            document_id=suffix,
            source="example-fixture",
            source_job_id=source_job_id,
            content_fingerprint="a" * 64,
            title=title,
            company="Prairie Systems",
            location=location,
            description=description,
            url=f"https://jobs.example.test/{source_job_id}",
            posted_at=posted_at,
            employment_type="Full-time",
            salary_min=100_000,
            salary_max=140_000,
            salary_currency="USD",
            salary_period="year",
            skills=skills or ["Python", "Docker"],
            organizations=["prairie systems"],
            entity_locations=["chicago"],
            acquired_at=datetime(2026, 11, 11, 12, 0, tzinfo=UTC),
            nlp_text_sha256="b" * 64,
            nlp_model="core_web_sm",
            nlp_model_version="3.8.0",
            skill_dictionary_version="skills-v1",
        )

    return factory
