import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers so pytest doesn't warn about unknown marks."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests that require live external services (Supabase, APIs)",
    )


@pytest.fixture
def mock_supabase(mocker):
    """
    Injects a MagicMock Supabase client. Use in tests that should not hit the real DB.

    Usage:
        def test_something(mock_supabase):
            mock_supabase.table.return_value.select.return_value.execute.return_value.data = []
    """
    from app.db import client as client_module
    client_module.reset_client()

    mock = mocker.MagicMock()
    mocker.patch("app.db.client.get_supabase_client", return_value=mock)
    yield mock

    client_module.reset_client()


@pytest.fixture
def sample_curated_site_data() -> dict:
    return {
        "site_name":           "LiveMint Stock Market",
        "section_url":         "https://www.livemint.com/market/stock-market-news",
        "active":              True,
        "pre_score_threshold": 4.0,
    }


@pytest.fixture
def sample_brand_voice() -> list[dict]:
    return [
        {
            "content":  "Most people think helium is for balloons. It's actually for chips, MRI machines, and rockets.",
            "platform": "linkedin",
        },
        {
            "content":  "The rupee didn't just quietly slip to ₹95 against the dollar.",
            "platform": "linkedin",
        },
    ]
