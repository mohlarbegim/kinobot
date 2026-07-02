from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from cachetools import TTLCache


class ThrottlingMiddleware(BaseMiddleware):
    """Spam himoya middleware"""

    def __init__(self, rate_limit: float = 0.5):
        self.rate_limit = rate_limit
        self.cache = TTLCache(maxsize=10000, ttl=rate_limit)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id

            if user_id in self.cache:
                # Rate limit
                return

            self.cache[user_id] = True

        return await handler(event, data)
