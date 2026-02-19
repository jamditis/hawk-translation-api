import pytest
from unittest.mock import MagicMock, patch
from api.auth import authenticate_request, AuthContext


def make_mock_db(key_hash=None, org_id="org-123", tier="instant", daily_quota=100, active=True):
    mock_key = MagicMock()
    mock_key.key_hash = key_hash or "abc123"
    mock_key.active = active
    mock_key.org_id = org_id
    mock_key.id = "key-456"

    mock_org = MagicMock()
    mock_org.id = org_id
    mock_org.name = "Test Newsroom"
    mock_org.tier = tier
    mock_org.daily_quota = daily_quota
    mock_org.active = True

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_key
    mock_db.get.return_value = mock_org
    return mock_db, mock_key, mock_org


def test_missing_auth_header_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        authenticate_request(authorization=None, db=MagicMock(), redis_client=MagicMock())
    assert exc.value.status_code == 401


def test_malformed_header_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        authenticate_request(authorization="not-bearer-format", db=MagicMock(), redis_client=MagicMock())
    assert exc.value.status_code == 401


def test_invalid_key_raises():
    from fastapi import HTTPException
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    with pytest.raises(HTTPException) as exc:
        authenticate_request(authorization="Bearer hawk_live_badkey123", db=mock_db, redis_client=mock_redis)
    assert exc.value.status_code == 401


def test_valid_key_returns_auth_context():
    from api.keys import generate_api_key, hash_key
    key = generate_api_key()
    mock_db, mock_key, mock_org = make_mock_db(key_hash=hash_key(key))
    mock_redis = MagicMock()
    mock_redis.get.return_value = None  # cache miss — forces DB lookup

    ctx = authenticate_request(
        authorization=f"Bearer {key}",
        db=mock_db,
        redis_client=mock_redis
    )
    assert isinstance(ctx, AuthContext)
    assert ctx.org_id == "org-123"
    assert ctx.tier == "instant"
