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
        update={"robots_txt_reviewed": True, "terms_reviewed": True}
    )
    live = source_config.model_copy(
        update={"method": AcquisitionMethod.HTTP, "compliance": policy}
    )

    live.assert_collection_allowed()
