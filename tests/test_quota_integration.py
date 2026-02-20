"""Integration tests for quota enforcement against a real Redis instance.

Requires REDIS_URL env var pointing to a running Redis.
These tests flush the keys they create but use a unique prefix to avoid collisions.
"""

import os
import uuid

import pytest
from redis import Redis

from api.quota import check_and_increment_quota, check_quota, _quota_key


@pytest.fixture
def redis_client():
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    client = Redis.from_url(url)
    try:
        client.ping()
    except Exception:
        pytest.skip("Redis not available")
    return client


@pytest.fixture
def org_id():
    return f"test-org-{uuid.uuid4().hex[:8]}"


def test_atomic_quota_allows_within_limit(redis_client, org_id):
    """check_and_increment_quota allows requests within the daily limit."""
    # Should not raise for first 3 requests with quota=3
    for _ in range(3):
        check_and_increment_quota(org_id, daily_quota=3, redis_client=redis_client)

    # Clean up
    key = _quota_key(org_id)
    redis_client.delete(key)


def test_atomic_quota_blocks_at_limit(redis_client, org_id):
    """check_and_increment_quota raises 429 once the limit is reached."""
    from fastapi import HTTPException

    for _ in range(5):
        check_and_increment_quota(org_id, daily_quota=5, redis_client=redis_client)

    with pytest.raises(HTTPException) as exc_info:
        check_and_increment_quota(org_id, daily_quota=5, redis_client=redis_client)

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["error"] == "quota_exceeded"

    key = _quota_key(org_id)
    redis_client.delete(key)


def test_atomic_quota_no_race_condition(redis_client, org_id):
    """With quota=1, only one of two rapid calls should succeed."""
    from fastapi import HTTPException
    import concurrent.futures

    results = []

    def try_increment():
        try:
            check_and_increment_quota(org_id, daily_quota=1, redis_client=redis_client)
            return "ok"
        except HTTPException:
            return "blocked"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(try_increment) for _ in range(2)]
        results = [f.result() for f in futures]

    assert results.count("ok") == 1, f"Expected exactly 1 success, got: {results}"
    assert results.count("blocked") == 1, f"Expected exactly 1 block, got: {results}"

    key = _quota_key(org_id)
    redis_client.delete(key)


def test_quota_key_has_ttl(redis_client, org_id):
    """After incrementing, the key should have a TTL (expires at midnight UTC)."""
    check_and_increment_quota(org_id, daily_quota=100, redis_client=redis_client)

    key = _quota_key(org_id)
    ttl = redis_client.ttl(key)
    assert ttl > 0, f"Expected positive TTL, got {ttl}"
    # TTL should be less than 24 hours
    assert ttl <= 86400, f"TTL {ttl}s exceeds 24 hours"

    redis_client.delete(key)
