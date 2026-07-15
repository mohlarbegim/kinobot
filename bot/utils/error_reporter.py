"""
Xatoliklarni Telegram kanaliga yuborish (bug kanali).

Botda yuz bergan xatolar settings.BUG_CHANNEL_ID kanaliga yuboriladi - shunda
xatolikni Railway loglaridan qidirmasdan darhol ko'rish mumkin.

Muhim qoidalar:
- HECH QACHON xato tashlamaydi. Bu global error handler ichidan chaqiriladi -
  bu yerdagi xato "xato ustiga xato" tsiklini boshlab yuborardi.
- Bir xil xato takrorlansa kanal spam bo'lmasligi uchun DEDUP qilinadi
  (bir xil xato ERROR_DEDUP_TTL soniya ichida faqat bir marta yuboriladi).
"""
import logging
import traceback
from html import escape

from cachetools import TTLCache
from django.conf import settings

logger = logging.getLogger(__name__)

# Bir xil xato shu muddat ichida qayta yuborilmaydi (spam oldini olish)
ERROR_DEDUP_TTL = 600  # 10 daqiqa
_recent_errors = TTLCache(maxsize=200, ttl=ERROR_DEDUP_TTL)

# Telegram xabar limiti 4096 - traceback undan uzun bo'lishi mumkin
MAX_TRACEBACK_CHARS = 2500


def _signature(exception: Exception) -> str:
    """Xatoning "o'ziga xos izi" - dedup uchun.

    Traceback'ning oxirgi kadri (fayl:qator) + xato turi. Xabar matni kirmaydi -
    aks holda har xil user_id bilan bir xil bug har safar yangi bo'lib ko'rinardi.
    """
    tb = exception.__traceback__
    last = None
    while tb is not None:
        last = tb
        tb = tb.tb_next
    if last is None:
        return f"{type(exception).__name__}"
    frame = last.tb_frame
    return f"{type(exception).__name__}:{frame.f_code.co_filename}:{last.tb_lineno}"


def _describe_update(update) -> str:
    """Update'dan foydali kontekst: kim, qayerda, nima yubordi."""
    if update is None:
        return "Update: yo'q"

    parts = []
    try:
        message = getattr(update, 'message', None)
        callback = getattr(update, 'callback_query', None)
        src = message or (callback.message if callback else None)
        from_user = None
        if message:
            from_user = message.from_user
        elif callback:
            from_user = callback.from_user

        if from_user:
            uname = f"@{from_user.username}" if from_user.username else "username yo'q"
            parts.append(f"👤 User: <code>{from_user.id}</code> ({escape(str(uname))})")

        if message and message.text:
            parts.append(f"💬 Matn: <code>{escape(message.text[:100])}</code>")
        elif callback and callback.data:
            parts.append(f"🔘 Callback: <code>{escape(str(callback.data)[:100])}</code>")

        if getattr(update, 'update_id', None):
            parts.append(f"🆔 Update: <code>{update.update_id}</code>")
    except Exception:  # noqa: BLE001 - kontekst yig'ishda xato hisobotni buzmasin
        pass

    return "\n".join(parts) if parts else "Update: kontekst yo'q"


async def report_error(bot, exception: Exception, update=None) -> bool:
    """Xatoni bug kanaliga yuborish.

    Returns:
        True - yuborildi, False - yuborilmadi (kanal sozlanmagan / dedup / xato).
    """
    channel_id = getattr(settings, 'BUG_CHANNEL_ID', '')
    if not channel_id:
        return False

    try:
        sig = _signature(exception)
        if sig in _recent_errors:
            return False  # yaqinda yuborilgan - takrorlamaymiz
        _recent_errors[sig] = True

        tb_text = ''.join(
            traceback.format_exception(type(exception), exception, exception.__traceback__)
        )
        if len(tb_text) > MAX_TRACEBACK_CHARS:
            # Oxiri muhimroq (asl xato joyi) - boshini qirqamiz
            tb_text = '...\n' + tb_text[-MAX_TRACEBACK_CHARS:]

        text = (
            f"🐞 <b>Botda xatolik</b>\n\n"
            f"❗️ <b>{escape(type(exception).__name__)}</b>: "
            f"<code>{escape(str(exception)[:300])}</code>\n\n"
            f"{_describe_update(update)}\n\n"
            f"<pre>{escape(tb_text)}</pre>"
        )

        await bot.send_message(chat_id=channel_id, text=text, disable_web_page_preview=True)
        return True
    except Exception as e:  # noqa: BLE001
        # Bu funksiya global error handler ichidan chaqiriladi - bu yerda xato
        # tashlasak cheksiz tsikl boshlanardi. Faqat loglaymiz.
        logger.warning(f"Xatolikni bug kanaliga yuborib bo'lmadi: {e}")
        return False
