from jobsift.config import Settings, get_settings


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert str(settings.elasticsearch_url) == "http://elasticsearch:9200/"


def test_get_settings_reads_prefixed_environment(monkeypatch) -> None:
    monkeypatch.setenv("JOBSIFT_ENVIRONMENT", "test")
    monkeypatch.setenv("JOBSIFT_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("JOBSIFT_ELASTICSEARCH_URL", "http://search.example:9200")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.environment == "test"
    assert settings.log_level == "DEBUG"
    assert str(settings.elasticsearch_url) == "http://search.example:9200/"
    get_settings.cache_clear()
