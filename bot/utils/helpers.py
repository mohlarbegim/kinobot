from datetime import datetime
from typing import Optional
from html import escape as _html_escape
import asyncio
import logging

from apps.users.models import User
from apps.channels.models import Channel
from asgiref.sync import sync_to_async
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter

logger = logging.getLogger(__name__)


def esc(value) -> str:
    """HTML parse_mode uchun xavfsiz matn.

    Foydalanuvchi/admin kiritgan matnni (ism, kino nomi, tavsif) HTML xabarga
    joylashdan oldin '&', '<', '>' belgilarini escape qiladi. Aks holda ism ichida
    '&' yoki '<' bo'lsa Telegram "can't parse entities" xatosini beradi.
    """
    if value is None:
        return ""
    return _html_escape(str(value), quote=False)


@sync_to_async
def get_or_create_user(user_id: int, username: Optional[str], full_name: str, referral_code: Optional[str] = None) -> User:
    """Foydalanuvchini olish yoki yaratish"""
    from apps.core.models import BotSettings
    from django.utils import timezone
    from datetime import timedelta

    user, created = User.objects.get_or_create(
        user_id=user_id,
        defaults={
            'username': username,
            'full_name': full_name,
        }
    )

    if not created:
        user.username = username
        user.full_name = full_name
        user.save(update_fields=['username', 'full_name', 'last_active'])
    elif referral_code and created:
        # Referal bog'lash va bonus berish
        try:
            referrer = User.objects.get(referral_code=referral_code)
            if referrer.user_id != user_id:
                user.referred_by = referrer
                user.save(update_fields=['referred_by'])

                # Referrer'ga bonus berish
                settings = BotSettings.get_settings()
                if settings.referral_active and settings.referral_bonus > 0:
                    bonus_days = settings.referral_bonus
                    if referrer.free_trial_expires:
                        if referrer.free_trial_expires > timezone.now():
                            referrer.free_trial_expires += timedelta(days=bonus_days)
                        else:
                            referrer.free_trial_expires = timezone.now() + timedelta(days=bonus_days)
                    else:
                        referrer.free_trial_expires = timezone.now() + timedelta(days=bonus_days)
                    referrer.save(update_fields=['free_trial_expires'])

                    # Taklif qiluvchiga xabar berish uchun ma'lumotni obyektga biriktiramiz
                    # (bu yerdan Telegram xabar yubora olmaymiz - sync kontekst; cmd_start yuboradi).
                    user._referral_bonus = {
                        'referrer_id': referrer.user_id,
                        'bonus_days': bonus_days,
                        'referrals_count': referrer.referrals.count(),
                    }

        except User.DoesNotExist:
            pass

    return user


@sync_to_async
def get_user(user_id: int) -> Optional[User]:
    """Foydalanuvchini olish"""
    try:
        return User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return None


@sync_to_async
def update_user_activity(user_id: int):
    """Foydalanuvchi faolligini yangilash"""
    from django.utils import timezone
    # USE_TZ=True bo'lgani uchun timezone-aware vaqt ishlatamiz (datetime.now() naive
    # bo'lib, last_active ni noto'g'ri (offset bilan) saqlagan bo'lardi).
    User.objects.filter(user_id=user_id).update(last_active=timezone.now())


@sync_to_async
def get_active_channels():
    """Aktiv kanallarni olish"""
    return list(Channel.objects.filter(is_active=True).order_by('order'))


@sync_to_async
def get_checkable_channels():
    """Tekshirish mumkin bo'lgan kanallarni olish (Channel.is_checkable bilan bir xil mezon)."""
    return list(Channel.objects.filter(
        is_active=True,
        channel_type__in=Channel.CHECKABLE_TYPES,
        channel_id__isnull=False,
    ).order_by('order'))


def format_number(num: int) -> str:
    """Raqamni formatlash"""
    return f"{num:,}".replace(",", " ")


def format_datetime(dt: datetime) -> str:
    """Sanani formatlash"""
    return dt.strftime("%d.%m.%Y %H:%M")


def format_date(dt: datetime) -> str:
    """Sanani formatlash (faqat kun)"""
    return dt.strftime("%d.%m.%Y")


@sync_to_async
def update_user_joined_channel(user_id: int, channel_id: int):
    """Foydalanuvchi qaysi kanal orqali kelganini yangilash"""
    try:
        user = User.objects.get(user_id=user_id)
        # Faqat birinchi marta yozish
        if not user.joined_from_channel_id:
            user.joined_from_channel_id = channel_id
            user.save(update_fields=['joined_from_channel_id'])
    except User.DoesNotExist:
        pass


