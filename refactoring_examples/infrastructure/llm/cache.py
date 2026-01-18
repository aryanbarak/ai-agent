"""
Thread-safe cache implementations with eviction policies.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from typing import Any


class LRUCache:
    """
    Thread-safe LRU (Least Recently Used) cache with size limit.
    
    Features:
    - Automatic eviction of least recently used items
    - Thread-safe operations using asyncio locks
    - TTL (Time To Live) support
    - Size limit enforcement
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int | None = 3600):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of items to store
            default_ttl: Default TTL in seconds (None = no expiration)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, tuple[Any, float | None]] = OrderedDict()
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Any | None:
        """
        Retrieve value from cache.
        
        Returns None if key doesn't exist or is expired.
        """
        async with self._lock:
            if key not in self._cache:
                return None
            
            value, expiry = self._cache[key]
            
            # Check if expired
            if expiry is not None and time.time() > expiry:
                del self._cache[key]
                return None
            
            # Move to end (mark as recently used)
            self._cache.move_to_end(key)
            
            return value
    
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """
        Store value in cache.
        
        Args:
            key: Cache key
            value: Value to store
            ttl: TTL in seconds (None = use default, 0 = no expiration)
        """
        async with self._lock:
            # Calculate expiry time
            if ttl == 0:
                expiry = None
            else:
                ttl_seconds = ttl if ttl is not None else self.default_ttl
                expiry = time.time() + ttl_seconds if ttl_seconds else None
            
            # Add/update item
            if key in self._cache:
                self._cache.move_to_end(key)
            
            self._cache[key] = (value, expiry)
            
            # Evict oldest if over size limit
            if len(self._cache) > self.max_size:
                self._cache.popitem(last=False)  # Remove oldest (first) item
    
    async def delete(self, key: str) -> None:
        """Remove value from cache."""
        async with self._lock:
            self._cache.pop(key, None)
    
    async def clear(self) -> None:
        """Clear all cached values."""
        async with self._lock:
            self._cache.clear()
    
    async def size(self) -> int:
        """Return current cache size."""
        async with self._lock:
            return len(self._cache)
    
    async def cleanup_expired(self) -> int:
        """
        Remove all expired items.
        
        Returns:
            Number of items removed
        """
        async with self._lock:
            now = time.time()
            expired_keys = [
                key
                for key, (_, expiry) in self._cache.items()
                if expiry is not None and now > expiry
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            return len(expired_keys)


class SemanticCache:
    """
    Semantic cache for LLM responses.
    
    Uses content hashing to identify similar requests and
    cache responses for reuse.
    """
    
    def __init__(self, base_cache: LRUCache):
        self.base_cache = base_cache
    
    def _make_key(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        model: str,
    ) -> str:
        """
        Create cache key from request parameters.
        
        Uses SHA256 hash of normalized content.
        """
        # Normalize messages to JSON string
        normalized = json.dumps(
            {
                "messages": messages,
                "temperature": round(temperature, 2),
                "model": model,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        
        # Hash to create compact key
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    async def get_response(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        model: str,
    ) -> dict[str, Any] | None:
        """Retrieve cached LLM response."""
        key = self._make_key(messages, temperature, model)
        return await self.base_cache.get(key)
    
    async def set_response(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        model: str,
        response: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """Store LLM response in cache."""
        key = self._make_key(messages, temperature, model)
        await self.base_cache.set(key, response, ttl=ttl)
    
    async def clear(self) -> None:
        """Clear all cached responses."""
        await self.base_cache.clear()


# ============================================================================
# Background cleanup task
# ============================================================================

async def periodic_cleanup(cache: LRUCache, interval: int = 300):
    """
    Periodically clean up expired cache entries.
    
    Args:
        cache: Cache instance to clean
        interval: Cleanup interval in seconds (default: 5 minutes)
    """
    while True:
        await asyncio.sleep(interval)
        removed = await cache.cleanup_expired()
        if removed > 0:
            print(f"[Cache] Cleaned up {removed} expired entries")
