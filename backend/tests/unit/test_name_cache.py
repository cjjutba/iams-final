"""
Tests for the thread-safe NameCache used in live_stream.py.
Verifies: set/get, TTL expiry, thread safety under concurrent writes.
"""
import time
import threading
import pytest


def get_cache_class():
    from app.routers.live_stream import NameCache
    return NameCache


def test_cache_stores_and_retrieves():
    NameCache = get_cache_class()
    cache = NameCache(ttl_seconds=60)
    cache.set("user-1", "Alice Santos", "2023-0001")
    result = cache.get("user-1")
    assert result is not None
    name, sid = result
    assert name == "Alice Santos"
    assert sid == "2023-0001"


def test_cache_returns_none_for_missing_key():
    NameCache = get_cache_class()
    cache = NameCache(ttl_seconds=60)
    assert cache.get("nonexistent") is None


def test_cache_expires_after_ttl():
    """Entries should return None after TTL elapses."""
    NameCache = get_cache_class()
    cache = NameCache(ttl_seconds=1)
    cache.set("user-2", "Bob Reyes", "2023-0002")

    # Manually expire the entry by backdating its timestamp
    with cache._lock:
        value, _ = cache._store["user-2"]
        cache._store["user-2"] = (value, time.monotonic() - 2)  # 2 seconds ago

    assert cache.get("user-2") is None, "Expired entry should return None"


def test_cache_is_thread_safe():
    """Concurrent writes must not corrupt the cache."""
    NameCache = get_cache_class()
    cache = NameCache(ttl_seconds=300)
    errors = []

    def writer(uid, name):
        try:
            for _ in range(100):
                cache.set(uid, name, f"id-{uid}")
                cache.get(uid)
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=writer, args=(f"u{i}", f"Student {i}"))
        for i in range(20)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread safety errors: {errors}"


def test_cache_overwrite_refreshes_ttl():
    """Re-setting an entry resets its TTL."""
    NameCache = get_cache_class()
    cache = NameCache(ttl_seconds=1)
    cache.set("user-3", "Carol Tan", "2023-0003")

    # Expire it manually
    with cache._lock:
        value, _ = cache._store["user-3"]
        cache._store["user-3"] = (value, time.monotonic() - 2)

    # Re-set with fresh TTL
    cache.set("user-3", "Carol Tan Updated", "2023-0003")
    result = cache.get("user-3")
    assert result is not None
    assert result[0] == "Carol Tan Updated"
