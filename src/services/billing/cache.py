"""
Billing in-process cache.

This module provides a small TTL cache for billing rule lookups and other
high-read, low-churn billing configuration objects.

Important:
- Keep cached values *session-agnostic*. Avoid caching SQLAlchemy ORM objects
  bound to a specific Session; prefer plain dataclasses / dicts.
"""

from __future__ import annotations

import time
from typing import Any


class BillingCache:
    """
    Simple TTL + LRU cache.

    - TTL: 300s (5 minutes)
    - Max entries per cache: 2048 (evict oldest on overflow)
    """

    TTL_SECONDS = 300
    MAX_ENTRIES = 2048

    _rule_cache: dict[str, tuple[Any, float]] = {}
    _collector_cache: dict[str, tuple[Any, float]] = {}
    _default_rule_cache: dict[str, tuple[Any, float]] = {}

    # ----------------------------
    # Rule cache
    # ----------------------------
    @classmethod
    def get_rule(cls, cache_key: str) -> Any | None:
        return cls._get(cls._rule_cache, cache_key)

    @classmethod
    def set_rule(cls, cache_key: str, value: Any) -> None:
        cls._set(cls._rule_cache, cache_key, value)

    # ----------------------------
    # Default-rule cache
    # ----------------------------
    @classmethod
    def get_default_rule(cls, cache_key: str) -> Any | None:
        return cls._get(cls._default_rule_cache, cache_key)

    @classmethod
    def set_default_rule(cls, cache_key: str, value: Any) -> None:
        cls._set(cls._default_rule_cache, cache_key, value)

    # ----------------------------
    # Collector cache (reserved)
    # ----------------------------
    @classmethod
    def get_collectors(cls, cache_key: str) -> Any | None:
        return cls._get(cls._collector_cache, cache_key)

    @classmethod
    def set_collectors(cls, cache_key: str, value: Any) -> None:
        cls._set(cls._collector_cache, cache_key, value)

    # ----------------------------
    # Invalidation
    # ----------------------------
    @classmethod
    def invalidate_all(cls) -> None:
        cls._rule_cache.clear()
        cls._collector_cache.clear()
        cls._default_rule_cache.clear()

    @classmethod
    def invalidate_model(cls, model_name: str) -> None:
        """
        Invalidate cache entries referencing a model name.

        Note:
        - This is best-effort string matching (cache key format must include model_name).
        """
        cls._invalidate_by_substring(cls._rule_cache, model_name)
        cls._invalidate_by_substring(cls._default_rule_cache, model_name)

    # ----------------------------
    # Internal helpers
    # ----------------------------
    @classmethod
    def _get(cls, cache: dict[str, tuple[Any, float]], key: str) -> Any | None:
        item = cache.get(key)
        if item is None:
            return None
        value, ts = item
        if time.time() - ts < cls.TTL_SECONDS:
            return value
        # expired
        try:
            del cache[key]
        except KeyError:
            pass
        return None

    @classmethod
    def _set(cls, cache: dict[str, tuple[Any, float]], key: str, value: Any) -> None:
        """Set with LRU eviction when cache exceeds MAX_ENTRIES."""
        now = time.time()
        cache[key] = (value, now)

        # Evict oldest entries if over limit
        if len(cache) > cls.MAX_ENTRIES:
            cls._evict_oldest(cache, cls.MAX_ENTRIES // 4)

    @classmethod
    def _evict_oldest(cls, cache: dict[str, tuple[Any, float]], count: int) -> None:
        """Evict the oldest `count` entries from cache."""
        if not cache or count <= 0:
            return
        # Sort by timestamp (oldest first) and remove
        sorted_keys = sorted(cache.keys(), key=lambda k: cache[k][1])
        for k in sorted_keys[:count]:
            cache.pop(k, None)

    @staticmethod
    def _invalidate_by_substring(cache: dict[str, tuple[Any, float]], needle: str) -> None:
        if not needle:
            return
        keys = [k for k in cache.keys() if needle in k]
        for k in keys:
            cache.pop(k, None)
