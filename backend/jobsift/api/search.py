import base64
import binascii
import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import AnyHttpUrl, BaseModel, Field, ValidationError

from jobsift.search.gateway import ElasticsearchRequestError
from jobsift.search.models import (
    FacetBucket,
    JobSearchRequest,
    JobSearchResult,
    SearchCursor,
    SearchDocument,
)
from jobsift.search.service import JobSearchService

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobSummary(BaseModel):
    id: str
    title: str
    company: str
    location: str | None
    description: str | None
    url: AnyHttpUrl
    posted_at: datetime | None
    employment_type: str | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    salary_period: str | None
    skills: list[str]
    source: str
    acquired_at: datetime

    @classmethod
    def from_document(cls, document: SearchDocument) -> "JobSummary":
        return cls(
            id=document.document_id,
            title=document.title,
            company=document.company,
            location=document.location,
            description=document.description,
            url=document.url,
            posted_at=document.posted_at,
            employment_type=document.employment_type,
            salary_min=document.salary_min,
            salary_max=document.salary_max,
            salary_currency=document.salary_currency,
            salary_period=document.salary_period,
            skills=document.skills,
            source=document.source,
            acquired_at=document.acquired_at,
        )


class SearchMeta(BaseModel):
    took_ms: int = Field(ge=0)
    is_partial: bool
    warnings: list[str]


class JobSearchResponse(BaseModel):
    total: int = Field(ge=0)
    results: list[JobSummary]
    facets: dict[str, list[FacetBucket]]
    next_cursor: str | None
    meta: SearchMeta


class ApiProblem(BaseModel):
    code: str
    message: str
    retryable: bool


class ApiProblemEnvelope(BaseModel):
    detail: ApiProblem


def get_search_service(request: Request) -> JobSearchService:
    return request.app.state.search_service


def encode_cursor(cursor: SearchCursor | None) -> str | None:
    if cursor is None:
        return None
    payload = json.dumps(cursor.values, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(value: str | None) -> SearchCursor | None:
    if value is None:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        decoded = base64.b64decode(value + padding, altchars=b"-_", validate=True)
        raw_values = json.loads(decoded)
        return SearchCursor(values=raw_values)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_cursor",
                "message": "cursor is malformed or does not match the search sort",
                "retryable": False,
            },
        ) from None


def _request(
    q: Annotated[str | None, Query(max_length=300)] = None,
    location: Annotated[list[str] | None, Query(max_length=20)] = None,
    skill: Annotated[list[str] | None, Query(max_length=20)] = None,
    source: Annotated[list[str] | None, Query(max_length=20)] = None,
    posted_from: datetime | None = None,
    posted_to: datetime | None = None,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(max_length=2048)] = None,
) -> JobSearchRequest:
    try:
        return JobSearchRequest(
            query=q,
            locations=location or [],
            skills=skill or [],
            sources=source or [],
            posted_from=posted_from,
            posted_to=posted_to,
            size=size,
            cursor=decode_cursor(cursor),
        )
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_search",
                "message": str(error.errors()[0]["msg"]),
                "retryable": False,
            },
        ) from None


@router.get(
    "",
    response_model=JobSearchResponse,
    responses={
        422: {"model": ApiProblemEnvelope},
        503: {"model": ApiProblemEnvelope},
    },
)
def search_jobs(
    search_request: Annotated[JobSearchRequest, Depends(_request)],
    service: Annotated[JobSearchService, Depends(get_search_service)],
) -> JobSearchResponse:
    """Search the current immutable index view with validated filters and an opaque cursor."""

    try:
        result = service.search(search_request)
    except ElasticsearchRequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "search_unavailable",
                "message": "Job search is temporarily unavailable. Please retry shortly.",
                "retryable": True,
            },
        ) from None
    return _response(result)


def _response(result: JobSearchResult) -> JobSearchResponse:
    return JobSearchResponse(
        total=result.total,
        results=[JobSummary.from_document(hit.document) for hit in result.hits],
        facets={"skills": result.skill_facets, "locations": result.location_facets},
        next_cursor=encode_cursor(result.next_cursor),
        meta=SearchMeta(
            took_ms=result.took_ms,
            is_partial=result.is_partial,
            warnings=result.warnings,
        ),
    )
