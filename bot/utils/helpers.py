from datetime import datetime
from typing import Optional
from html import escape as _html_escape
from html import unescape as _html_unescape
import asyncio
import logging
import re

from apps.users.models import User
from apps.channels.models import Channel
from asgiref.sync import sync_to_async
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter

logger = logging.getLogger(__name__)


def esc(value) -> str:
    """HTML parse_mode uchun xavfsiz matn (formatlash YO'Q).

    ISHONCHSIZ matn uchun: foydalanuvchi ismi (full_name), username, qidiruv so'rovi,
    kino so'rovi nomi, user kiritgan kod. Bularda '&', '<', '>' escape qilinadi.
    Foydalanuvchi o'z ismini "<b>x" qilib qo'yishi mumkin - shablonlar uni xom
    almashtiradi, shuning uchun bu yerdagi escape YAGONA himoya. OLIB TASHLAMANG.

    Admin yozgan matn (kino nomi/tavsifi, e'lon) uchun safe_html() ishlating -
    u bold/italic'ni saqlaydi.
    """
    if value is None:
        return ""
    return _html_escape(str(value), quote=False)


# Telegram HTML parse_mode qo'llab-quvvatlaydigan teglar (rasmiy ro'yxat).
# <a href> alohida ishlanadi (unda atribut bor).
_TG_TAGS = 'b|strong|i|em|u|ins|s|strike|del|code|pre|tg-spoiler|blockquote'
_TG_TAG_RE = re.compile(rf'&lt;(/?)({_TG_TAGS})&gt;', re.IGNORECASE)
_TG_A_OPEN_RE = re.compile(r'&lt;a href="([^"<>]*)"&gt;', re.IGNORECASE)
_TG_A_CLOSE_RE = re.compile(r'&lt;/a&gt;', re.IGNORECASE)


def safe_html(value) -> str:
    """ADMIN yozgan matnni formatlashni SAQLAB, xavfsiz HTML'ga aylantirish.

    Avval hamma narsa escape qilinadi, so'ng Telegram qo'llab-quvvatlaydigan
    teglargina qaytariladi (whitelist). Natijada:
      - <b>qalin</b> / <i>qiya</i> ISHLAYDI (ilgari esc() ularni matnga aylantirardi),
      - kino nomidagi tasodifiy '&' yoki '<' Telegram "can't parse entities"
        xatosini BERMAYDI (xom qoldirsak berardi - kino yuborishда fallback yo'q).

    Faqat ISHONCHLI (admin kiritgan) maydonlar uchun: kino nomi, tavsif, e'lon matni.
    Foydalanuvchi kiritgan matnga esc() ishlating.
    """
    if value is None:
        return ""
    txt = _html_escape(str(value), quote=False)
    txt = _TG_TAG_RE.sub(r'<\1\2>', txt)
    txt = _TG_A_OPEN_RE.sub(lambda m: f'<a href="{m.group(1).replace("&amp;", "&")}">', txt)
    txt = _TG_A_CLOSE_RE.sub('</a>', txt)
    return txt


def html_text_of(message) -> str:
    """Xabar matnini (yoki caption'ini) FORMATLASH bilan olish.

    message.text Telegram formatlashini YO'QOTADI - u sof matn qaytaradi, shuning
    uchun admin Telegram'da qalin/qiya qilib yozgan matn botda oddiy bo'lib chiqardi.
    message.html_text entity'larni HTML teglarga aylantiradi (<b>, <i>, <a href> ...),
    bot esa HTML parse_mode bilan yuboradi - formatlash saqlanadi.

    aiogram matn ham caption ham bo'lmasa TypeError beradi - himoyalangan.
    """
    try:
        return message.html_text
    except (TypeError, AttributeError):
        return message.text or message.caption or ""


def to_plain(value, limit: int = 200) -> str:
    """HTML matnni SOF matnga aylantirish (Telegram alert uchun).

    callback.answer(show_alert=True) HTML'ni QO'LLAB-QUVVATLAMAYDI va ~200 belgi
    bilan cheklangan. Shablon HTML bilan yozilgan bo'lsa, teglar alertда xom
    ko'rinib qolmasligi uchun olib tashlanadi va matn qisqartiriladi.
    """
    if value is None:
        return ""
    txt = re.sub(r'<[^>]+>', '', str(value))
    txt = _html_unescape(txt)
    txt = re.sub(r'\n{2,}', '\n', txt).strip()
    return txt[:limit]


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
def get_message_text(message_type: str, **kwargs) -> str:
    """Admin tahrirlaydigan xabar shablonini olish (MessageTemplate).

    Placeholder qiymatlarini {key} bo'yicha almashtiradi. Shablon topilmasa
    _get_default_message'ga tushadi. HTML parse_mode ishlatilgani uchun
    foydalanuvchi kiritgan qiymatlar (ism, kino nomi) CHAQIRUVDAN OLDIN esc()
    bilan uzatilishi kerak (get_message oddiy str.replace qiladi).
    """
    from apps.core.models import MessageTemplate
    return MessageTemplate.get_message(message_type, **kwargs)


@sync_to_async
def get_channel_by_tg_id(tg_chat_id: int):
    """Telegram chat id bo'yicha aktiv majburiy kanalni topish (join request uchun)."""
    return Channel.objects.filter(channel_id=tg_chat_id, is_active=True).first()


