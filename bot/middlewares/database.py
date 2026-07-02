import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings as django_settings
from cachetools import TTLCache

from bot.constants import (
    CACHE_TTL_USER, CACHE_TTL_SETTINGS, CACHE_TTL_ADMIN,
    CACHE_MAX_USERS, CACHE_MAX_ADMINS
)

logger = logging.getLogger(__name__)

# Local cache for faster access - constants dan qiymatlar
_user_cache = TTLCache(maxsize=CACHE_MAX_USERS, ttl=CACHE_TTL_USER)
_settings_cache = TTLCache(maxsize=1, ttl=CACHE_TTL_SETTINGS)
_admin_cache = TTLCache(maxsize=CACHE_MAX_ADMINS, ttl=CACHE_TTL_ADMIN)


class DatabaseMiddleware(BaseMiddleware):
    """Database middleware - optimized for speed"""

    # /start va /help buyruqlari har doim ishlashi kerak
    ALWAYS_ALLOWED_COMMANDS = {'/start', '/help'}
    # Obuna tekshirish callback'i ham har doim ishlashi kerak
    ALWAYS_ALLOWED_CALLBACKS = {'check_subscription'}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user:
            # Fast settings check from cache
            settings = await self._get_settings_cached()

            # /start va /help har doim ishlashi kerak (bot o'chirilgan bo'lsa ham)
            is_allowed = False
            if isinstance(event, Message) and event.text:
                parts = event.text.split()
                cmd = parts[0] if parts else ''
                is_allowed = cmd in self.ALWAYS_ALLOWED_COMMANDS
            elif isinstance(event, CallbackQuery) and event.data:
                is_allowed = event.data in self.ALWAYS_ALLOWED_CALLBACKS

            if not settings.is_active and not is_allowed:
                # Admin tekshirish - adminlar bot o'chirilgan bo'lsa ham ishlata oladi
                is_admin = await self._is_admin_cached(user.id)
                if not is_admin:
                    msg = settings.maintenance_message or "Bot texnik ishlar sababli to'xtatilgan."
                    if isinstance(event, Message):
                        await event.answer(msg)
                    elif isinstance(event, CallbackQuery):
                        await event.answer(msg, show_alert=True)
                    return

            # Fast user check from cache
            db_user = await self._get_user_cached(user.id)

            if db_user:
                if db_user.is_banned:
                    ban_text = "⛔️ Siz botda bloklangansiz."
                    if db_user.ban_reason:
                        ban_text += f"\nSabab: {db_user.ban_reason}"
                    if isinstance(event, Message):
                        await event.answer(ban_text)
                    elif isinstance(event, CallbackQuery):
                        await event.answer(ban_text, show_alert=True)
                    return

                data['db_user'] = db_user

            data['bot_settings'] = settings

        return await handler(event, data)

    async def _get_user_cached(self, user_id: int):
        """Get user with local cache"""
        if user_id in _user_cache:
            return _user_cache[user_id]

        user = await self._get_user_db(user_id)
        if user:
            _user_cache[user_id] = user
        return user

    async def _get_settings_cached(self):
        """Get settings with local cache"""
        if 'settings' in _settings_cache:
            return _settings_cache['settings']

        settings = await self._get_settings_db()
        _settings_cache['settings'] = settings
        return settings

    async def _is_admin_cached(self, user_id: int) -> bool:
        """Check if user is admin with cache"""
        # Settings.ADMINS ro'yxatini tekshirish
        if user_id in django_settings.ADMINS:
            return True

        # Cache tekshirish
        if user_id in _admin_cache:
            return _admin_cache[user_id]

        # Database tekshirish
        is_admin = await self._check_admin_db(user_id)
        _admin_cache[user_id] = is_admin
        return is_admin

    @sync_to_async
    def _check_admin_db(self, user_id: int) -> bool:
        """Check if user is admin in database"""
        from apps.users.models import Admin
        return Admin.objects.filter(user__user_id=user_id).exists()

    @sync_to_async
    def _get_user_db(self, user_id: int):
        from apps.users.models import User
        try:
            return User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            return None

    @sync_to_async
    def _get_settings_db(self):
        from apps.core.models import BotSettings
        return BotSettings.get_settings()


def clear_user_cache(user_id: int = None):
    """Clear user cache"""
    if user_id:
        _user_cache.pop(user_id, None)
    else:
        _user_cache.clear()


def clear_settings_cache():
    """Clear settings cache"""
    _settings_cache.clear()


def clear_admin_cache(user_id: int = None):
    """Clear admin cache"""
    if user_id:
        _admin_cache.pop(user_id, None)
    else:
        _admin_cache.clear()
