import pytest
from unittest.mock import MagicMock
from api.quota import check_quota, increment_quota


def make_redis(current_count):
    mock = MagicMock()
    mock.get.return_value = str(current_count).encode() if current_count is not None else None
    return mock


def test_under_quota_passes():
    redis = make_redis(current_count=10)
    # Should not raise
    check_quota(org_id="org-1", daily_quota=100, redis_client=redis)


def test_at_quota_raises():
    from fastapi import HTTPException
    redis = make_redis(current_count=100)
    with pytest.raises(HTTPException) as exc:
        check_quota(org_id="org-1", daily_quota=100, redis_client=redis)
    assert exc.value.status_code == 429
    assert "quota_exceeded" in str(exc.value.detail)


def test_no_existing_count_passes():
    redis = make_redis(current_count=None)
    check_quota(org_id="org-1", daily_quota=50, redis_client=redis)


def test_increment_sets_expiry():
    redis = MagicMock()
    redis.incr.return_value = 1  # first increment of the day
    increment_quota(org_id="org-1", redis_client=redis)
    redis.incr.assert_called_once()
    redis.expireat.assert_called_once()
