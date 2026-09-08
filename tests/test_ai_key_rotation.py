import time

from app.services.ai.key_rotation import KeyRotator


def test_no_keys_returns_none():
    rotator = KeyRotator([])
    assert rotator.has_keys() is False
    assert rotator.get_key() is None


def test_round_robin_across_keys():
    rotator = KeyRotator(["key1", "key2", "key3"])
    seen = [rotator.get_key() for _ in range(6)]
    assert seen == ["key1", "key2", "key3", "key1", "key2", "key3"]


def test_failed_key_excluded_until_cooldown_expires():
    rotator = KeyRotator(["key1", "key2"], cooldown_seconds=0.05)
    rotator.mark_failure("key1")
    assert rotator.get_key() == "key2"
    assert rotator.get_key() == "key2"  # key1 still cooling down

    time.sleep(0.06)
    available = set(rotator.available_keys())
    assert "key1" in available  # back in rotation after cooldown


def test_mark_success_clears_failure_state():
    rotator = KeyRotator(["key1"], cooldown_seconds=100)
    rotator.mark_failure("key1")
    assert rotator.available_keys() == []
    rotator.mark_success("key1")
    assert rotator.available_keys() == ["key1"]
    assert rotator.status()[0]["failure_count"] == 0


def test_status_reports_key_suffix_not_full_key():
    rotator = KeyRotator(["sk-supersecretkey1234"])
    status = rotator.status()[0]
    assert status["key_suffix"] == "1234"
    assert "supersecret" not in str(status)  # never leak the full key


def test_all_keys_in_cooldown_get_key_returns_none():
    rotator = KeyRotator(["key1", "key2"], cooldown_seconds=100)
    rotator.mark_failure("key1")
    rotator.mark_failure("key2")
    assert rotator.get_key() is None
