import hmac
import secrets
import hashlib


def generate_api_key(environment: str = "live") -> str:
    """Generate a new API key. Format: hawk_{env}_{32 random chars}"""
    # token_urlsafe(24) produces exactly 32 base64url chars (24 bytes × 4/3, no padding)
    random_part = secrets.token_urlsafe(24)[:32]
    return f"hawk_{environment}_{random_part}"


def hash_key(key: str) -> str:
    """SHA-256 hash of the key for DB storage. Fast lookup, not bcrypt."""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_key(key: str, stored_hash: str) -> bool:
    """Verify a key against its stored hash."""
    return hmac.compare_digest(hash_key(key), stored_hash)


def extract_prefix(key: str) -> str:
    """Extract display prefix (e.g. 'hawk_live_abc1') for UI display."""
    # Key format is hawk_{env}_{32 random chars}. Find the second underscore
    # by splitting only on the first two, avoiding splits in the random part.
    parts = key.split("_", 2)
    if len(parts) < 3:
        return ""
    env_part = f"hawk_{parts[1]}_"
    return env_part + parts[2][:4]