@sync_to_async
def record_channel_subscriptions(user_id: int, channel_ids: list):
    """Foydalanuvchining kanal obunalarini yozish"""
    from apps.channels.models import ChannelSubscription

    try:
        user = User.objects.get(user_id=user_id)

        for channel_id in channel_ids:
            # get_or_create - takroriy yozilmasligi uchun
            ChannelSubscription.objects.get_or_create(
                channel_id=channel_id,
                user=user
            )
    except User.DoesNotExist:
        pass


@sync_to_async
def get_confirmed_channel_ids(user_id: int) -> set:
    """
    Foydalanuvchi tasdiqlagan kanallar (Channel PK) to'plami.

    Instagram / bot / tashqi kanallar Telegram API bilan tekshirib bo'lmaydi,
    shuning uchun foydalanuvchi "Obuna bo'ldim" tugmasini bosib tasdiqlaydi va
    ChannelSubscription yozuvi yaratiladi. Shu yozuvlar shu yerda qaytadi.
    """
    from apps.channels.models import ChannelSubscription
    return set(
        ChannelSubscription.objects
        .filter(user__user_id=user_id)
        .values_list('channel_id', flat=True)
    )


@sync_to_async
def get_channel_by_tg_id(tg_chat_id: int):
    """Telegram chat id bo'yicha aktiv majburiy kanalni topish (join request uchun)."""
    return Channel.objects.filter(channel_id=tg_chat_id, is_active=True).first()


@sync_to_async
def record_join_request(user_id: int, channel_pk: int):
    """Foydalanuvchining yopiq kanalga qo'shilish so'rovini yozish."""
    from apps.channels.models import ChannelJoinRequest
    try:
        user = User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return
    ChannelJoinRequest.objects.get_or_create(channel_id=channel_pk, user=user)


@sync_to_async
def get_join_requested_ids(user_id: int) -> set:
    """Foydalanuvchi qo'shilish so'rovi yuborgan kanallar (Channel PK) to'plami."""
    from apps.channels.models import ChannelJoinRequest
    return set(
        ChannelJoinRequest.objects
        .filter(user__user_id=user_id)
        .values_list('channel_id', flat=True)
    )


@sync_to_async
def get_channel_subscription_count(channel_pk: int) -> int:
    """Kanal obunachilari sonini olish"""
    from apps.channels.models import ChannelSubscription
    return ChannelSubscription.objects.filter(channel_id=channel_pk).count()


async def safe_execute(coro_factory, max_retries: int = 3, delay: float = 1.0):
    """
    Tarmoq xatolarida qayta urinish bilan xavfsiz bajarish.

    MUHIM: coroutine obyektini emas, uni YARATADIGAN callable (factory) uzatiladi.
    Coroutine faqat bir marta await qilinadi, shuning uchun har urinishда yangi
    coroutine yaratilishi kerak (aks holda "cannot reuse already awaited coroutine").

    Foydalanish:
        await safe_execute(lambda: message.answer("Salom!"))
        await safe_execute(lambda: callback.message.edit_text("Yangi matn"))

    Args:
        coro_factory: Har chaqirilganda yangi coroutine qaytaradigan callable
        max_retries: Maksimal urinishlar soni (default: 3)
        delay: Urinishlar orasidagi kutish (soniyalarda)

    Returns:
        Coroutine natijasi yoki None (agar barcha urinishlar muvaffaqiyatsiz bo'lsa)
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await coro_factory()
        except TelegramRetryAfter as e:
            # Flood limit - belgilangan vaqt kutish
            logger.warning(f"Flood limit: {e.retry_after}s kutish (urinish {attempt + 1}/{max_retries})")
            await asyncio.sleep(e.retry_after)
        except TelegramNetworkError as e:
            # Tarmoq xatosi - qayta urinish
            last_exception = e
            logger.warning(f"Tarmoq xatosi: {e} (urinish {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                await asyncio.sleep(delay * (attempt + 1))  # Exponential backoff
        except Exception as e:
            # Boshqa xatolar - qayta urinmaslik
            logger.error(f"Xato: {e}")
            raise

    logger.error(f"Barcha urinishlar muvaffaqiyatsiz: {last_exception}")
    return None
