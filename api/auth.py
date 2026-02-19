import json
from dataclasses import dataclass
import hmac as _hmac
from fastapi import HTTPException
from sqlalchemy.orm import Session
from redis import Redis
from api.keys import hash_key
from db.models import APIKey, Organization


@dataclass
class AuthContext:
    org_id: str
    org_name: str
    tier: str
    daily_quota: int
    api_key_id: str


CACHE_TTL_SECONDS = 300  # 5 minutes


def authenticate_request(
    authorization: str | None,
    db: Session,
    redis_client: Redis,
) -> AuthContext:
    if not authorization:
        raise HTTPException(status_code=401, detail={"error": "missing_auth_header"})

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail={"error": "invalid_auth_format"})

    raw_key = parts[1]
    key_hash = hash_key(raw_key)

    # Redis cache check (5-min TTL avoids DB hit on every request)
    cache_key = f"api_key:{key_hash}"
    cached = redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        return AuthContext(**data)

    # DB lookup on cache miss
    api_key = db.query(APIKey).filter(
        APIKey.key_hash == key_hash,
        APIKey.active == True,
    ).first()

    if not api_key:
        raise HTTPException(status_code=401, detail={"error": "invalid_api_key"})

    org = db.get(Organization, api_key.org_id)
    if not org or not org.active:
        raise HTTPException(status_code=401, detail={"error": "invalid_api_key"})

    ctx = AuthContext(
        org_id=org.id,
        org_name=org.name,
        tier=org.tier,
        daily_quota=org.daily_quota,
        api_key_id=api_key.id,
    )

    # Cache for 5 minutes
    redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(ctx.__dict__))

    return ctx
