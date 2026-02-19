from api.keys import generate_api_key, hash_key, verify_key, extract_prefix

def test_generate_live_key_format():
    key = generate_api_key(environment="live")
    assert key.startswith("hawk_live_")
    assert len(key) == len("hawk_live_") + 32

def test_generate_test_key_format():
    key = generate_api_key(environment="test")
    assert key.startswith("hawk_test_")

def test_key_prefix_extraction():
    key = generate_api_key(environment="live")
    prefix = extract_prefix(key)
    assert prefix.startswith("hawk_live_")
    assert len(prefix) == 14  # "hawk_live_" (10) + 4 random chars

def test_hash_is_deterministic():
    key = "hawk_live_abc123def456ghi789jkl012mno3"
    expected = "70a59f4a8e647bdf378992b08af4e31707dfed32a8accc69de3fc14c030143fa"
    assert hash_key(key) == expected
    assert hash_key(key) == hash_key(key)  # also self-consistent

def test_verify_correct_key():
    key = generate_api_key()
    hashed = hash_key(key)
    assert verify_key(key, hashed) is True

def test_verify_wrong_key():
    key = generate_api_key()
    hashed = hash_key(key)
    assert verify_key("hawk_live_wrongkey12345678901234567", hashed) is False
