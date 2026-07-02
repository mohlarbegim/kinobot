"""
Jarayonlararo cache invalidatsiyasi - Redis pub/sub (SUBSCRIBE/LISTEN tomoni).

Bot jarayonida ishlaydigan background task. apps/core/cache_bus.py PUBLISH qilgan
xabarlarni tinglab, tegishli in-process cache'ni tozalaydi. Shu tarzda Django admin
veb-panelidan qilingan o'zgartirishlar botga (TTL kutmasdan) darhol yetadi.

Redis sozlanmagan bo'lsa - darhol chiqadi (no-op) va tizim eski TTL xatti-harakatiga
qaytadi.
"""
import asyncio
import json
import logging

from apps.core.cache_bus import CHANNEL, redis_enabled

logger = logging.getLogger(__name__)


def _apply_invalidation(payload: dict) -> None:
    """Kelgan xabarga ko'ra tegishli in-process cache'ni tozalash (bot jarayonida)."""
    from bot.middlewares.database import (
        clear_user_cache, clear_settings_cache, clear_admin_cache,
    )
    from bot.middlewares.subscription import (
        clear_subscription_cache, clear_channels_cache,
    )

    kind = payload.get('kind')
    if kind == 'user':
        user_id = payload.get('id')
        clear_user_cache(user_id)
        clear_subscription_cache(user_id)
    elif kind == 'user_all':
        clear_user_cache()
        clear_subscription_cache()
    elif kind == 'settings':
        clear_settings_cache()
    elif kind == 'channels':
        clear_channels_cache()
        clear_subscription_cache()  # kanal o'zgardi -> barcha userlar qayta tekshirilsin
    elif kind == 'admin':
        clear_admin_cache(payload.get('id'))
    else:
        logger.debug(f"Noma'lum invalidatsiya turi: {kind}")


async def run_invalidation_listener() -> None:
    """Redis kanalini tinglab, cache invalidatsiyasini qo'llaydi (bot background task).

    Ulanish uzilsa qayta ulanishga urinadi. Redis yo'q bo'lsa darhol chiqadi (no-op).
    Hech qachon botni buzmaydi - barcha xatolar ushlanadi.
    """
    if not redis_enabled():
        logger.info("Cache invalidation listener: Redis sozlanmagan, o'tkazib yuborildi.")
        return

    import os
    import redis.asyncio as aioredis

    url = os.getenv('REDIS_URL')
    while True:
        client = None
        try:
            client = aioredis.from_url(url)
            pubsub = client.pubsub()
            await pubsub.subscribe(CHANNEL)
            logger.info(f"Cache invalidation listener ishga tushdi (kanal: {CHANNEL})")
            async for message in pubsub.listen():
                if message.get('type') != 'message':
                    continue
                try:
                    raw = message['data']
                    if isinstance(raw, (bytes, bytearray)):
                        raw = raw.decode('utf-8')
                    payload = json.loads(raw)
                    if payload.get('kind') == 'broadcast':
                        # Dashboard'dan ishga tushirilgan xabar yuborish -> alohida task
                        from bot.utils.broadcast_sender import send_broadcast
                        bid = payload.get('id')
                        if bid is not None:
                            asyncio.create_task(send_broadcast(bid))
                    else:
                        _apply_invalidation(payload)
                except Exception as e:
                    logger.warning(f"Invalidatsiya xabarini qayta ishlashda xato: {e}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Invalidation listener xatosi: {e}. 5s dan keyin qayta ulanadi...")
            await asyncio.sleep(5)
        finally:
            if client is not None:
                try:
                    await client.aclose()
                except Exception:
                    pass