@sync_to_async
def record_join_request(user_id: int, channel_pk: int, username: str = None, full_name: str = None):
    """Foydalanuvchining yopiq kanalga qo'shilish so'rovini yozish.

    User bazada bo'lmasa YARATAMIZ: /start bosmasdan turib kanalga zayavka tashlagan
    foydalanuvchi (masalan botga emas, kanalga birinchi kelgan) ham hisobga olinishi
    kerak. Ilgari bunday user'ning so'rovi jimgina tashlab yuborilardi va u keyin
    botda abadiy bloklanib qolardi (zayavkani qayta yubora olmaydi).

    Takroriy so'rovda created_at YANGILANADI (get_or_create eskisini qoldirardi -
    bekor qilib qayta yuborgan user eski vaqt bilan qolib ketardi).
    """
    from apps.channels.models import ChannelJoinRequest
    from django.utils import timezone

    user, _ = User.objects.get_or_create(
        user_id=user_id,
        defaults={'username': username, 'full_name': full_name or ''},
    )
    ChannelJoinRequest.objects.update_or_create(
        channel_id=channel_pk, user=user,
        defaults={'created_at': timezone.now()},
    )


@sync_to_async
def get_join_requested_ids(user_id: int) -> set:
    """Foydalanuvchi qo'shilish so'rovi yuborgan kanallar (Channel PK) to'plami.

    JOIN_REQUEST_TTL_DAYS = 0 (standart) -> MUDDATSIZ: barcha so'rovlar hisobga olinadi.
    Musbat qiymatда faqat shu kun ichidagi so'rovlar hisobga olinadi (bekor qilingan/
    rad etilgan so'rov Telegram signal bermaydi, shuning uchun muddatdan keyin
    get_chat_member qayta tekshiradi).
    """
    from datetime import timedelta
    from django.utils import timezone
    from apps.channels.models import ChannelJoinRequest
    from bot.constants import JOIN_REQUEST_TTL_DAYS

    qs = ChannelJoinRequest.objects.filter(user__user_id=user_id)
    if JOIN_REQUEST_TTL_DAYS > 0:
        cutoff = timezone.now() - timedelta(days=JOIN_REQUEST_TTL_DAYS)
        qs = qs.filter(created_at__gte=cutoff)
    return set(qs.values_list('channel_id', flat=True))


async def compute_missing_channels(bot, user_id: int, channels: list) -> list:
    """Bajarilmagan majburiy kanallar ro'yxati (Telegram avval, Instagram oxirida).

    Handler'dagi check_subscription va SubscriptionMiddleware._check_subscription
    IKKALASI shu funksiyani chaqiradi - mantiq bitta joyda (ilgari ikki nusxa bo'lib,
    har o'zgarish ikki faylда qo'lда sinxronlanardi). `channels` chaqiruvchi tomonidan
    beriladi (handler get_active_channels; middleware keshlangan ro'yxat).

    - Telegram (is_checkable): get_chat_member; 'left'/'kicked' bo'lsa yopiq kanal
      qo'shilish so'rovi bor-yo'qligi tekshiriladi. get_chat_member xatosi -> fail-open
      (kanal o'tkaziladi). DB lookup try'dan tashqarida - DB xatosi fail-open QILMAYDI.
    - Instagram/tashqi (non-checkable): "obuna bo'ldim" tasdig'i (ChannelSubscription).
    """
    from aiogram.exceptions import TelegramBadRequest

    checkable_missing = []
    noncheckable_missing = []
    confirmed_ids = None   # lazy - Instagram tasdiqlari
    requested_ids = None   # lazy - yopiq kanal join request'lari

    for channel in channels:
        if channel.is_checkable:
            try:
                member = await bot.get_chat_member(channel.channel_id, user_id)
                status = member.status
            except TelegramBadRequest as e:
                logger.warning(f"Obunani tekshirib bo'lmadi (channel_id={channel.channel_id}): {e}")
                continue
            except Exception as e:
                logger.warning(f"Obunani tekshirishda kutilmagan xato (channel_id={channel.channel_id}): {e}")
                continue

            if status in ['left', 'kicked']:
                if requested_ids is None:
                    requested_ids = await get_join_requested_ids(user_id)
                if channel.id not in requested_ids:
                    checkable_missing.append(channel)
        else:
            if confirmed_ids is None:
                confirmed_ids = await get_confirmed_channel_ids(user_id)
            if channel.id not in confirmed_ids:
                noncheckable_missing.append(channel)

    return checkable_missing + noncheckable_missing


@sync_to_async
def remove_channel_membership(user_id: int, channel_pk: int):
    """
    Foydalanuvchi kanaldan chiqib ketganda (left/kicked) uning shu kanalga oid
    qo'shilish so'rovi va obuna yozuvlarini o'chiradi.

    Shundan so'ng keyingi tekshiruvda kanal "bajarilmagan" bo'lib qaytadi va bot
    qayta obuna so'raydi (chat_member update orqali chaqiriladi).
    """
    from apps.channels.models import ChannelJoinRequest, ChannelSubscription
    try:
        user = User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return
    ChannelJoinRequest.objects.filter(channel_id=channel_pk, user=user).delete()
    ChannelSubscription.objects.filter(channel_id=channel_pk, user=user).delete()


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
