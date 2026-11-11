import json
from pathlib import Path

import pytest
from jobsift.acquisition.models import SourceConfig

REPOSITORY_ROOT = Path(__file__).parents[3]


@pytest.fixture
def fixture_path() -> Path:
    return REPOSITORY_ROOT / "backend/tests/fixtures/example_jobs.html"


@pytest.fixture
def source_config() -> SourceConfig:
    config_path = REPOSITORY_ROOT / "config/sources/example-fixture.json"
    return SourceConfig.model_validate(json.loads(config_path.read_text()))
