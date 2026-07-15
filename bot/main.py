import asyncio
import logging
import sys
import os

# Ensure parent directory is in path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Router
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault, ErrorEvent
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramAPIError
from django.conf import settings

from bot.loader import bot, dp
from bot.handlers import router
from bot.middlewares import DatabaseMiddleware, SubscriptionMiddleware, ThrottlingMiddleware
from bot.utils.error_reporter import report_error

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def set_bot_commands():
    """Bot buyruqlarini sozlash"""
    # Oddiy foydalanuvchilar uchun
    user_commands = [
        BotCommand(command="start", description="🏠 Boshlash"),
        BotCommand(command="help", description="❓ Yordam"),
        BotCommand(command="top", description="🔥 Top kinolar"),
        BotCommand(command="last", description="🆕 Yangi kinolar"),
        BotCommand(command="rand", description="🎲 Random kino"),
        BotCommand(command="categories", description="📂 Kategoriyalar"),
        BotCommand(command="premium", description="💎 Premium"),
        BotCommand(command="profile", description="👤 Profil"),
    ]

    # Admin buyruqlari
    admin_commands = user_commands + [
        BotCommand(command="admin", description="👨‍💼 Admin panel"),
        BotCommand(command="addmovie", description="➕ Kino qo'shish"),
        BotCommand(command="user", description="👤 User ma'lumoti"),
        BotCommand(command="ban", description="⛔ Bloklash"),
        BotCommand(command="unban", description="✅ Blokdan chiqarish"),
    ]

    # Barcha foydalanuvchilar uchun
    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

    # Har bir admin uchun alohida
    for admin_id in settings.ADMINS:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
            logger.info(f"Admin buyruqlari o'rnatildi: {admin_id}")
        except Exception as e:
            logger.error(f"Admin buyruqlarini o'rnatishda xato ({admin_id}): {e}")


async def on_startup():
    """Bot ishga tushganda"""
    logger.info("Bot ishga tushdi!")

    # Webhookni o'chirish
    await bot.delete_webhook(drop_pending_updates=True)

    # Bot buyruqlarini o'rnatish
    await set_bot_commands()
    logger.info("Bot buyruqlari o'rnatildi!")

    # Premium scheduler ni ishga tushirish (background task)
    from bot.utils.scheduler import start_scheduler
    asyncio.create_task(start_scheduler(bot, check_interval=3600))  # Har 1 soatda tekshirish
    logger.info("Premium scheduler ishga tushdi!")

    # Jarayonlararo cache invalidation listener (Redis pub/sub). Redis yo'q bo'lsa no-op.
    from bot.utils.cache_listener import run_invalidation_listener
    asyncio.create_task(run_invalidation_listener())


async def on_shutdown():
    """Bot to'xtaganda"""
    logger.info("Bot to'xtadi!")
    await bot.session.close()


# ==================== ERROR HANDLERS ====================

@dp.error()
async def error_handler(event: ErrorEvent):
    """Global xato handler - barcha xatolarni ushlaydi"""
    exception = event.exception
    update = event.update

    # TelegramNetworkError - tarmoq xatosi (Connection reset by peer)
    if isinstance(exception, TelegramNetworkError):
        logger.warning(
            f"Tarmoq xatosi (TelegramNetworkError): {exception}. "
            f"Update ID: {update.update_id if update else 'N/A'}"
        )
        # Bu xato avtomatik hal bo'ladi, hech narsa qilish shart emas
        return True

    # TelegramRetryAfter - flood limit
    if isinstance(exception, TelegramRetryAfter):
        logger.warning(
            f"Flood limit: {exception.retry_after} soniya kutish kerak. "
            f"Update ID: {update.update_id if update else 'N/A'}"
        )
        # Kutish va davom etish
        await asyncio.sleep(exception.retry_after)
        return True

    # Boshqa TelegramAPIError xatolari
    if isinstance(exception, TelegramAPIError):
        logger.error(
            f"Telegram API xatosi: {exception}. "
            f"Update ID: {update.update_id if update else 'N/A'}"
        )
        await report_error(bot, exception, update)
        return True

    # Noma'lum xatolar - loglash
    logger.exception(
        f"Kutilmagan xato: {exception}. "
        f"Update ID: {update.update_id if update else 'N/A'}",
        exc_info=exception
    )
    # Bug kanaliga yuborish (sozlanmagan bo'lsa jimgina o'tadi, xato tashlamaydi)
    await report_error(bot, exception, update)
    return True


async def main():
    """Asosiy funksiya"""
    # Middlewarelar
    dp.message.middleware(ThrottlingMiddleware())
    dp.message.middleware(DatabaseMiddleware())
    dp.message.middleware(SubscriptionMiddleware())

    dp.callback_query.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    # Routerlar
    dp.include_router(router)

    # Startup/Shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Polling
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
