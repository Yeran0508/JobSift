import re
import unicodedata
from hashlib import sha256

import pandas as pd

from jobsift.acquisition.models import RawJobPosting
from jobsift.processing.models import (
    CleaningPolicy,
    CleaningReport,
    CleanJobPosting,
    DroppedJob,
    MissingnessDecision,
    MissingValueStrategy,
    TransformationAction,
    TransformationRecord,
)

_RAW_MISSING_FIELDS = (
    "title",
    "company",
    "location",
    "description",
    "url",
    "posted_at_raw",
    "salary_raw",
)
_CLEAN_MISSING_FIELDS = (
    "location",
    "description",
    "posted_at",
    "employment_type",
    "salary_min",
    "salary_max",
)
_SALARY_NUMBER = re.compile(r"(?<!\d)(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*([kK])?")


class JobCleaner:
    def __init__(self, policy: CleaningPolicy | None = None) -> None:
        self._policy = policy or CleaningPolicy()

    def clean(self, raw_jobs: list[RawJobPosting]) -> CleaningReport:
        frame = self._frame(raw_jobs)
        missingness_before = self._missingness(frame, _RAW_MISSING_FIELDS)
        identity_missing_rate = self._identity_missingness(frame)
        dropped: list[DroppedJob] = []
        frame = self._drop_invalid_identity(frame, dropped)
        frame = self._deduplicate_stable_ids(frame, dropped)

        clean_jobs = [self._normalize_job(row["raw"]) for _, row in frame.iterrows()]
        clean_jobs = self._deduplicate_fingerprints(clean_jobs, dropped)
        clean_jobs, salary_decision = self._apply_salary_policy(clean_jobs)
        missingness_after = self._clean_missingness(clean_jobs)

        decisions = [
            MissingnessDecision(
                field="title/company/url",
                missing_rate=identity_missing_rate,
                strategy=MissingValueStrategy.DROP_ROW,
                reason="identity fields cannot be safely inferred",
            ),
            MissingnessDecision(
                field="location",
                missing_rate=missingness_before.get("location", 0.0),
                strategy=self._policy.location_strategy,
                reason="an explicit marker is filterable without inventing a location",
            ),
            MissingnessDecision(
                field="description",
                missing_rate=missingness_before.get("description", 0.0),
                strategy=MissingValueStrategy.NONE,
                reason="job descriptions are independent and must not be forward-filled",
            ),
            MissingnessDecision(
                field="posted_at",
                missing_rate=missingness_before.get("posted_at_raw", 0.0),
                strategy=MissingValueStrategy.NONE,
                reason="an unknown publication time must remain unknown",
            ),
            MissingnessDecision(
                field="employment_type",
                missing_rate=missingness_after.get("employment_type", 0.0),
                strategy=self._policy.employment_type_strategy,
                reason="infer only explicit text patterns, otherwise use the configured marker",
            ),
            salary_decision,
        ]
        return CleaningReport(
            input_rows=len(raw_jobs),
            output_rows=len(clean_jobs),
            missingness_before=missingness_before,
            missingness_after=missingness_after,
            decisions=decisions,
            dropped=dropped,
            jobs=clean_jobs,
        )

    @staticmethod
    def _frame(raw_jobs: list[RawJobPosting]) -> pd.DataFrame:
        rows = [
            job.model_dump(mode="python") | {"raw": job, "row_order": index}
            for index, job in enumerate(raw_jobs)
        ]
        return pd.DataFrame(rows, columns=[*RawJobPosting.model_fields, "raw", "row_order"])

    @staticmethod
    def _missingness(frame: pd.DataFrame, fields: tuple[str, ...]) -> dict[str, float]:
        if frame.empty:
            return {field: 0.0 for field in fields}
        return {
            field: sum(JobCleaner._is_missing(value) for value in frame[field]) / len(frame)
            for field in fields
        }

    @staticmethod
    def _identity_missingness(frame: pd.DataFrame) -> float:
        if frame.empty:
            return 0.0
        identity_fields = ("title", "company", "url")
        return sum(
            any(JobCleaner._is_missing(row[field]) for field in identity_fields)
            for _, row in frame.iterrows()
        ) / len(frame)

    @staticmethod
    def _is_missing(value: object) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    @staticmethod
    def _drop_invalid_identity(frame: pd.DataFrame, dropped: list[DroppedJob]) -> pd.DataFrame:
        if frame.empty:
            return frame
        invalid = frame[["title", "company", "url"]].map(JobCleaner._is_missing).any(axis=1)
        for _, row in frame[invalid].iterrows():
            fields = [
                field
                for field in ("title", "company", "url")
                if JobCleaner._is_missing(row[field])
            ]
            dropped.append(
                DroppedJob(
                    source=row["source"],
                    source_job_id=row["source_job_id"],
                    reason=f"missing required identity fields: {', '.join(fields)}",
                )
            )
        return frame[~invalid].copy()

    @staticmethod
    def _deduplicate_stable_ids(
        frame: pd.DataFrame, dropped: list[DroppedJob]
    ) -> pd.DataFrame:
        if frame.empty:
            return frame
        ordered = frame.sort_values(
            ["acquired_at", "row_order"], ascending=[False, True], kind="stable"
        )
        duplicate = ordered.duplicated(["source", "source_job_id"], keep="first")
        for _, row in ordered[duplicate].iterrows():
            identity = f"{row['source']}:{row['source_job_id']}"
            dropped.append(
                DroppedJob(
                    source=row["source"],
                    source_job_id=row["source_job_id"],
                    reason="duplicate stable source identity; kept the newest acquisition",
                    duplicate_of=identity,
                )
            )
        return ordered[~duplicate].sort_values("row_order", kind="stable")

    def _normalize_job(self, raw: RawJobPosting) -> CleanJobPosting:
        transformations: list[TransformationRecord] = []
        title = self._normalized_text(raw.title)
        company = self._normalized_text(raw.company)
        description = self._normalized_text(raw.description)
        location = self._location(raw.location)
        self._record_normalization("title", raw.title, title, transformations)
        self._record_normalization("company", raw.company, company, transformations)
        self._record_normalization("description", raw.description, description, transformations)
        self._record_normalization("location", raw.location, location, transformations)

        if location is None and self._policy.location_strategy is MissingValueStrategy.MARKER:
            location = self._policy.missing_marker
            transformations.append(
                TransformationRecord(
                    field="location",
                    action=TransformationAction.IMPUTED,
                    reason="missing location replaced with an explicit marker",
                )
            )

        posted_at = self._date(raw.posted_at_raw)
        if posted_at is not None:
            transformations.append(
                TransformationRecord(
                    field="posted_at",
                    action=TransformationAction.PARSED,
                    reason="parsed with pandas as a UTC timestamp",
                )
            )

        employment_type = self._employment_type(title, description)
        if employment_type is not None:
            transformations.append(
                TransformationRecord(
                    field="employment_type",
                    action=TransformationAction.INFERRED,
                    reason="matched an explicit employment-type phrase in title or description",
                )
            )
        elif self._policy.employment_type_strategy is MissingValueStrategy.MARKER:
            employment_type = self._policy.missing_marker
            transformations.append(
                TransformationRecord(
                    field="employment_type",
                    action=TransformationAction.IMPUTED,
                    reason="no explicit employment type found; used the configured marker",
                )
            )

        salary_min, salary_max, currency, period = self._salary(raw.salary_raw)
        if salary_min is not None:
            transformations.append(
                TransformationRecord(
                    field="salary",
                    action=TransformationAction.PARSED,
                    reason="parsed numeric range while preserving the raw salary text",
                )
            )
        assert title is not None and company is not None and raw.url is not None
        fingerprint = self._fingerprint(title, company, location, description)
        return CleanJobPosting(
            source=raw.source,
            source_job_id=raw.source_job_id,
            title=title,
            company=company,
            location=location,
            description=description,
            url=raw.url,
            posted_at=posted_at,
            employment_type=employment_type,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_period=period,
            acquired_at=raw.acquired_at,
            content_fingerprint=fingerprint,
            transformations=transformations,
            raw=raw,
        )

    @staticmethod
    def _normalized_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(unicodedata.normalize("NFKC", value).replace("\ufffd", "").split())
        return normalized or None

    @classmethod
    def _location(cls, value: str | None) -> str | None:
        normalized = cls._normalized_text(value)
        if normalized is None:
            return None
        lowered = normalized.casefold()
        if "remote" in lowered:
            is_us = re.search(r"\b(us|u\.s\.|united states)\b", lowered)
            return "Remote, US" if is_us else "Remote"
        match = re.fullmatch(r"(.+?),\s*([a-zA-Z]{2})", normalized)
        return f"{match.group(1).strip()}, {match.group(2).upper()}" if match else normalized

    @staticmethod
    def _date(value: str | None):
        if value is None:
            return None
        parsed = pd.to_datetime(value, errors="coerce", utc=True)
        return None if pd.isna(parsed) else parsed.to_pydatetime()

    @staticmethod
    def _employment_type(title: str | None, description: str | None) -> str | None:
        text = f"{title or ''} {description or ''}".casefold()
        patterns = (
            (r"\b(intern|internship)\b", "Internship"),
            (r"\bpart[ -]?time\b", "Part-time"),
            (r"\b(contract|contractor|temporary)\b", "Contract"),
            (r"\bfull[ -]?time\b", "Full-time"),
        )
        return next((label for pattern, label in patterns if re.search(pattern, text)), None)

    @classmethod
    def _salary(
        cls, value: str | None
    ) -> tuple[float | None, float | None, str | None, str | None]:
        normalized = cls._normalized_text(value)
        if normalized is None:
            return None, None, None, None
        lowered = normalized.casefold().replace("–", "-").replace("—", "-")
        matches = _SALARY_NUMBER.findall(lowered)
        if not matches:
            return None, None, None, None
        amounts = [
            float(number.replace(",", "")) * (1000 if suffix else 1)
            for number, suffix in matches[:2]
        ]
        minimum = amounts[0]
        maximum = amounts[-1]
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        currency = "USD" if "$" in lowered or re.search(r"\busd\b", lowered) else None
        if re.search(r"\b(hour|hourly|hr)\b", lowered):
            period = "hour"
        elif re.search(r"\b(year|yearly|annual|annum)\b", lowered):
            period = "year"
        else:
            period = None
        return minimum, maximum, currency, period

    @staticmethod
    def _fingerprint(
        title: str, company: str, location: str | None, description: str | None
    ) -> str:
        content = "\x1f".join(
            value.casefold() for value in (title, company, location or "", description or "")
        )
        return sha256(content.encode()).hexdigest()

    @staticmethod
    def _record_normalization(
        field: str,
        raw: str | None,
        normalized: str | None,
        transformations: list[TransformationRecord],
    ) -> None:
        if raw is not None and raw != normalized:
            reason = (
                "canonicalized location text after Unicode and whitespace normalization"
                if field == "location"
                else "applied Unicode NFKC and whitespace normalization"
            )
            transformations.append(
                TransformationRecord(
                    field=field,
                    action=TransformationAction.NORMALIZED,
                    reason=reason,
                )
            )

    @staticmethod
    def _deduplicate_fingerprints(
        jobs: list[CleanJobPosting], dropped: list[DroppedJob]
    ) -> list[CleanJobPosting]:
        kept: list[CleanJobPosting] = []
        by_fingerprint: dict[str, CleanJobPosting] = {}
        for job in sorted(jobs, key=lambda item: item.acquired_at, reverse=True):
            existing = by_fingerprint.get(job.content_fingerprint)
            if existing is None:
                by_fingerprint[job.content_fingerprint] = job
                kept.append(job)
            else:
                dropped.append(
                    DroppedJob(
                        source=job.source,
                        source_job_id=job.source_job_id,
                        reason="duplicate normalized content fingerprint",
                        duplicate_of=f"{existing.source}:{existing.source_job_id}",
                    )
                )
        identities = {(job.source, job.source_job_id): index for index, job in enumerate(jobs)}
        return sorted(kept, key=lambda job: identities[(job.source, job.source_job_id)])

    def _apply_salary_policy(
        self, jobs: list[CleanJobPosting]
    ) -> tuple[list[CleanJobPosting], MissingnessDecision]:
        missing_rate = (
            sum(job.salary_min is None for job in jobs) / len(jobs) if jobs else 0.0
        )
        if self._policy.salary_strategy is not MissingValueStrategy.MEDIAN:
            return jobs, MissingnessDecision(
                field="salary",
                missing_rate=missing_rate,
                strategy=MissingValueStrategy.NONE,
                reason="salary absence is preserved; forward-fill and mean would invent values",
            )
        observed = [job for job in jobs if job.salary_min is not None]
        units = {(job.salary_currency, job.salary_period) for job in observed}
        unit = next(iter(units)) if len(units) == 1 else (None, None)
        units_are_known = all(unit)
        if (
            missing_rate > self._policy.salary_median_max_missing_rate
            or not observed
            or not units_are_known
        ):
            return jobs, MissingnessDecision(
                field="salary",
                missing_rate=missing_rate,
                strategy=MissingValueStrategy.NONE,
                reason=(
                    "median imputation rejected: missingness exceeded the threshold "
                    "or units differed"
                ),
            )
        median_min = float(pd.Series([job.salary_min for job in observed]).median())
        median_max = float(pd.Series([job.salary_max for job in observed]).median())
        currency, period = unit
        imputed = [
            job
            if job.salary_min is not None
            else job.model_copy(
                update={
                    "salary_min": median_min,
                    "salary_max": median_max,
                    "salary_currency": currency,
                    "salary_period": period,
                    "transformations": [
                        *job.transformations,
                        TransformationRecord(
                            field="salary",
                            action=TransformationAction.IMPUTED,
                            reason="filled from the median of compatible observed salary ranges",
                        ),
                    ],
                }
            )
            for job in jobs
        ]
        return imputed, MissingnessDecision(
            field="salary",
            missing_rate=missing_rate,
            strategy=MissingValueStrategy.MEDIAN,
            reason="missingness was within policy and all observed salaries used compatible units",
        )

    @staticmethod
    def _clean_missingness(jobs: list[CleanJobPosting]) -> dict[str, float]:
        if not jobs:
            return {field: 0.0 for field in _CLEAN_MISSING_FIELDS}
        frame = pd.DataFrame([job.model_dump(mode="python") for job in jobs])
        return JobCleaner._missingness(frame, _CLEAN_MISSING_FIELDS)
