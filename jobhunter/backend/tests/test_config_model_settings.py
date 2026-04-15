from app.config import settings


def test_scout_queries_model_defaults_to_mini():
    assert settings.SCOUT_QUERIES_MODEL == "gpt-4o-mini"


def test_scout_parse_model_defaults_to_mini():
    assert settings.SCOUT_PARSE_MODEL == "gpt-4o-mini"


def test_analytics_insights_model_defaults_to_mini():
    assert settings.ANALYTICS_INSIGHTS_MODEL == "gpt-4o-mini"
