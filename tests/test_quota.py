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
    import time
    redis = MagicMock()
    mock_pipe = MagicMock()
    mock_pipe.execute.return_value = [1, True]  # [incr result, expireat result]
    redis.pipeline.return_value = mock_pipe

    count = increment_quota(org_id="org-1", redis_client=redis)

    assert count == 1
    mock_pipe.incr.assert_called_once()
    mock_pipe.expireat.assert_called_once()

    # Verify the expiry timestamp is within a reasonable window (now → 25h from now)
    _, kwargs = mock_pipe.expireat.call_args
    ts_arg = mock_pipe.expireat.call_args[0][1]  # second positional arg
    now = time.time()
    assert now < ts_arg <= now + 90000  # 25 hours in seconds
