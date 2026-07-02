"""
Dashboard'dan (web) ishga tushirilgan broadcast'larni bot jarayonida yuborish.

Oqim: web `/api/broadcasts/` da Broadcast yozuvini yaratadi va Redis orqali
`{kind:'broadcast', id:<id>}` signalini yuboradi -> bot cache_listener buni ushlaydi
va shu yerdagi send_broadcast() ni asyncio task sifatida ishga tushiradi. Yuborish
botning o'z aiogram instance'i orqali (HTML fallback + Telegram rate-limit) bajariladi.
Progress DB'ga yozib boriladi, shunда dashboard jonli kuzatadi.
"""
import asyncio
import logging

from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

# Bir vaqtda / takroriy signalda bir broadcast ikki marta yuborilmasligi uchun guard
_in_progress: set = set()

# Telegram ~30 msg/s ruxsat beradi; xavfsizlik uchun ~20/s
_SEND_DELAY = 0.05


@sync_to_async
def _load_broadcast(bid: int):
    from apps.core.models import Broadcast
    try:
        b = Broadcast.objects.get(id=bid)
    except Broadcast.DoesNotExist:
        return None
    return {
        'id': b.id,
        'target': b.target,
        'content_type': b.content_type,
        'text': b.text,
        'file_id': b.file_id,
        'is_advertisement': b.is_advertisement,
        'is_completed': b.is_completed,
    }


@sync_to_async
def _get_user_ids(target: str, is_ad: bool):
    from django.utils import timezone
    from apps.users.models import User

    qs = User.objects.filter(is_banned=False)
    now = timezone.now()
    if target == 'premium':
        qs = qs.filter(is_premium=True, premium_expires__gt=now)
    elif target == 'regular':
        qs = qs.exclude(is_premium=True, premium_expires__gt=now)
    if is_ad:
        # Reklama premium foydalanuvchilarga bormaydi
        qs = qs.exclude(is_premium=True, premium_expires__gt=now)
    return list(qs.values_list('user_id', flat=True))


@sync_to_async
def _set_total(bid: int, total: int):
    from apps.core.models import Broadcast
    Broadcast.objects.filter(id=bid).update(total_users=total)


@sync_to_async
def _update_progress(bid: int, sent: int, failed: int):
    from apps.core.models import Broadcast
    Broadcast.objects.filter(id=bid).update(sent_count=sent, failed_count=failed)


@sync_to_async
def _complete(bid: int, sent: int, failed: int):
    from django.utils import timezone
    from apps.core.models import Broadcast
    Broadcast.objects.filter(id=bid).update(
        sent_count=sent, failed_count=failed,
        is_completed=True, completed_at=timezone.now(),
    )


async def send_broadcast(broadcast_id: int) -> None:
    """Broadcast'ni barcha maqsadli foydalanuvchilarga yuborish (bot jarayonida)."""
    if broadcast_id in _in_progress:
        logger.info(f"Broadcast #{broadcast_id} allaqachon yuborilmoqda, o'tkazib yuborildi.")
        return
    _in_progress.add(broadcast_id)
    try:
        from bot.loader import bot
        from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

        b = await _load_broadcast(broadcast_id)
        if not b:
            logger.warning(f"Broadcast #{broadcast_id} topilmadi.")
            return
        if b['is_completed']:
            logger.info(f"Broadcast #{broadcast_id} allaqachon yakunlangan.")
            return

        user_ids = await _get_user_ids(b['target'], b['is_advertisement'])
        await _set_total(broadcast_id, len(user_ids))
        logger.info(f"Broadcast #{broadcast_id} boshlandi: {len(user_ids)} ta oluvchi.")

        ctype = b['content_type']
        text = b['text'] or ''
        file_id = b['file_id'] or ''

        async def _deliver(uid, parse_mode="__default__"):
            kwargs = {} if parse_mode == "__default__" else {'parse_mode': parse_mode}
            if ctype == 'text':
                await bot.send_message(uid, text, **kwargs)
            elif ctype == 'photo':
                await bot.send_photo(uid, file_id, caption=text, **kwargs)
            elif ctype == 'video':
                await bot.send_video(uid, file_id, caption=text, **kwargs)
            elif ctype == 'document':
                await bot.send_document(uid, file_id, caption=text, **kwargs)
            else:
                await bot.send_message(uid, text, **kwargs)

        sent = 0
        failed = 0
        for uid in user_ids:
            try:
                try:
                    await _deliver(uid)
                except TelegramBadRequest:
                    # HTML tahlili muvaffaqiyatsiz -> oddiy matn sifatida qayta yuborish
                    await _deliver(uid, parse_mode=None)
                sent += 1
            except TelegramRetryAfter as e:
                # Flood limit -> kutamiz va shu userga qayta urinamiz
                await asyncio.sleep(e.retry_after)
                try:
                    await _deliver(uid, parse_mode=None)
                    sent += 1
                except Exception:
                    failed += 1
            except Exception:
                failed += 1

            if (sent + failed) % 20 == 0:
                await _update_progress(broadcast_id, sent, failed)
            await asyncio.sleep(_SEND_DELAY)

        await _complete(broadcast_id, sent, failed)
        logger.info(f"Broadcast #{broadcast_id} yakunlandi: {sent} yuborildi, {failed} xato.")
    except Exception as e:
        logger.error(f"Broadcast #{broadcast_id} yuborishda xato: {e}")
    finally:
        _in_progress.discard(broadcast_id)
