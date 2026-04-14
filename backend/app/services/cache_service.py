"""
Caching service for FlowGen AI.
Provides in-memory caching for expensive operations like parsing and diagram generation.
"""
import hashlib
import logging
from typing import Any, Optional, Callable
from functools import wraps
from cachetools import TTLCache, LRUCache

logger = logging.getLogger(__name__)


class CacheService:
    """
    Caching service using in-memory cache.
    Uses TTL (Time To Live) cache for automatic expiration.
    """
    
    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        """
        Initialize cache service.
        
        Args:
            maxsize: Maximum number of cached items
            ttl: Time to live in seconds (default: 1 hour)
        """
        # TTL cache for parsed code (expires after 1 hour)
        self.parse_cache = TTLCache(maxsize=maxsize, ttl=ttl)
        
        # LRU cache for diagram generation (keeps most recently used)
        self.diagram_cache = LRUCache(maxsize=maxsize // 2)
        
        logger.info(f"Cache initialized: maxsize={maxsize}, ttl={ttl}s")
    
    def _generate_key(self, *args, **kwargs) -> str:
        """
        Generate a unique cache key from arguments.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            MD5 hash of the arguments
        """
        # Combine all arguments into a string
        key_parts = [str(arg) for arg in args]
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
        key_string = "|".join(key_parts)
        
        # Generate MD5 hash
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def cache_parse_result(self, language: str, filename: str, content: str) -> Optional[Any]:
        """
        Get cached parse result.
        
        Args:
            language: Programming language
            filename: File name
            content: Code content
            
        Returns:
            Cached result or None if not found
        """
        key = self._generate_key(language, filename, content)
        result = self.parse_cache.get(key)
        
        if result:
            logger.debug(f"Cache HIT for parse: {filename}")
        else:
            logger.debug(f"Cache MISS for parse: {filename}")
        
        return result
    
    def store_parse_result(self, language: str, filename: str, content: str, result: Any):
        """
        Store parse result in cache.
        
        Args:
            language: Programming language
            filename: File name
            content: Code content
            result: Parse result to cache
        """
        key = self._generate_key(language, filename, content)
        self.parse_cache[key] = result
        logger.debug(f"Cached parse result for: {filename}")
    
    def cache_diagram_result(self, diagram_type: str, parsed_data: dict) -> Optional[Any]:
        """
        Get cached diagram result.
        
        Args:
            diagram_type: 'flowchart' or 'workflow'
            parsed_data: Parsed code data
            
        Returns:
            Cached result or None if not found
        """
        # Use a simplified key based on parsed data structure
        key = self._generate_key(diagram_type, str(parsed_data))
        result = self.diagram_cache.get(key)
        
        if result:
            logger.debug(f"Cache HIT for {diagram_type}")
        else:
            logger.debug(f"Cache MISS for {diagram_type}")
        
        return result
    
    def store_diagram_result(self, diagram_type: str, parsed_data: dict, result: Any):
        """
        Store diagram result in cache.
        
        Args:
            diagram_type: 'flowchart' or 'workflow'
            parsed_data: Parsed code data
            result: Diagram result to cache
        """
        key = self._generate_key(diagram_type, str(parsed_data))
        self.diagram_cache[key] = result
        logger.debug(f"Cached {diagram_type} result")
    
    def clear_cache(self):
        """Clear all caches."""
        self.parse_cache.clear()
        self.diagram_cache.clear()
        logger.info("All caches cleared")
    
    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        return {
            "parse_cache": {
                "size": len(self.parse_cache),
                "maxsize": self.parse_cache.maxsize,
                "hits": getattr(self.parse_cache, 'hits', 0),
                "misses": getattr(self.parse_cache, 'misses', 0)
            },
            "diagram_cache": {
                "size": len(self.diagram_cache),
                "maxsize": self.diagram_cache.maxsize,
                "hits": getattr(self.diagram_cache, 'hits', 0),
                "misses": getattr(self.diagram_cache, 'misses', 0)
            }
        }


# Global cache instance
cache_service = CacheService(maxsize=1000, ttl=3600)


def cached_parse(func: Callable) -> Callable:
    """
    Decorator for caching parse results.
    
    Usage:
        @cached_parse
        def parse_code(language, filename, content):
            ...
    """
    @wraps(func)
    def wrapper(self, language: str, filename: str, content: str, *args, **kwargs):
        # Try to get from cache
        cached_result = cache_service.cache_parse_result(language, filename, content)
        if cached_result is not None:
            return cached_result
        
        # Not in cache, execute function
        result = func(self, language, filename, content, *args, **kwargs)
        
        # Store in cache
        cache_service.store_parse_result(language, filename, content, result)
        
        return result
    
    return wrapper


def cached_diagram(diagram_type: str):
    """
    Decorator factory for caching diagram results.
    
    Usage:
        @cached_diagram('flowchart')
        def build(self, parsed_data):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, parsed_data: dict, *args, **kwargs):
            # Try to get from cache
            cached_result = cache_service.cache_diagram_result(diagram_type, parsed_data)
            if cached_result is not None:
                return cached_result
            
            # Not in cache, execute function
            result = func(self, parsed_data, *args, **kwargs)
            
            # Store in cache
            cache_service.store_diagram_result(diagram_type, parsed_data, result)
            
            return result
        
        return wrapper
    
    return decorator
