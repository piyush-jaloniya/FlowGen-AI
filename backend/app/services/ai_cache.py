import hashlib
import json
import os
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class AIInsightsCache:
    """Cache for AI-generated insights to reduce API calls."""
    
    def __init__(self, ttl_hours: int = 24):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = timedelta(hours=ttl_hours)
    
    def get_cache_key(self, code: str, analysis_type: str) -> str:
        """Generate cache key from code hash and analysis type."""
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        return f"{analysis_type}:{code_hash[:16]}"
    
    def get(self, code: str, analysis_type: str) -> Optional[str]:
        """Get cached response if available and not expired."""
        key = self.get_cache_key(code, analysis_type)
        if key in self.cache:
            entry = self.cache[key]
            if datetime.now() - entry['timestamp'] < self.ttl:
                logger.info(f"Cache hit for {analysis_type}")
                return entry['response']
            else:
                # Expired, remove from cache
                del self.cache[key]
                logger.debug(f"Cache expired for {analysis_type}")
        return None
    
    def set(self, code: str, analysis_type: str, response: str):
        """Cache the response."""
        key = self.get_cache_key(code, analysis_type)
        self.cache[key] = {
            'response': response,
            'timestamp': datetime.now()
        }
        logger.debug(f"Cached response for {analysis_type}")
    
    def clear_expired(self):
        """Remove all expired entries from cache."""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self.cache.items()
            if now - entry['timestamp'] >= self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]
        if expired_keys:
            logger.info(f"Cleared {len(expired_keys)} expired cache entries")


class QuotaTracker:
    """Track and limit AI API usage to prevent quota exhaustion."""
    
    def __init__(self, daily_limit: int = 15, usage_file: str = ".ai_insights_usage.json"):
        self.daily_limit = daily_limit
        self.usage_file = usage_file
        self.usage = self._load_usage()
    
    def _load_usage(self) -> Dict[str, Any]:
        """Load usage data from file."""
        if os.path.exists(self.usage_file):
            try:
                with open(self.usage_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load usage file: {e}")
        return {'date': str(date.today()), 'count': 0}
    
    def _save_usage(self):
        """Save usage data to file."""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(self.usage, f)
        except Exception as e:
            logger.error(f"Failed to save usage file: {e}")
    
    def can_make_request(self) -> tuple[bool, int]:
        """
        Check if request can be made.
        Returns: (can_make, remaining_requests)
        """
        today = str(date.today())
        
        # Reset counter if it's a new day
        if self.usage.get('date') != today:
            self.usage = {'date': today, 'count': 0}
            self._save_usage()
        
        remaining = self.daily_limit - self.usage.get('count', 0)
        return remaining > 0, max(0, remaining)
    
    def increment(self):
        """Increment usage counter."""
        self.usage['count'] = self.usage.get('count', 0) + 1
        self._save_usage()
        logger.info(f"AI Insights usage: {self.usage['count']}/{self.daily_limit}")
    
    def get_remaining(self) -> int:
        """Get remaining requests for today."""
        _, remaining = self.can_make_request()
        return remaining
    
    def reset(self):
        """Reset usage counter (for testing)."""
        self.usage = {'date': str(date.today()), 'count': 0}
        self._save_usage()
