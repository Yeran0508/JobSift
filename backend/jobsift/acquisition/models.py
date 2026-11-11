from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class AcquisitionMethod(StrEnum):
    API = "api"
    HTTP = "http"
    SELENIUM = "selenium"
    FIXTURE = "fixture"


class CompliancePolicy(BaseModel):
    robots_txt_reviewed: bool = False
    terms_reviewed: bool = False
    public_jobs_only: bool = True
    collects_personal_data: bool = False
    max_requests_per_minute: int = Field(default=10, ge=1, le=120)
    attribution: str


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
    parser_owner: str
    selectors: FieldSelectors
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
