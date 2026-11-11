from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class AcquisitionMethod(StrEnum):
    API = "api"
    HTTP = "http"
    SELENIUM = "selenium"
    FIXTURE = "fixture"


class ParserKind(StrEnum):
    HTML = "html"
    GREENHOUSE = "greenhouse"


class HttpPolicy(BaseModel):
    timeout_seconds: float = Field(default=15.0, gt=0.0, le=60.0)
    max_attempts: int = Field(default=3, ge=1, le=5)
    initial_backoff_seconds: float = Field(default=0.5, ge=0.0, le=10.0)
    max_backoff_seconds: float = Field(default=8.0, ge=0.0, le=60.0)
    user_agent: str = Field(min_length=1, max_length=200)


class CompliancePolicy(BaseModel):
    robots_txt_reviewed: bool = False
    terms_reviewed: bool = False
    public_jobs_only: bool = True
    collects_personal_data: bool = False
    max_requests_per_minute: int = Field(default=10, ge=1, le=120)
    attribution: str = Field(min_length=1)
    reviewed_on: date | None = None
    documentation_url: HttpUrl | None = None
    robots_url: HttpUrl | None = None
    terms_url: HttpUrl | None = None


class FieldSelectors(BaseModel):
    card: str
    title: str
    company: str
    url: str
    source_id_attribute: str = "data-job-id"
    location: str | None = None
    description: str | None = None
    posted_at: str | None = None
    salary: str | None = None


class SourceConfig(BaseModel):
    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    display_name: str
    base_url: HttpUrl
    enabled: bool = True
    method: AcquisitionMethod
    parser_kind: ParserKind = ParserKind.HTML
    parser_owner: str = Field(min_length=1)
    endpoint_url: HttpUrl | None = None
    selectors: FieldSelectors | None = None
    http: HttpPolicy | None = None
    compliance: CompliancePolicy
    required_field_missing_threshold: float = Field(default=0.0, ge=0.0, le=1.0)

    def assert_collection_allowed(self) -> None:
        if not self.enabled:
            raise ValueError(f"source {self.source_id} is disabled")
        if self.method is AcquisitionMethod.FIXTURE:
            return
        if not self.compliance.robots_txt_reviewed:
            raise ValueError(f"source {self.source_id} has no robots.txt review")
        if not self.compliance.terms_reviewed:
            raise ValueError(f"source {self.source_id} has no terms review")
        if not self.compliance.public_jobs_only:
            raise ValueError(f"source {self.source_id} is not limited to public jobs")
        if self.compliance.collects_personal_data:
            raise ValueError(f"source {self.source_id} would collect personal data")
        if self.compliance.reviewed_on is None:
            raise ValueError(f"source {self.source_id} has no compliance review date")
        if self.endpoint_url is None:
            raise ValueError(f"source {self.source_id} has no endpoint URL")
        if self.http is None:
            raise ValueError(f"source {self.source_id} has no HTTP policy")


class RawJobPosting(BaseModel):
    source: str
    source_job_id: str
    title: str | None
    company: str | None
    location: str | None
    description: str | None
    url: HttpUrl | None
    posted_at_raw: str | None
    salary_raw: str | None
    acquired_at: datetime


class ParseReport(BaseModel):
    source: str
    cards_seen: int
    jobs: list[RawJobPosting]
    missing_rates: dict[str, float]
