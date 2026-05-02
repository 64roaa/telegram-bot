import time
import logging
import re
from typing import Dict, Tuple

logger = logging.getLogger("Amanteech.Core.Security")

class SecurityManager:
    """Enterprise-grade security and rate limiting system."""
    
    def __init__(self):
        # user_id -> (last_request_time, count)
        self._user_flood_cache: Dict[int, Tuple[float, int]] = {}
        self.FLOOD_THRESHOLD = 5  # requests
        self.FLOOD_WINDOW = 3     # seconds
        self.BAN_TIME = 60        # seconds

    def is_flooding(self, user_id: int) -> bool:
        """Check if a user is exceeding rate limits."""
        now = time.time()
        if user_id not in self._user_flood_cache:
            self._user_flood_cache[user_id] = (now, 1)
            return False

        last_time, count = self._user_flood_cache[user_id]
        
        # Reset window if time passed
        if now - last_time > self.FLOOD_WINDOW:
            self._user_flood_cache[user_id] = (now, 1)
            return False

        # Increment count within window
        new_count = count + 1
        self._user_flood_cache[user_id] = (last_time, new_count)
        
        if new_count > self.FLOOD_THRESHOLD:
            logger.warning(f"🚨 FLOOD DETECTED: User {user_id} sent {new_count} requests in {self.FLOOD_WINDOW}s")
            return True
        
        return False

    @staticmethod
    def sanitize_input(text: str) -> str:
        """Clean and sanitize user input to prevent injection/malformed data."""
        if not text: return ""
        # Remove potentially dangerous characters but keep Arabic/English
        clean_text = re.sub(r'[<>{}\[\]\\]', '', text)
        return clean_text.strip()

    @staticmethod
    def validate_url(url: str) -> bool:
        """Robust URL validation."""
        pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return bool(pattern.match(url))

security_gate = SecurityManager()
