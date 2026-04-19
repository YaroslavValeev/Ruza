from apps.api.app.security import create_session_token, has_permission, parse_session_token


def test_token_roundtrip():
    token = create_session_token("staff_admin", "admin", ttl_minutes=5)
    payload = parse_session_token(token)
    assert payload["staff_user_id"] == "staff_admin"
    assert payload["role"] == "admin"
    assert "iat" in payload
    assert "exp" in payload


def test_permissions():
    assert has_permission("admin", "write:ops")
    assert has_permission("operator", "write:ops")
    assert not has_permission("pilot", "write:ops")
