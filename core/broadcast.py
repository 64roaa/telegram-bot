import asyncio
import logging
from telegram.ext import Application
from telegram.error import Forbidden, RetryAfter, TelegramError

logger = logging.getLogger("Amanteech.Core.Broadcast")

class BroadcastEngine:
    def __init__(self, app: Application, max_concurrent=30):
        self.app = app
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.stats = {"success": 0, "failed": 0, "blocked": 0}

    async def _send_safe(self, chat_id, text, **kwargs):
        """Atomic send operation with retry and error tracking."""
        async with self.semaphore:
            try:
                await self.app.bot.send_message(chat_id, text, **kwargs)
                self.stats["success"] += 1
                return True
            except Forbidden:
                self.stats["blocked"] += 1
                logger.warning(f"User {chat_id} blocked the bot.")
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after)
                return await self._send_safe(chat_id, text, **kwargs)
            except TelegramError as e:
                self.stats["failed"] += 1
                logger.error(f"Failed to send to {chat_id}: {e}")
            return False

    async def broadcast(self, user_ids, text, **kwargs):
        """High-performance concurrent broadcast."""
        self.stats = {"success": 0, "failed": 0, "blocked": 0}
        logger.info(f"🚀 Starting broadcast to {len(user_ids)} users...")
        
        tasks = [self._send_safe(uid, text, **kwargs) for uid in user_ids]
        await asyncio.gather(*tasks)
        
        logger.info(f"✅ Broadcast finished. Stats: {self.stats}")
        return self.stats
