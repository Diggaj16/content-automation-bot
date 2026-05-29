import pytest


def test_client_is_singleton(mocker):
    """get_supabase_client returns the same instance on repeated calls."""
    from app.db import client as client_module
    client_module.reset_client()

    mock_create = mocker.patch("app.db.client.create_client")
    mock_create.return_value = object()

    from app.db.client import get_supabase_client
    c1 = get_supabase_client()
    c2 = get_supabase_client()

    assert c1 is c2
    assert mock_create.call_count == 1

    client_module.reset_client()


def test_client_uses_service_role_key(mocker):
    """Client is initialised with the service role key, not the anon key."""
    from app.db import client as client_module
    client_module.reset_client()

    mock_create = mocker.patch("app.db.client.create_client")
    mock_create.return_value = object()

    from app.db.client import get_supabase_client
    get_supabase_client()

    call_args = mock_create.call_args[0]
    key_used = call_args[1]
    assert len(key_used) > 50   # service role JWTs are long
    assert key_used != "anon"

    client_module.reset_client()


@pytest.mark.integration
def test_client_can_query_supabase():
    """Real connection smoke test — requires .env with valid credentials."""
    from app.db import client as client_module
    client_module.reset_client()

    from app.db.client import get_supabase_client
    db = get_supabase_client()

    result = db.table("curated_sites").select("id").limit(1).execute()
    assert result is not None
    assert hasattr(result, "data")

    client_module.reset_client()
