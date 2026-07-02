"""
Jarayonlararo cache invalidatsiyasi - Redis pub/sub (PUBLISH tomoni).

Muammo: bot (aiogram) va veb (gunicorn/Django admin) ALOHIDA jarayonlar bo'lib, har
birida o'z in-process cache'i (TTLCache) bor. Django admin panelidan settings / user /
kanal o'zgartirilganda bot jarayonining cache'ini bevosita tozalab bo'lmaydi.

Yechim: yozuvchi tomon Redis kanaliga "invalidate" xabari PUBLISH qiladi; bot esa shu
kanalni tinglab (bot/utils/cache_listener.py), tegishli in-process cache'ini tozalaydi.
Push modeli - har so'rovda qo'shimcha Redis o'qishi yo'q.

Redis sozlanmagan bo'lsa (USE_REDIS=False yoki REDIS_URL yo'q) - hammasi no-op bo'ladi
va tizim eski TTL-asosidagi xatti-harakatga qaytadi. Bu modul faqat standart kutubxona
va (ixtiyoriy) redis ga bog'liq - bot ichki modullarini import qilmaydi.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

CHANNEL = 'kinobot:cache_invalidate'

_sync_client = None  # lazy sync redis client (publish uchun qayta ishlatiladi)


def redis_enabled() -> bool:
    return (
        os.getenv('USE_REDIS', 'False').lower() in ('true', '1', 'yes')
        and bool(os.getenv('REDIS_URL'))
    )


def _get_sync_client():
    global _sync_client
    if _sync_client is None:
        import redis  # redis>=5.0 requirements'da bor
        _sync_client = redis.from_url(os.getenv('REDIS_URL'))
    return _sync_client


def publish_invalidation(kind: str, **data) -> None:
    """Cache invalidatsiya xabarini e'lon qilish (sync - Django signal/handler/admin'dan).

    Xatoga chidamli: Redis yo'q yoki ishlamasa - jimgina o'tadi (yozuvchi jarayonni
    hech qachon buzmaydi).
    """
    if not redis_enabled():
        return
    try:
        payload = json.dumps({'kind': kind, **data})
        _get_sync_client().publish(CHANNEL, payload)
    except Exception as e:
        logger.debug(f"Cache invalidatsiya publish xatosi: {e}")
        # Ulanish buzilgan bo'lsa keyingi safar qayta yaratamiz
        global _sync_client
        _sync_client = None
