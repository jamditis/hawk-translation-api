from datetime import datetime, UTC, timedelta
from fastapi import HTTPException
from redis import Redis


# Lua script for atomic check-and-increment.
# Returns 0 if the new count is within quota, or 1 if quota is exceeded.
_CHECK_AND_INCREMENT_LUA = """
local key = KEYS[1]
local quota = tonumber(ARGV[1])
local expiry = tonumber(ARGV[2])
local current = tonumber(redis.call('GET', key) or '0')
if current >= quota then
    return 1
end
redis.call('INCR', key)
redis.call('EXPIREAT', key, expiry)
return 0
"""


def _quota_key(org_id: str) -> str:
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"quota:{org_id}:{date_str}"


def _midnight_timestamp() -> int:
    now = datetime.now(UTC)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp())


def check_and_increment_quota(org_id: str, daily_quota: int, redis_client: Redis) -> None:
    """Atomically check quota and increment if within limit.

    Uses a Lua script so the check+increment is a single atomic Redis operation,
    eliminating the TOCTOU race that existed with separate check/increment calls.
    Raises 429 if the org has hit its daily translation quota.
    """
    key = _quota_key(org_id)
    midnight = _midnight_timestamp()
    exceeded = redis_client.eval(_CHECK_AND_INCREMENT_LUA, 1, key, daily_quota, midnight)
    if exceeded:
        reset_at = datetime.fromtimestamp(midnight, UTC).isoformat()
        raise HTTPException(
            status_code=429,
            detail={"error": "quota_exceeded", "reset_at": reset_at, "limit": daily_quota},
        )


# Keep the old functions available for callers that need read-only checks
# or explicit increments (e.g. admin tooling).
def check_quota(org_id: str, daily_quota: int, redis_client: Redis) -> None:
    """Raise 429 if org has hit its daily translation quota (read-only check)."""
    key = _quota_key(org_id)
    current = redis_client.get(key)
    count = int(current) if current else 0
    if count >= daily_quota:
        reset_at = datetime.fromtimestamp(_midnight_timestamp(), UTC).isoformat()
        raise HTTPException(
            status_code=429,
            detail={"error": "quota_exceeded", "reset_at": reset_at, "limit": daily_quota},
        )


def increment_quota(org_id: str, redis_client: Redis) -> int:
    """Increment the org's daily usage counter. Always sets TTL to midnight UTC."""
    key = _quota_key(org_id)
    midnight = _midnight_timestamp()
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expireat(key, midnight)
    results = pipe.execute()
    return results[0]
