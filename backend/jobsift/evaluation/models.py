from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from jobsift.search.models import JobSearchRequest


class RelevanceCase(BaseModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    request: JobSearchRequest
    relevance: dict[str, int]
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_relevance(self) -> "RelevanceCase":
        if not self.relevance:
            raise ValueError("a relevance case must contain at least one judgment")
        if any(grade < 0 or grade > 3 for grade in self.relevance.values()):
            raise ValueError("relevance grades must be between zero and three")
        return self


class RelevanceSuite(BaseModel):
    version: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    judged_at: datetime
    grade_scale: dict[int, str]
    cases: list[RelevanceCase] = Field(min_length=1)


class CaseMetrics(BaseModel):
    case_id: str
    retrieved: list[str]
    precision_at_k: float = Field(ge=0.0, le=1.0)
    ndcg_at_k: float = Field(ge=0.0, le=1.0)


class EvaluationReport(BaseModel):
    suite_version: str
    dataset: str
    k: int = Field(ge=1)
    cases: list[CaseMetrics]
    mean_precision_at_k: float = Field(ge=0.0, le=1.0)
    mean_ndcg_at_k: float = Field(ge=0.0, le=1.0)


class PipelineMetricSnapshot(BaseModel):
    measured_at: datetime
    runs_total: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    missing_rates: dict[str, float]
    duplicates_removed: int = Field(ge=0)
    indexed_documents: int = Field(ge=0)
    freshness_seconds: float | None = Field(default=None, ge=0.0)
    latency_samples: int = Field(ge=0)
    latency_p50_ms: float | None = Field(default=None, ge=0.0)
    latency_p95_ms: float | None = Field(default=None, ge=0.0)
