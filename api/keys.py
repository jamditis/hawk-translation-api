import secrets
import hashlib


def generate_api_key(environment: str = "live") -> str:
    """Generate a new API key. Format: hawk_{env}_{32 random chars}"""
    random_part = secrets.token_urlsafe(24)[:32]
    return f"hawk_{environment}_{random_part}"


def hash_key(key: str) -> str:
    """SHA-256 hash of the key for DB storage. Fast lookup, not bcrypt."""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_key(key: str, stored_hash: str) -> bool:
    """Verify a key against its stored hash."""
    return hash_key(key) == stored_hash


def extract_prefix(key: str) -> str:
    """Extract display prefix (e.g. 'hawk_live_abc1') for UI display."""
    parts = key.split("_")
    if len(parts) < 3:
        return key[:14]
    env_part = f"hawk_{parts[1]}_"
    return env_part + parts[2][:4]
