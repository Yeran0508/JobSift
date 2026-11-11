from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, model_validator

from jobsift.acquisition.models import RawJobPosting


class MissingValueStrategy(StrEnum):
    DROP_ROW = "drop_row"
    MARKER = "marker"
    MEDIAN = "median"
    NONE = "none"


class TransformationAction(StrEnum):
    NORMALIZED = "normalized"
    PARSED = "parsed"
    INFERRED = "inferred"
    IMPUTED = "imputed"


class CleaningPolicy(BaseModel):
    location_strategy: MissingValueStrategy = MissingValueStrategy.MARKER
    employment_type_strategy: MissingValueStrategy = MissingValueStrategy.MARKER
    salary_strategy: MissingValueStrategy = MissingValueStrategy.NONE
    salary_median_max_missing_rate: float = Field(default=0.2, ge=0.0, le=1.0)
    missing_marker: str = Field(default="Unknown", min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_field_strategies(self) -> "CleaningPolicy":
        if not self.missing_marker.strip():
            raise ValueError("missing marker must contain a visible character")
        marker_or_none = {MissingValueStrategy.MARKER, MissingValueStrategy.NONE}
        if self.location_strategy not in marker_or_none:
            raise ValueError("location strategy must be marker or none")
        if self.employment_type_strategy not in marker_or_none:
            raise ValueError("employment type strategy must be marker or none")
        if self.salary_strategy not in {
            MissingValueStrategy.MEDIAN,
            MissingValueStrategy.NONE,
        }:
            raise ValueError("salary strategy must be median or none")
        return self


class TransformationRecord(BaseModel):
    field: str
    action: TransformationAction
    reason: str


class MissingnessDecision(BaseModel):
    field: str
    missing_rate: float = Field(ge=0.0, le=1.0)
    strategy: MissingValueStrategy
    reason: str


class DroppedJob(BaseModel):
    source: str
    source_job_id: str
    reason: str
    duplicate_of: str | None = None


class CleanJobPosting(BaseModel):
    source: str
    source_job_id: str
    title: str
    company: str
    location: str | None
    description: str | None
    url: HttpUrl
    posted_at: datetime | None
    employment_type: str | None
    salary_min: float | None = Field(default=None, ge=0.0)
    salary_max: float | None = Field(default=None, ge=0.0)
    salary_currency: str | None = None
    salary_period: str | None = None
    acquired_at: datetime
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    transformations: list[TransformationRecord]
    raw: RawJobPosting


class CleaningReport(BaseModel):
    input_rows: int = Field(ge=0)
    output_rows: int = Field(ge=0)
    missingness_before: dict[str, float]
    missingness_after: dict[str, float]
    decisions: list[MissingnessDecision]
    dropped: list[DroppedJob]
    jobs: list[CleanJobPosting]
