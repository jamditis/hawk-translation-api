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


# Note: check_quota + increment_quota is not atomic. Two simultaneous requests
# from the same org can both pass the check before either increments the counter,
# allowing a brief overage at the quota boundary. For daily translation quotas
# this is an acceptable trade-off vs. the complexity of a Lua script or
# distributed lock.
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
    """Increment the org's daily usage counter. Always sets TTL to midnight UTC.

    Uses a pipeline so INCR and EXPIREAT execute in the same network roundtrip,
    preventing the key from persisting without a TTL if the process is killed between calls.
    """
    key = _quota_key(org_id)
    midnight = _midnight_timestamp()
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expireat(key, midnight)
    results = pipe.execute()
    return results[0]
