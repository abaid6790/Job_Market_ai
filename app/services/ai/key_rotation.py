"""
Rotates through multiple API keys for a single provider.

On a rate-limit/quota failure, the offending key is put in cooldown and
excluded from rotation until it expires — it isn't permanently discarded,
so a temporarily-exhausted key automatically becomes available again
without any manual intervention.
"""
import time


class KeyRotator:
    def __init__(self, keys: list[str], cooldown_seconds: int = 60):
        self.keys = [k for k in keys if k]
        self.cooldown_seconds = cooldown_seconds
        self._disabled_until: dict[str, float] = {}
        self._failure_counts: dict[str, int] = {}
        self._last_success: dict[str, float] = {}
        self._next_index = 0

    def has_keys(self) -> bool:
        return bool(self.keys)

    def available_keys(self) -> list[str]:
        now = time.time()
        return [k for k in self.keys if self._disabled_until.get(k, 0) <= now]

    def get_key(self) -> str | None:
        """Round-robin among currently-available (not-in-cooldown) keys."""
        available = self.available_keys()
        if not available:
            return None
        key = available[self._next_index % len(available)]
        self._next_index += 1
        return key

    def mark_failure(self, key: str, cooldown_seconds: int | None = None) -> None:
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1
        self._disabled_until[key] = time.time() + (cooldown_seconds or self.cooldown_seconds)

    def mark_success(self, key: str) -> None:
        self._last_success[key] = time.time()
        self._failure_counts[key] = 0
        self._disabled_until.pop(key, None)

    def status(self) -> list[dict]:
        now = time.time()
        return [
            {
                "key_suffix": key[-4:] if len(key) >= 4 else key,
                "available": self._disabled_until.get(key, 0) <= now,
                "failure_count": self._failure_counts.get(key, 0),
                "cooldown_remaining_seconds": max(0, round(self._disabled_until.get(key, 0) - now)),
                "last_success": self._last_success.get(key),
            }
            for key in self.keys
        ]
