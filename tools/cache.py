"""
In-memory AI response cache.

Per-process dict-based cache met TTL.
Railway heeft ephemeral filesystem, dus geen file-based cache.
Mag nooit functioneel verschil veroorzaken — alleen voor dure, niet-kritieke reads.

Configuratie via .env:
  AI_CACHE_ENABLED=1  (default: uit)
"""

import os
import time
from dotenv import load_dotenv

load_dotenv()

_CACHE_ENABLED = os.getenv("AI_CACHE_ENABLED", "0") == "1"
_cache: dict[str, tuple[float, object]] = {}


def cache_get(key: str, max_age_hours: float = 24) -> object | None:
    """Haal waarde op als cache enabled en niet verlopen."""
    if not _CACHE_ENABLED:
        return None

    entry = _cache.get(key)
    if entry is None:
        return None

    stored_at, data = entry
    if (time.time() - stored_at) > max_age_hours * 3600:
        del _cache[key]
        return None

    return data


def cache_set(key: str, data: object) -> None:
    """Sla waarde op in cache."""
    if not _CACHE_ENABLED:
        return
    _cache[key] = (time.time(), data)


def cache_clear(prefix: str = "") -> int:
    """Verwijder cache entries met gegeven prefix. Zonder prefix: alles wissen."""
    if not prefix:
        count = len(_cache)
        _cache.clear()
        return count

    to_delete = [k for k in _cache if k.startswith(prefix)]
    for k in to_delete:
        del _cache[k]
    return len(to_delete)
