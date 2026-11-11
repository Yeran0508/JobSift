from datetime import datetime
from hashlib import sha256

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator

from jobsift.processing.enrichment_models import EnrichedJobPosting


class SearchDocument(BaseModel):
    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source: str
    source_job_id: str
    content_fingerprint: str
    title: str
    company: str
    location: str | None = None
    description: str | None = None
    url: AnyHttpUrl
    posted_at: datetime | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    skills: list[str]
    organizations: list[str]
    entity_locations: list[str]
    acquired_at: datetime
    nlp_text_sha256: str
    nlp_model: str
    nlp_model_version: str
    skill_dictionary_version: str

    @classmethod
    def from_enriched(
        cls,
        job: EnrichedJobPosting,
        *,
        model_name: str,
        model_version: str,
        dictionary_version: str,
    ) -> "SearchDocument":
        clean = job.clean
        identity = f"{clean.source}\x00{clean.source_job_id}"
        return cls(
            document_id=sha256(identity.encode()).hexdigest(),
            source=clean.source,
            source_job_id=clean.source_job_id,
            content_fingerprint=clean.content_fingerprint,
            title=clean.title,
            company=clean.company,
            location=clean.location,
            description=clean.description,
            url=str(clean.url),
            posted_at=clean.posted_at,
            employment_type=clean.employment_type,
            salary_min=clean.salary_min,
            salary_max=clean.salary_max,
            salary_currency=clean.salary_currency,
            salary_period=clean.salary_period,
            skills=[skill.canonical for skill in job.skills],
            organizations=[entity.normalized for entity in job.organizations],
            entity_locations=[entity.normalized for entity in job.locations],
            acquired_at=clean.acquired_at,
            nlp_text_sha256=job.nlp_text_sha256,
            nlp_model=model_name,
            nlp_model_version=model_version,
            skill_dictionary_version=dictionary_version,
        )


class SearchCursor(BaseModel):
    values: list[str | int | float | None] = Field(min_length=2, max_length=3)


class JobSearchRequest(BaseModel):
    query: str | None = Field(default=None, max_length=300)
    locations: list[str] = Field(default_factory=list, max_length=20)
    skills: list[str] = Field(default_factory=list, max_length=20)
    sources: list[str] = Field(default_factory=list, max_length=20)
    posted_from: datetime | None = None
    posted_to: datetime | None = None
    size: int = Field(default=20, ge=1, le=100)
    cursor: SearchCursor | None = None

    @model_validator(mode="after")
    def validate_range_and_query(self) -> "JobSearchRequest":
        if self.posted_from and self.posted_to and self.posted_from > self.posted_to:
            raise ValueError("posted_from must not be after posted_to")
        if self.query is not None:
            self.query = self.query.strip() or None
        return self


class SearchHit(BaseModel):
    score: float | None
    sort: list[str | int | float | None]
    document: SearchDocument


class FacetBucket(BaseModel):
    key: str
    count: int = Field(ge=0)


class JobSearchResult(BaseModel):
    total: int = Field(ge=0)
    took_ms: int = Field(ge=0)
    hits: list[SearchHit]
    next_cursor: SearchCursor | None
    skill_facets: list[FacetBucket]
    location_facets: list[FacetBucket]
    is_partial: bool = False
    warnings: list[str] = Field(default_factory=list)


class IndexBuildResult(BaseModel):
    index_name: str
    documents_indexed: int = Field(ge=0)
    alias: str
    previous_indices: list[str]
    alias_switched: bool
