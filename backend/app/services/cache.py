"""Tiny in-process TTL cache. Market data changes twice a day, so a few
minutes of caching removes nearly all repeat database work on the free tier."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

_store: dict[tuple[Any, ...], tuple[float, Any]] = {}
_lock = threading.Lock()
MAX_ENTRIES = 512


def ttl_cache(seconds: float) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # The first positional argument is a DB session; never part of the key.
            key = (fn.__qualname__, args[1:], tuple(sorted(kwargs.items())))
            now = time.monotonic()
            with _lock:
                hit = _store.get(key)
                if hit and hit[0] > now:
                    return hit[1]
            value = fn(*args, **kwargs)
            with _lock:
                if len(_store) >= MAX_ENTRIES:
                    _store.clear()
                _store[key] = (now + seconds, value)
            return value

        return wrapper

    return decorator


def clear() -> None:
    with _lock:
        _store.clear()
