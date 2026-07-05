import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from asgiref.sync import sync_to_async
from cachetools import TTLCache
from django.conf import settings

logger = logging.getLogger(__name__)

# Cache for channels and user subscriptions
_channels_cache = TTLCache(maxsize=1, ttl=300)
_subscription_cache = TTLCache(maxsize=5000, ttl=30)


class SubscriptionMiddleware(BaseMiddleware):
    """Majburiy obuna middleware - optimized"""

    SKIP_COMMANDS = {'/start', '/help', '/admin'}
    SKIP_CALLBACKS = {'check_subscription', 'admin:panel', 'admin:stats', 'admin:movies',
                      'admin:add_movie', 'admin:channels', 'admin:users', 'admin:payments',
                      'admin:settings', 'admin:broadcast'}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        db_user = data.get('db_user')

        # Get user_id
        user_id = None
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            user_id = event.from_user.id

        # Admin users skip subscription check
        if user_id and user_id in settings.ADMINS:
            return await handler(event, data)

        # Premium users skip
        if db_user and db_user.is_premium_active:
            return await handler(event, data)

        # Skip commands/callbacks
        if isinstance(event, Message):
            parts = event.text.split() if event.text else []
            if parts and parts[0] in self.SKIP_COMMANDS:
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            if event.data and (
                event.data in self.SKIP_CALLBACKS
                or event.data.startswith('admin:')
            ):
                return await handler(event, data)

        if user_id:
            # Check subscription with cache
            cache_key = f"sub_{user_id}"

            if cache_key in _subscription_cache:
                not_subscribed = _subscription_cache[cache_key]
            else:
                bot: Bot = data['bot']
                not_subscribed = await self._check_subscription(bot, user_id)
                _subscription_cache[cache_key] = not_subscribed

            if not_subscribed:
                from bot.keyboards import channels_kb, subscription_prompt_text
                text = subscription_prompt_text(not_subscribed)

                if isinstance(event, Message):
                    await event.answer(text, reply_markup=channels_kb(not_subscribed))
                elif isinstance(event, CallbackQuery):
                    # event.message eski/kirib bo'lmaydigan xabar bo'lsa None bo'lishi mumkin
                    if event.message:
                        await event.message.answer(text, reply_markup=channels_kb(not_subscribed))
                    await event.answer()
                return

        return await handler(event, data)

    async def _check_subscription(self, bot: Bot, user_id: int) -> list:
        """
        Obunani tekshirish. Handlerdagi check_subscription bilan bir xil.

        - Telegram (checkable): MAJBURIY. get_chat_member; yopiq kanalga qo'shilish
          so'rovi (chat_join_request) yuborgan bo'lsa ham o'tadi.
        - Instagram / bot / tashqi (non-checkable): MAJBURIY, "obuna bo'ldim" tasdig'i
          (ikki tashrif) orqali.

        Bajarilmagan barcha kanallar birga qaytadi (Telegram + Instagram).
        """
        from bot.utils import get_confirmed_channel_ids, get_join_requested_ids

        channels = await self._get_channels_cached()
        checkable_missing = []
        noncheckable_missing = []
        confirmed_ids = None  # lazy - Instagram tasdiqlari
        requested_ids = None  # lazy - yopiq kanal join request'lari

        for channel in channels:
            if channel.is_checkable:
                # FAQAT get_chat_member (Telegram) xatosi fail-open bo'ladi. DB lookup
                # (get_join_requested_ids) try'dan TASHQARIDA - DB xatosi fail-open
                # qilmasligi kerak (aks holda DB uzilishida hamma gate'dan o'tib ketardi;
                # non-checkable shoxidagi get_confirmed_channel_ids ham propagate qiladi).
                try:
                    member = await bot.get_chat_member(channel.channel_id, user_id)
                    status = member.status
                except TelegramBadRequest as e:
                    # Bot kanalni tekshira olmadi (admin emas / topilmadi) -> fail-open.
                    logger.warning(f"Obunani tekshirib bo'lmadi (channel_id={channel.channel_id}): {e}")
                    continue
                except Exception as e:
                    # TelegramForbiddenError ("bot is not a member...") va boshqalar ham fail-open.
                    logger.warning(f"Obunani tekshirishda kutilmagan xato (channel_id={channel.channel_id}): {e}")
                    continue

                if status in ['left', 'kicked']:
                    if requested_ids is None:
                        requested_ids = await get_join_requested_ids(user_id)
                    if channel.id not in requested_ids:
                        checkable_missing.append(channel)
            else:
                # Instagram / bot / tashqi - tasdiq (ikki tashrif) orqali
                if confirmed_ids is None:
                    confirmed_ids = await get_confirmed_channel_ids(user_id)
                if channel.id not in confirmed_ids:
                    noncheckable_missing.append(channel)

        return checkable_missing + noncheckable_missing

    async def _get_channels_cached(self):
        """Get channels with cache"""
        if 'channels' in _channels_cache:
            return _channels_cache['channels']

        channels = await self._get_channels_db()
        _channels_cache['channels'] = channels
        return channels

    @sync_to_async
    def _get_channels_db(self):
        from apps.channels.models import Channel
        return list(Channel.objects.filter(is_active=True).order_by('order'))


def clear_subscription_cache(user_id: int = None):
    """Clear subscription cache"""
    if user_id:
        _subscription_cache.pop(f"sub_{user_id}", None)
    else:
        _subscription_cache.clear()


def clear_channels_cache():
    """Clear channels cache"""
    _channels_cache.clear()
