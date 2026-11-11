from datetime import date

import pytest
from jobsift.acquisition.models import AcquisitionMethod, SourceConfig


def test_fixture_source_is_allowed_without_live_site_reviews(source_config: SourceConfig) -> None:
    source_config.assert_collection_allowed()


def test_disabled_source_is_rejected(source_config: SourceConfig) -> None:
    disabled = source_config.model_copy(update={"enabled": False})

    with pytest.raises(ValueError, match="is disabled"):
        disabled.assert_collection_allowed()


@pytest.mark.parametrize(
    ("policy_update", "message"),
    [
        ({"robots_txt_reviewed": False}, "no robots.txt review"),
        ({"terms_reviewed": False}, "no terms review"),
        ({"public_jobs_only": False}, "not limited to public jobs"),
        ({"collects_personal_data": True}, "would collect personal data"),
    ],
)
def test_live_source_must_pass_every_compliance_gate(
    source_config: SourceConfig,
    policy_update: dict[str, bool],
    message: str,
) -> None:
    verified_policy = source_config.compliance.model_copy(
        update={"robots_txt_reviewed": True, "terms_reviewed": True}
    )
    policy = verified_policy.model_copy(update=policy_update)
    live = source_config.model_copy(
        update={"method": AcquisitionMethod.HTTP, "compliance": policy}
    )

    with pytest.raises(ValueError, match=message):
        live.assert_collection_allowed()


def test_verified_public_live_source_is_allowed(source_config: SourceConfig) -> None:
    policy = source_config.compliance.model_copy(
        update={
            "robots_txt_reviewed": True,
            "terms_reviewed": True,
            "reviewed_on": date(2026, 11, 11),
        }
    )
    live = source_config.model_copy(
        update={
            "method": AcquisitionMethod.HTTP,
            "compliance": policy,
            "endpoint_url": "https://jobs.example.test/api/jobs",
            "http": {
                "timeout_seconds": 10,
                "max_attempts": 2,
                "initial_backoff_seconds": 0.1,
                "max_backoff_seconds": 1,
                "user_agent": "JobSift tests",
            },
        }
    )

    live.assert_collection_allowed()


def test_live_source_requires_review_date(source_config: SourceConfig) -> None:
    policy = source_config.compliance.model_copy(
        update={"robots_txt_reviewed": True, "terms_reviewed": True}
    )
    live = source_config.model_copy(
        update={"method": AcquisitionMethod.HTTP, "compliance": policy}
    )

    with pytest.raises(ValueError, match="no compliance review date"):
        live.assert_collection_allowed()


def test_live_source_requires_endpoint_and_http_policy(source_config: SourceConfig) -> None:
    policy = source_config.compliance.model_copy(
        update={
            "robots_txt_reviewed": True,
            "terms_reviewed": True,
            "reviewed_on": date(2026, 11, 11),
        }
    )
    missing_endpoint = source_config.model_copy(
        update={"method": AcquisitionMethod.HTTP, "compliance": policy}
    )
    with pytest.raises(ValueError, match="no endpoint URL"):
        missing_endpoint.assert_collection_allowed()

    missing_http = missing_endpoint.model_copy(
        update={"endpoint_url": "https://jobs.example.test/api/jobs"}
    )
    with pytest.raises(ValueError, match="no HTTP policy"):
        missing_http.assert_collection_allowed()
