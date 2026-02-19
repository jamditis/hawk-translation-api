from datetime import datetime, UTC, timedelta
from fastapi import HTTPException
from redis import Redis


def _quota_key(org_id: str) -> str:
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"quota:{org_id}:{date_str}"


def _midnight_timestamp() -> int:
    now = datetime.now(UTC)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp())


def check_quota(org_id: str, daily_quota: int, redis_client: Redis) -> None:
    """Raise 429 if org has hit its daily translation quota."""
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
    """Increment the org's daily usage counter. Sets TTL to midnight UTC on first increment."""
    key = _quota_key(org_id)
    count = redis_client.incr(key)
    if count == 1:
        # First increment today — set expiry to midnight UTC so counter auto-resets
        redis_client.expireat(key, _midnight_timestamp())
    return count
