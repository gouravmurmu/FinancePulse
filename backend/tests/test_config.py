from app.core.config import Settings


def test_database_url_gets_psycopg_driver():
    s = Settings(database_url="postgres://u:p@h:5432/d")
    assert s.database_url == "postgresql+psycopg://u:p@h:5432/d"
    s = Settings(database_url="postgresql://u:p@h:5432/d")
    assert s.database_url == "postgresql+psycopg://u:p@h:5432/d"


def test_cors_origins_parsed_from_comma_list(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.com/, https://b.com")
    assert Settings().cors_origins == ["https://a.com", "https://b.com"]
