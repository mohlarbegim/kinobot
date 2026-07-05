import random
import logging
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest, ChatMemberUpdated
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from asgiref.sync import sync_to_async
from cachetools import TTLCache
from django.conf import settings

from apps.users.models import User, Admin
from apps.movies.models import Movie, Category
from apps.channels.models import Channel
from apps.payments.models import Tariff
from bot.keyboards import (
    main_menu_inline_kb, channels_kb, subscription_prompt_text, categories_kb, movies_kb,
    tariffs_kb, back_kb, movie_action_kb, saved_movies_kb,
    search_filter_kb, filter_country_kb, filter_language_kb, filter_year_kb,
    flash_sale_tariffs_kb, filter_movies_kb
)
from bot.utils import get_or_create_user, format_number, format_date, update_user_joined_channel, record_channel_subscriptions, get_confirmed_channel_ids, get_join_requested_ids, get_channel_by_tg_id, record_join_request, remove_channel_membership, get_message_text, compute_missing_channels, esc
from apps.payments.models import PendingPaymentSession
from datetime import timedelta
from django.utils import timezone as dj_timezone

# Logger
logger = logging.getLogger(__name__)

# Constants import
from bot.constants import (
    CACHE_TTL_MOVIES, CACHE_TTL_CATEGORIES, CACHE_TTL_BOT_INFO,
    CACHE_TTL_SUBSCRIPTION, CACHE_MAX_MOVIES, CACHE_MAX_PENDING_SUBS,
    DEFAULT_PER_PAGE, PREMIUM_MOVIES_PER_PAGE, TOP_MOVIES_LIMIT,
    MAX_MOVIE_CODE_LENGTH, PENDING_PAYMENT_TIMEOUT
)


async def is_user_admin(user_id: int) -> bool:
    """Foydalanuvchi adminmi tekshirish"""
    # 1. settings.ADMINS ro'yxatini tekshirish
    if user_id in settings.ADMINS:
        return True

    # 2. Database'dagi Admin modelini tekshirish
    @sync_to_async
    def check_db():
        return Admin.objects.filter(user__user_id=user_id).exists()

    return await check_db()

router = Router()

# Cache - constants dan qiymatlar
_movies_cache = TTLCache(maxsize=CACHE_MAX_MOVIES, ttl=CACHE_TTL_MOVIES)
_categories_cache = TTLCache(maxsize=1, ttl=CACHE_TTL_CATEGORIES)
_bot_info_cache = TTLCache(maxsize=1, ttl=CACHE_TTL_BOT_INFO)

# Obuna kutayotgan kanallar (user_id -> [channel_ids])
# TTLCache ishlatamiz - avtomatik tozalanadi (memory leak oldini olish)
_pending_subscriptions: TTLCache = TTLCache(maxsize=CACHE_MAX_PENDING_SUBS, ttl=CACHE_TTL_SUBSCRIPTION)

# Instagram/tashqi "ikki marta Tekshirish" bosqichi (user_id -> True).
# Telegram kanallari bajarilib, faqat Instagram qolganda BIRINCHI «Tekshirish»da
# Instagram qayta ko'rsatiladi (ikkinchi tashrifga majburlash), IKKINCHI «Tekshirish»da
# tasdiqlanadi. Barcha callback'lar bitta bot process'ida ishlangani uchun in-memory yetarli.
_instagram_recheck: TTLCache = TTLCache(maxsize=CACHE_MAX_PENDING_SUBS, ttl=CACHE_TTL_SUBSCRIPTION)


async def get_bot_link(bot: Bot) -> str:
    """Bot linkini olish (cached)"""
    if 'bot_info' in _bot_info_cache:
        return f"https://t.me/{_bot_info_cache['bot_info'].username}"

    bot_info = await bot.me()
    _bot_info_cache['bot_info'] = bot_info
    return f"https://t.me/{bot_info.username}"


async def get_bot_username(bot: Bot) -> str:
    """Bot username'ini olish (cached)"""
    if 'bot_info' in _bot_info_cache:
        return _bot_info_cache['bot_info'].username

    bot_info = await bot.me()
    _bot_info_cache['bot_info'] = bot_info
    return bot_info.username


async def send_movie_or_notice(target, movie, caption, reply_markup=None):
    """
    Kino videosini yuboradi. Agar file_id bo'sh bo'lsa (video hali yuklanmagan -
    admin videosiz qo'shgan), video o'rniga matnli xabar yuboradi (crash bo'lmaydi).

    protect_content=True: foydalanuvchi videoni boshqa chatga forward qila olmaydi
    va yuklab (save) tarqata olmaydi (kontent himoyasi).

    target: Message yoki callback.message (ikkalasida ham answer_video/answer bor).
    """
    if movie.file_id:
        await target.answer_video(
            video=movie.file_id,
            caption=caption,
            reply_markup=reply_markup,
            protect_content=True,
        )
    else:
        await target.answer(
            f"{caption}\n\n⚠️ <i>Video hali yuklanmagan.</i>",
            reply_markup=reply_markup
        )


async def check_user_subscription(bot: Bot, user_id: int, db_user: User = None) -> list:
    """
    Foydalanuvchi obunasini tekshirish.
    Admin yoki premium bo'lsa, bo'sh list qaytaradi.
    """
    from bot.middlewares.subscription import clear_subscription_cache

    # Admin tekshirish
    if user_id in settings.ADMINS:
        return []

    # Premium tekshirish
    if db_user and db_user.is_premium_active:
        return []

    # Cache tozalash va tekshirish
    clear_subscription_cache(user_id)
    return await check_subscription(bot, user_id)


# ==================== START ====================

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    """Start buyrug'i"""
    user = message.from_user

    referral_code = None
    if message.text and len(message.text.split()) > 1:
        referral_code = message.text.split()[1]

    db_user = await get_or_create_user(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        referral_code=referral_code
    )

    # Referal bonus berilgan bo'lsa - taklif qiluvchini xabardor qilamiz (motivatsiya)
    ref_bonus = getattr(db_user, '_referral_bonus', None)
    if ref_bonus:
        try:
            await bot.send_message(
                ref_bonus['referrer_id'],
                f"🎁 <b>Yangi do'st taklif qildingiz!</b>\n\n"
                f"👤 {esc(user.full_name)} sizning havolangiz orqali qo'shildi.\n"
                f"➕ Sizga <b>{ref_bonus['bonus_days']} kun</b> qo'shildi.\n"
                f"👥 Jami taklif qilganlaringiz: <b>{ref_bonus['referrals_count']} ta</b>\n\n"
                f"Ko'proq do'st taklif qiling — ko'proq bonus oling! 🚀"
            )
        except Exception as e:
            # Taklif qiluvchi botni bloklagan bo'lishi mumkin - jim o'tamiz
            logger.info(f"Referal bonus xabari yuborilmadi (referrer={ref_bonus['referrer_id']}): {e}")

    not_subscribed = await check_subscription(bot, user.id)

    # Admin tekshirish
    is_admin = await is_user_admin(user.id)

    if not_subscribed and not is_admin:
        # Obuna bo'lmagan kanallarni eslab qolamiz (bot orqali obuna bo'lganlarni hisoblash uchun)
        _pending_subscriptions[user.id] = [ch.id for ch in not_subscribed]

        await message.answer(
            f"👋 Salom, <b>{esc(user.full_name)}</b>!\n\n"
            + subscription_prompt_text(not_subscribed),
            reply_markup=channels_kb(not_subscribed)
        )
        return

    status = ""
    if db_user.is_premium_active:
        status = "💎 Premium\n\n"
    elif db_user.is_trial_active:
        status = "🎁 Trial\n\n"

    await message.answer(
        await get_message_text('welcome', full_name=esc(user.full_name), status=status),
        reply_markup=main_menu_inline_kb(is_admin=is_admin)
    )


# ==================== OBUNA TEKSHIRISH ====================

async def _finalize_subscription_success(callback: CallbackQuery, user):
    """Barcha kanallar obuna/tasdiqlanganda: yozib qo'yish + menyuni ko'rsatish."""
    # Bot orqali obuna bo'lgan kanallarni yozamiz (get_or_create - takrorlanmaydi)
    if user.id in _pending_subscriptions:
        pending_channel_ids = _pending_subscriptions.pop(user.id)
        if pending_channel_ids:
            await record_channel_subscriptions(user.id, pending_channel_ids)
            # Birinchi kanalni "kelgan kanal" sifatida saqlaymiz
            await update_user_joined_channel(user.id, pending_channel_ids[0])

    is_admin = await is_user_admin(user.id)

    try:
        await callback.message.edit_text(
            await get_message_text('subscription_success'),
            reply_markup=main_menu_inline_kb(is_admin=is_admin)
        )
    except TelegramBadRequest:
        pass  # Xabar o'zgartirilmagan (masalan, video xabar)


async def _show_current_stage(callback: CallbackQuery, not_subscribed: list):
    """Bajarilmagan barcha kanallarni (Telegram + Instagram birga) ko'rsatish."""
    _pending_subscriptions[callback.from_user.id] = [ch.id for ch in not_subscribed]
    try:
        await callback.message.edit_text(
            subscription_prompt_text(not_subscribed),
            reply_markup=channels_kb(not_subscribed)
        )
    except TelegramBadRequest:
        pass  # Xabar o'zgartirilmagan


@router.chat_join_request()
async def on_chat_join_request(request: ChatJoinRequest):
    """
    Yopiq (private) majburiy kanalga qo'shilish so'rovi kelganда - uni obuna deb
    hisoblaymiz (so'rovning o'zi kifoya, admin tasdig'ini kutmaymiz). Bot kanalga
    admin bo'lsa shu update keladi.
    """
    from bot.middlewares.subscription import clear_subscription_cache

    channel = await get_channel_by_tg_id(request.chat.id)
    if not channel:
        return  # bizning majburiy kanalimiz emas

    await record_join_request(request.from_user.id, channel.id)
    clear_subscription_cache(request.from_user.id)


@router.chat_member()
async def on_chat_member_update(update: ChatMemberUpdated):
    """
    Majburiy kanaldagi foydalanuvchi a'zoligi o'zgarsa (bot admin bo'lsa keladi).

    Kanaldan chiqib ketsa (left/kicked) - uning shu kanalga oid qo'shilish so'rovi
    va obuna yozuvlari o'chiriladi, cache tozalanadi. Shunda keyingi harakatida bot
    QAYTA obuna so'raydi. (Instagram/tashqi kanallar bu yerda kelmaydi - ular uchun
    chiqishni aniqlab bo'lmaydi.)
    """
    from bot.middlewares.subscription import clear_subscription_cache

    channel = await get_channel_by_tg_id(update.chat.id)
    if not channel:
        return  # bizning majburiy kanalimiz emas

    user_id = update.new_chat_member.user.id
    new_status = update.new_chat_member.status

    if new_status in ('left', 'kicked'):
        await remove_channel_membership(user_id, channel.id)

    # Har qanday o'zgarishda cache'ni yangilaymiz (chiqqan/qo'shilganini darhol aks ettirish)
    clear_subscription_cache(user_id)


@router.callback_query(F.data == "check_subscription")
async def check_sub_callback(callback: CallbackQuery, bot: Bot):
    """
    Obunani tekshirish. Instagram/tashqi kanallar uchun "ikki marta Tekshirish" mantig'i:

    1) Telegram kanallariga obuna bo'lmagan bo'lsa - odatiy so'rov ko'rsatiladi.
    2) Telegram bajarilib, faqat Instagram/tashqi qolsa: BIRINCHI «Tekshirish»da
       Instagram QAYTA ko'rsatiladi (obuna bo'lishga majburlash - manipulatsiya).
    3) IKKINCHI «Tekshirish»da Instagram tasdiqlanadi (bot uni tekshira olmaydi).
    """
    from bot.middlewares.subscription import clear_subscription_cache

    user = callback.from_user

    # Cache ni tozalash - yangi tekshirish uchun
    clear_subscription_cache(user.id)

    not_subscribed = await check_subscription(bot, user.id)

    # Hammasi joyida
    if not not_subscribed:
        _instagram_recheck.pop(user.id, None)
        await callback.answer("✅ Tasdiqlandi!")
        await _finalize_subscription_success(callback, user)
        return

    tg_missing = [ch for ch in not_subscribed if getattr(ch, 'is_checkable', True)]
    ig_missing = [ch for ch in not_subscribed if not getattr(ch, 'is_checkable', True)]

    # Telegram kanallari hali to'liq emas - avval ularni bajarish shart
    if tg_missing:
        _instagram_recheck.pop(user.id, None)  # Instagram bosqichini qayta boshlaymiz
        await callback.answer("❌ Avval barcha Telegram kanallariga obuna bo'ling!", show_alert=True)
        await _show_current_stage(callback, not_subscribed)
        return

    # Faqat Instagram/tashqi qoldi
    if not _instagram_recheck.get(user.id):
        # BIRINCHI «Tekshirish»: Instagram'ni qayta ko'rsatamiz (2-tashrifga majburlash)
        _instagram_recheck[user.id] = True
        await callback.answer(
            "📢 Sahifaga obuna bo'ling, so'ng yana «Tekshirish» tugmasini bosing!",
            show_alert=True
        )
        await _show_instagram_recheck(callback, ig_missing)
        return

    # IKKINCHI «Tekshirish»: tasdiqlaymiz
    _instagram_recheck.pop(user.id, None)
    await record_channel_subscriptions(user.id, [ch.id for ch in ig_missing])
    await update_user_joined_channel(user.id, ig_missing[0].id)
    clear_subscription_cache(user.id)
    await callback.answer("✅ Tasdiqlandi!")
    await _finalize_subscription_success(callback, user)


async def _show_instagram_recheck(callback: CallbackQuery, ig_channels: list):
    """BIRINCHI «Tekshirish»dan keyin Instagram'ni qayta ko'rsatish (ikkinchi tashrif uchun)."""
    _pending_subscriptions[callback.from_user.id] = [ch.id for ch in ig_channels]
    try:
        await callback.message.edit_text(
            subscription_prompt_text(ig_channels, confirming=True),
            reply_markup=channels_kb(ig_channels)
        )
    except TelegramBadRequest:
        pass


# ==================== BACK TO MENU ====================

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_callback(callback: CallbackQuery):
    """Menyuga qaytish"""
    is_admin = await is_user_admin(callback.from_user.id)

    try:
        await callback.message.edit_text(
            "🏠 <b>Asosiy menyu</b>\n\n"
            "🎬 Kino kodini yuboring yoki menyu tugmalaridan foydalaning:",
            reply_markup=main_menu_inline_kb(is_admin=is_admin)
        )
    except TelegramBadRequest:
        # Video/rasm xabarini edit qilib bo'lmaydi - yangi xabar yuborish
        await callback.message.answer(
            "🏠 <b>Asosiy menyu</b>\n\n"
            "🎬 Kino kodini yuboring yoki menyu tugmalaridan foydalaning:",
            reply_markup=main_menu_inline_kb(is_admin=is_admin)
        )
    await callback.answer()


# ==================== KINO OLISH ====================

@router.message(F.text.regexp(r'^\d+$'), StateFilter(None))
async def get_movie_by_code(message: Message, db_user: User = None, bot: Bot = None):
    """Kod bo'yicha kino olish"""
    user_id = message.from_user.id
    code = message.text.strip()

    # Input validation - faqat raqamlar va max uzunlik
    if not code.isdigit() or len(code) > MAX_MOVIE_CODE_LENGTH:
        await message.answer(
            "❌ Noto'g'ri kod formati.\n\n"
            "🔍 Kino kodi faqat raqamlardan iborat bo'lishi kerak.",
            reply_markup=back_kb()
        )
        return

    # Obunani tekshirish (helper funksiya orqali)
    not_subscribed = await check_user_subscription(bot, user_id, db_user)
    if not_subscribed:
        await message.answer(
            subscription_prompt_text(not_subscribed),
            reply_markup=channels_kb(not_subscribed)
        )
        return

    movie = await get_movie_by_code_db(code)

    if not movie:
        await message.answer(
            await get_message_text('movie_not_found', code=esc(code)),
            reply_markup=back_kb()
        )
        return

    if not movie.is_active:
        await message.answer(
            "❌ Bu kino hozircha mavjud emas.",
            reply_markup=back_kb()
        )
        return

    # Premium check
    if movie.is_premium and not (db_user and db_user.is_premium_active):
        is_admin = await is_user_admin(user_id)
        await message.answer(
            f"💎 <b>{esc(movie.display_title)}</b>\n\n"
            "Bu kino faqat Premium foydalanuvchilar uchun.\n\n"
            "Premium olish uchun 💎 Premium tugmasini bosing.",
            reply_markup=main_menu_inline_kb(is_admin=is_admin)
        )
        return

    # Send movie
    try:
        bot_link = await get_bot_link(bot)

        desc = f"\n\n📖 {esc(movie.description)}" if movie.description else ""
        year_text = f"📅 Yil: {movie.year}\n" if movie.year else ""
        country_text = f"🌍 Davlat: {movie.get_country_display()}\n" if hasattr(movie, 'get_country_display') else ""

        caption = (
            f"🎬 <b>{esc(movie.display_title)}</b>{desc}\n\n"
            f"📝 Kod: <code>{esc(movie.code)}</code>\n"
            f"{year_text}"
            f"{country_text}"
            f"📺 Sifat: {movie.get_quality_display()}\n"
            f"🌐 Til: {movie.get_language_display()}\n"
            f"👁 Ko'rishlar: {format_number(movie.views)}\n\n"
            f"🤖 <b>Bot:</b> {bot_link}"
        )

        # Saqlangan yoki yo'qligini tekshirish
        is_saved = await check_movie_saved(user_id, movie.code) if db_user else False

        await send_movie_or_notice(
            message, movie, caption,
            movie_action_kb(movie.code, is_saved)
        )

        # Update stats
        await increment_movie_views(movie.id)
        if db_user:
            await increment_user_movies(db_user.user_id)

    except TelegramBadRequest as e:
        logger.error(f"Kino yuborishda xatolik (code={code}): {e}")
        await message.answer("❌ Kino faylida xatolik.", reply_markup=back_kb())


# ==================== QIDIRISH ====================

@router.callback_query(F.data == "search")
async def search_callback(callback: CallbackQuery, state: FSMContext):
    """Qidirish"""
    # State tozalash
    await state.clear()

    await callback.message.edit_text(
        await get_message_text('search_prompt'),
        reply_markup=search_filter_kb()
    )
    await callback.answer()


# ==================== NOM BO'YICHA QIDIRISH (Inline mode orqali) ====================
# Inline mode handler: bot/handlers/inline.py da

@router.callback_query(F.data.startswith("movie_view:"))
async def movie_view_callback(callback: CallbackQuery, db_user: User = None, bot: Bot = None):
    """Kino ko'rish (qidiruv natijasidan)"""
    code = callback.data.split(":")[1]

    movie = await get_movie_by_code_db(code)

    if not movie:
        await callback.answer("❌ Kino topilmadi.", show_alert=True)
        return

    # Premium tekshirish
    if movie.is_premium and not (db_user and db_user.is_premium_active):
        await callback.answer("💎 Bu Premium kino! Premium olish uchun menudagi tugmani bosing.", show_alert=True)
        return

    # Ko'rishlar sonini oshirish
    await increment_movie_views(movie.id)

    # Saqlanganmi tekshirish
    is_saved = await check_movie_saved(callback.from_user.id, movie.code) if db_user else False

    # Kino yuborish
    try:
        if movie.file_id:
            await bot.send_video(
                chat_id=callback.from_user.id,
                video=movie.file_id,
                caption=f"🎬 <b>{esc(movie.display_title)}</b>\n\n📝 Kod: <code>{esc(movie.code)}</code>",
                reply_markup=movie_action_kb(movie.code, is_saved),
                protect_content=True,
            )
        else:
            await callback.message.answer(
                f"🎬 <b>{esc(movie.display_title)}</b>\n\n📝 Kod: <code>{esc(movie.code)}</code>\n\n⚠️ Video fayl topilmadi.",
                reply_markup=movie_action_kb(movie.code, is_saved)
            )
    except TelegramBadRequest as e:
        await callback.answer(f"❌ Xatolik: Video yuborib bo'lmadi.", show_alert=True)
        return
    except Exception as e:
        await callback.answer("❌ Xatolik yuz berdi.", show_alert=True)
        return

    await callback.answer()


# ==================== FILTRLAR ====================

@router.callback_query(F.data == "filter:category")
async def filter_category_callback(callback: CallbackQuery):
    """Janr bo'yicha filter"""
    categories = await get_categories()

    if not categories:
        await callback.answer("📭 Kategoriyalar yo'q", show_alert=True)
        return

    await callback.message.edit_text(
        "📂 <b>Janr tanlang:</b>",
        reply_markup=categories_kb(categories)
    )
    await callback.answer()


@router.callback_query(F.data == "filter:country")
async def filter_country_callback(callback: CallbackQuery):
    """Davlat bo'yicha filter"""
    await callback.message.edit_text(
        "🌍 <b>Davlat tanlang:</b>",
        reply_markup=filter_country_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "filter:language")
async def filter_language_callback(callback: CallbackQuery):
    """Til bo'yicha filter"""
    await callback.message.edit_text(
        "🌐 <b>Til tanlang:</b>",
        reply_markup=filter_language_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "filter:year")
async def filter_year_callback(callback: CallbackQuery):
    """Yil bo'yicha filter"""
    await callback.message.edit_text(
        "📅 <b>Yil tanlang:</b>",
        reply_markup=filter_year_kb()
    )
    await callback.answer()


# Filtr nomlari (bir nechta handler ishlatadi)
COUNTRY_NAMES = {
    'usa': '🇺🇸 AQSH', 'korea': '🇰🇷 Koreya', 'india': '🇮🇳 Hindiston',
    'turkey': '🇹🇷 Turkiya', 'russia': '🇷🇺 Rossiya', 'uzbekistan': '🇺🇿 O\'zbekiston',
    'japan': '🇯🇵 Yaponiya', 'china': '🇨🇳 Xitoy'
}
LANG_NAMES = {
    'uzbek': "🇺🇿 O'zbekcha", 'rus': '🇷🇺 Ruscha', 'eng': '🇺🇸 Inglizcha',
    'turk': '🇹🇷 Turkcha', 'korea': '🇰🇷 Koreyscha'
}


async def _show_filter_results(callback, filter_type, filter_value, page, movies, total_pages):
    """Filtr (davlat/til/yil) natijalarini ko'rsatish - birinchi sahifa va pagination uchun."""
    if filter_type == 'country':
        name = COUNTRY_NAMES.get(filter_value, filter_value)
        header = f"🌍 <b>{esc(name)} kinolari:</b>"
        empty = f"📭 {name} kinolari topilmadi"
    elif filter_type == 'language':
        name = LANG_NAMES.get(filter_value, filter_value)
        header = f"🌐 <b>{esc(name)} kinolar:</b>"
        empty = f"📭 {name} kinolar topilmadi"
    else:  # year
        header = f"📅 <b>{esc(filter_value)}-yil kinolari:</b>"
        empty = f"📭 {filter_value}-yil kinolari topilmadi"

    if not movies:
        await callback.answer(empty, show_alert=True)
        return

    await callback.message.edit_text(
        f"{header}\n\nJami: {len(movies)} ta",
        reply_markup=filter_movies_kb(movies, filter_type, filter_value, page=page, total_pages=total_pages)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("filter_country:"))
async def filter_country_result_callback(callback: CallbackQuery):
    """Davlat bo'yicha natijalar"""
    country = callback.data.split(":")[1]
    movies, total_pages = await get_movies_by_filter(country=country, page=1)
    await _show_filter_results(callback, 'country', country, 1, movies, total_pages)


@router.callback_query(F.data.startswith("filter_language:"))
async def filter_language_result_callback(callback: CallbackQuery):
    """Til bo'yicha natijalar"""
    language = callback.data.split(":")[1]
    movies, total_pages = await get_movies_by_filter(language=language, page=1)
    await _show_filter_results(callback, 'language', language, 1, movies, total_pages)


@router.callback_query(F.data.startswith("filter_year:"))
async def filter_year_result_callback(callback: CallbackQuery):
    """Yil bo'yicha natijalar"""
    year = callback.data.split(":")[1]
    movies, total_pages = await get_movies_by_filter(year=int(year), page=1)
    await _show_filter_results(callback, 'year', year, 1, movies, total_pages)


@router.callback_query(F.data.startswith("filter_page:"))
async def filter_page_callback(callback: CallbackQuery):
    """Filtr natijalari pagination - filtrni saqlab keyingi sahifani ko'rsatadi."""
    parts = callback.data.split(":")
    filter_type = parts[1]
    filter_value = parts[2]
    page = int(parts[3])

    if filter_type == 'country':
        movies, total_pages = await get_movies_by_filter(country=filter_value, page=page)
    elif filter_type == 'language':
        movies, total_pages = await get_movies_by_filter(language=filter_value, page=page)
    elif filter_type == 'year':
        movies, total_pages = await get_movies_by_filter(year=int(filter_value), page=page)
    else:
        await callback.answer()
        return

    await _show_filter_results(callback, filter_type, filter_value, page, movies, total_pages)


# ==================== TOP KINOLAR ====================

@router.callback_query(F.data == "top_movies")
async def top_movies_callback(callback: CallbackQuery):
    """Top kinolar"""
    movies = await get_top_movies(10)

    if not movies:
        await callback.answer("📭 Kinolar topilmadi.", show_alert=True)
        return

    text = "🔥 <b>Top 10 kinolar:</b>\n\n"
    for i, movie in enumerate(movies, 1):
        text += f"{i}. 🎬 <b>{esc(movie.display_title)}</b>\n"
        text += f"    📝 Kod: <code>{esc(movie.code)}</code> • 👁 {format_number(movie.views)}\n\n"

    text += "📥 Kino olish uchun kodini yuboring."

    await callback.message.edit_text(text, reply_markup=back_kb())
    await callback.answer()


@router.message(Command("top"))
async def top_movies_handler(message: Message):
    """Top kinolar command"""
    movies = await get_top_movies(10)

    if not movies:
        await message.answer("📭 Kinolar topilmadi.")
        return

    text = "🔥 <b>Top 10 kinolar:</b>\n\n"
    for i, movie in enumerate(movies, 1):
        text += f"{i}. 🎬 <b>{esc(movie.display_title)}</b>\n"
        text += f"    📝 Kod: <code>{esc(movie.code)}</code> • 👁 {format_number(movie.views)}\n\n"

    text += "📥 Kino olish uchun kodini yuboring."

    await message.answer(text, reply_markup=back_kb())


# ==================== PREMIUM KINOLAR ====================

@router.callback_query(F.data.startswith("premium_movies"))
async def premium_movies_callback(callback: CallbackQuery, db_user: User = None):
    """Premium kinolar - videolar bilan"""
    # Premium/trial bo'lmagan foydalanuvchilarga premium video katalogini bermaymiz
    if not (db_user and db_user.is_premium_active):
        await callback.answer("💎 Bu bo'lim faqat Premium foydalanuvchilar uchun.", show_alert=True)
        return

    # Sahifa raqamini olish
    parts = callback.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 1
    per_page = 5

    movies, total_pages = await get_premium_movies_paginated(page, per_page)

    if not movies:
        await callback.answer("📭 Premium kinolar topilmadi.", show_alert=True)
        return

    await callback.answer()

    # Eski xabarni o'chirish
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Sarlavha xabari
    await callback.message.answer(f"💎 <b>Premium kinolar</b> ({page}/{total_pages})")

    # Videolarni yuborish
    for movie in movies:
        try:
            await callback.message.answer_video(
                video=movie.file_id,
                caption=f"📝 Kod: <code>{esc(movie.code)}</code>",
                protect_content=True,
            )
        except Exception:
            pass

    # Navigatsiya tugmalari
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"premium_movies:{page - 1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"premium_movies:{page + 1}"))

    kb_buttons = []
    if nav_buttons:
        kb_buttons.append(nav_buttons)
    kb_buttons.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_menu")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    await callback.message.answer("📄 Sahifa: " + f"{page}/{total_pages}", reply_markup=kb)


# ==================== YANGI KINOLAR ====================

@router.callback_query(F.data == "new_movies")
async def new_movies_callback(callback: CallbackQuery):
    """Yangi kinolar"""
    movies = await get_last_movies(10)

    if not movies:
        await callback.answer("📭 Kinolar topilmadi.", show_alert=True)
        return

    text = "🆕 <b>Yangi kinolar:</b>\n\n"
    for movie in movies:
        premium = "💎 " if movie.is_premium else ""
        text += f"{premium}🎬 <b>{esc(movie.display_title)}</b>\n"
        text += f"    📝 Kod: <code>{esc(movie.code)}</code>\n\n"

    text += "📥 Kino olish uchun kodini yuboring."

    await callback.message.edit_text(text, reply_markup=back_kb())
    await callback.answer()


@router.message(Command("last"))
async def last_movies_handler(message: Message):
    """Yangi kinolar command"""
    movies = await get_last_movies(10)

    if not movies:
        await message.answer("📭 Kinolar topilmadi.")
        return

    text = "🆕 <b>Yangi kinolar:</b>\n\n"
    for movie in movies:
        premium = "💎 " if movie.is_premium else ""
        text += f"{premium}🎬 <b>{esc(movie.display_title)}</b>\n"
        text += f"    📝 Kod: <code>{esc(movie.code)}</code>\n\n"

    text += "📥 Kino olish uchun kodini yuboring."

    await message.answer(text, reply_markup=back_kb())


# ==================== RANDOM KINO ====================

@router.message(Command("rand"))
async def random_movie_handler(message: Message, db_user: User = None, bot: Bot = None):
    """Random kino"""
    user_id = message.from_user.id

    # Obunani tekshirish (helper funksiya orqali)
    not_subscribed = await check_user_subscription(bot, user_id, db_user)
    if not_subscribed:
        await message.answer(
            subscription_prompt_text(not_subscribed),
            reply_markup=channels_kb(not_subscribed)
        )
        return

    movie = await get_random_movie()

    if not movie:
        await message.answer("📭 Kinolar topilmadi.", reply_markup=back_kb())
        return

    if movie.is_premium and not (db_user and db_user.is_premium_active):
        is_admin = await is_user_admin(user_id)
        await message.answer(
            f"💎 <b>{esc(movie.display_title)}</b>\n\n"
            "Premium kino tushdi! Premium olish uchun 💎 Premium tugmasini bosing.",
            reply_markup=main_menu_inline_kb(is_admin=is_admin)
        )
        return

    try:
        bot_link = await get_bot_link(bot)

        desc = f"\n📖 {esc(movie.description)}" if movie.description else ""
        year_text = f" • 📅 {movie.year}" if movie.year else ""

        await send_movie_or_notice(
            message, movie,
            (
                f"🎲 <b>Random kino:</b>\n\n"
                f"🎬 <b>{esc(movie.display_title)}</b>{desc}\n\n"
                f"📝 Kod: <code>{esc(movie.code)}</code>\n"
                f"📺 {movie.get_quality_display()} • 🌐 {movie.get_language_display()}{year_text}\n\n"
                f"🤖 <b>Bot:</b> {bot_link}"
            ),
            back_kb()
        )
        await increment_movie_views(movie.id)
    except TelegramBadRequest as e:
        logger.error(f"Random kino yuborishda xatolik: {e}")
        await message.answer("❌ Xatolik yuz berdi.", reply_markup=back_kb())


# ==================== BARCHA KINOLAR ====================

@router.callback_query(F.data == "all_movies")
async def all_movies_callback(callback: CallbackQuery):
    """Barcha kinolar - kanalga yo'naltirish"""
    bot_settings = await get_bot_settings()

    if bot_settings and bot_settings.channel_link:
        channel_name = bot_settings.channel_name or "Kinolar kanali"
        channel_link = bot_settings.channel_link

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"📢 {channel_name}", url=channel_link)],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="search")]
        ])

        await callback.message.edit_text(
            "🎬 <b>Barcha kinolar</b>\n\n"
            "Barcha kinolarni kanalimizda topishingiz mumkin!\n\n"
            "👇 Kanalga o'tish uchun tugmani bosing:",
            reply_markup=kb
        )
    else:
        # Kanal sozlanmagan bo'lsa, eski funksiya
        movies, total_pages = await get_all_movies(page=1)

        if not movies:
            await callback.answer("📭 Kinolar topilmadi.", show_alert=True)
            return

        await callback.message.edit_text(
            "🎬 <b>Barcha kinolar</b>\n\nTanlang:",
            reply_markup=movies_kb(movies, page=1, total_pages=total_pages)
        )

    await callback.answer()


@router.message(Command("movies"))
async def all_movies_handler(message: Message):
    """Barcha kinolar command - kanalga yo'naltirish"""
    bot_settings = await get_bot_settings()

    if bot_settings and bot_settings.channel_link:
        channel_name = bot_settings.channel_name or "Kinolar kanali"
        channel_link = bot_settings.channel_link

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"📢 {channel_name}", url=channel_link)],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_menu")]
        ])

        await message.answer(
            "🎬 <b>Barcha kinolar</b>\n\n"
            "Barcha kinolarni kanalimizda topishingiz mumkin!\n\n"
            "👇 Kanalga o'tish uchun tugmani bosing:",
            reply_markup=kb
        )
    else:
        # Kanal sozlanmagan bo'lsa, eski funksiya
        movies, total_pages = await get_all_movies(page=1)

        if not movies:
            await message.answer("📭 Kinolar topilmadi.")
            return

        await message.answer(
            "🎬 <b>Barcha kinolar</b>\n\nTanlang:",
            reply_markup=movies_kb(movies, page=1, total_pages=total_pages)
        )


# ==================== KATEGORIYALAR ====================

@router.callback_query(F.data == "categories")
async def categories_callback(callback: CallbackQuery):
    """Kategoriyalar"""
    categories = await get_categories()

    if not categories:
        await callback.answer("📭 Kategoriyalar topilmadi.", show_alert=True)
        return

    await callback.message.edit_text(
        "📂 <b>Kategoriyalar</b>\n\nTanlang:",
        reply_markup=categories_kb(categories)
    )
    await callback.answer()


@router.message(Command("categories"))
async def categories_handler(message: Message):
    """Kategoriyalar command"""
    categories = await get_categories()

    if not categories:
        await message.answer("📭 Kategoriyalar topilmadi.")
        return

    await message.answer(
        "📂 <b>Kategoriyalar</b>\n\nTanlang:",
        reply_markup=categories_kb(categories)
    )


# ==================== KATEGORIYA BO'YICHA ====================

@router.callback_query(F.data.startswith("category:"))
async def category_movies_callback(callback: CallbackQuery):
    """Kategoriya bo'yicha kinolar"""
    category_id = int(callback.data.split(":")[1])

    movies, total_pages, category_name = await get_movies_by_category(category_id, page=1)

    if not movies:
        await callback.answer("📭 Bu kategoriyada kinolar yo'q.", show_alert=True)
        return

    await callback.message.edit_text(
        f"📂 <b>{category_name}</b>\n\nTanlang:",
        reply_markup=movies_kb(movies, page=1, total_pages=total_pages, category_id=category_id)
    )
    await callback.answer()


# ==================== PAGINATION ====================

@router.callback_query(F.data.startswith("movies_page:"))
async def movies_page_callback(callback: CallbackQuery):
    """Kinolar pagination"""
    parts = callback.data.split(":")
    category_id = int(parts[1]) if parts[1] != 'None' else None
    page = int(parts[2])

    if category_id:
        movies, total_pages, category_name = await get_movies_by_category(category_id, page=page)
        title = f"📂 <b>{category_name}</b>"
    else:
        movies, total_pages = await get_all_movies(page=page)
        title = "🎬 <b>Barcha kinolar</b>"

    await callback.message.edit_text(
        f"{title}\n\nTanlang:",
        reply_markup=movies_kb(movies, page=page, total_pages=total_pages, category_id=category_id)
    )
    await callback.answer()


# ==================== KINO TANLASH ====================

@router.callback_query(F.data.startswith("movie:"))
async def movie_callback(callback: CallbackQuery, db_user: User = None, bot: Bot = None):
    """Kinoni tanlash"""
    user_id = callback.from_user.id

    # Obunani tekshirish (helper funksiya orqali)
    not_subscribed = await check_user_subscription(bot, user_id, db_user)
    if not_subscribed:
        await callback.answer("❌ Avval kanallarga obuna bo'ling!", show_alert=True)
        await callback.message.answer(
            subscription_prompt_text(not_subscribed),
            reply_markup=channels_kb(not_subscribed)
        )
        return

    code = callback.data.split(":")[1]

    # Input validation
    if not code.isdigit() or len(code) > MAX_MOVIE_CODE_LENGTH:
        await callback.answer("❌ Noto'g'ri kod!", show_alert=True)
        return

    movie = await get_movie_by_code_db(code)

    if not movie:
        await callback.answer("❌ Kino topilmadi.", show_alert=True)
        return

    if movie.is_premium and not (db_user and db_user.is_premium_active):
        await callback.answer("💎 Bu Premium kino!", show_alert=True)
        return

    await callback.answer()

    try:
        bot_link = await get_bot_link(bot)

        desc = f"\n📖 {esc(movie.description)}" if movie.description else ""
        year_text = f" • 📅 {movie.year}" if movie.year else ""

        await send_movie_or_notice(
            callback.message, movie,
            (
                f"🎬 <b>{esc(movie.display_title)}</b>{desc}\n\n"
                f"📝 Kod: <code>{esc(movie.code)}</code>\n"
                f"📺 {movie.get_quality_display()} • 🌐 {movie.get_language_display()}{year_text}\n"
                f"👁 {format_number(movie.views)}\n\n"
                f"🤖 <b>Bot:</b> {bot_link}"
            ),
            back_kb()
        )
        await increment_movie_views(movie.id)
        if db_user:
            await increment_user_movies(db_user.user_id)
    except TelegramBadRequest as e:
        logger.error(f"Kino callback yuborishda xatolik (code={code}): {e}")
        await callback.message.answer("❌ Xatolik.", reply_markup=back_kb())


# ==================== PREMIUM ====================

@router.callback_query(F.data == "premium")
async def premium_callback(callback: CallbackQuery, db_user: User = None):
    """Premium"""
    if db_user and db_user.is_premium_active:
        await callback.message.edit_text(
            f"💎 <b>Sizda Premium mavjud!</b>\n\n"
            f"📅 Amal qilish muddati: {db_user.premium_expires.strftime('%d.%m.%Y') if db_user.premium_expires else 'Muddatsiz'}\n"
            f"⏳ Qolgan kunlar: {db_user.days_left}",
            reply_markup=back_kb()
        )
        await callback.answer()
        return

    tariffs = await get_tariffs()

    if not tariffs:
        await callback.answer("📭 Tariflar mavjud emas.", show_alert=True)
        return

    # Sozlamalardan chegirma muddatini olish
    settings = await get_bot_settings()
    discount_duration = settings.discount_duration  # sekundda

    # Flash sale - chegirma vaqti ichida
    is_flash_sale = settings.discount_active
    seconds_left = discount_duration

    if db_user and settings.discount_active:
        # Birinchi ko'rishni qayd qilish
        if not db_user.premium_first_view:
            await set_premium_first_view(db_user.user_id)
            is_flash_sale = True
            seconds_left = discount_duration
        else:
            is_flash_sale = db_user.is_flash_sale_active
            seconds_left = db_user.flash_sale_seconds_left

    if is_flash_sale:
        minutes = seconds_left // 60
        secs = seconds_left % 60
        duration_mins = discount_duration // 60
        timer_text = f"⏰ <b>CHEGIRMA!</b> Vaqt: {minutes}:{secs:02d}\n\n"
        text = (
            f"🔥 <b>FLASH SALE!</b> 🔥\n\n"
            f"{timer_text}"
            "💎 <b>Premium afzalliklari:</b>\n\n"
            "✅ Barcha kinolarga kirish\n"
            "✅ Reklamasiz foydalanish\n"
            "✅ Tezkor yuklash\n\n"
            f"⚡ <b>Shoshiling! Taklif atigi {duration_mins} daqiqa amal qiladi.</b>\n\n"
            "📦 Tarifni tanlang:"
        )
        await callback.message.edit_text(text, reply_markup=flash_sale_tariffs_kb(tariffs, is_discount=True))
    else:
        text = (
            "💎 <b>Premium afzalliklari:</b>\n\n"
            "✅ Barcha kinolarga kirish\n"
            "✅ Reklamasiz foydalanish\n"
            "✅ Tezkor yuklash\n\n"
            "📦 Tarifni tanlang:"
        )
        await callback.message.edit_text(text, reply_markup=flash_sale_tariffs_kb(tariffs, is_discount=False))

    await callback.answer()


@router.message(Command("premium"))
async def premium_handler(message: Message, db_user: User = None):
    """Premium command"""
    if db_user and db_user.is_premium_active:
        await message.answer(
            f"💎 <b>Sizda Premium mavjud!</b>\n\n"
            f"📅 Amal qilish muddati: {db_user.premium_expires.strftime('%d.%m.%Y') if db_user.premium_expires else 'Muddatsiz'}\n"
            f"⏳ Qolgan kunlar: {db_user.days_left}",
            reply_markup=back_kb()
        )
        return

    tariffs = await get_tariffs()

    if not tariffs:
        await message.answer("📭 Tariflar mavjud emas.")
        return

    # Sozlamalardan chegirma muddatini olish
    settings = await get_bot_settings()
    discount_duration = settings.discount_duration

    # Flash sale
    is_flash_sale = settings.discount_active
    seconds_left = discount_duration

    if db_user and settings.discount_active:
        if not db_user.premium_first_view:
            await set_premium_first_view(db_user.user_id)
            seconds_left = discount_duration
        else:
            is_flash_sale = db_user.is_flash_sale_active
            seconds_left = db_user.flash_sale_seconds_left

    if is_flash_sale:
        minutes = seconds_left // 60
        secs = seconds_left % 60
        duration_mins = discount_duration // 60
        await message.answer(
            f"🔥 <b>FLASH SALE!</b> 🔥\n\n"
            f"⏰ <b>CHEGIRMA!</b> Vaqt: {minutes}:{secs:02d}\n\n"
            "💎 <b>Premium afzalliklari:</b>\n\n"
            "✅ Barcha kinolarga kirish\n"
            "✅ Reklamasiz foydalanish\n"
            "✅ Tezkor yuklash\n\n"
            f"⚡ <b>Shoshiling! Taklif atigi {duration_mins} daqiqa amal qiladi.</b>\n\n"
            "📦 Tarifni tanlang:",
            reply_markup=flash_sale_tariffs_kb(tariffs, is_discount=True)
        )
    else:
        await message.answer(
            "💎 <b>Premium afzalliklari:</b>\n\n"
            "✅ Barcha kinolarga kirish\n"
            "✅ Reklamasiz foydalanish\n"
            "✅ Tezkor yuklash\n\n"
            "📦 Tarifni tanlang:",
            reply_markup=flash_sale_tariffs_kb(tariffs, is_discount=False)
        )


@router.callback_query(F.data.startswith("flash_tariff:"))
async def flash_tariff_callback(callback: CallbackQuery, db_user: User = None):
    """Flash sale tarif tanlash"""
    parts = callback.data.split(":")
    tariff_id = int(parts[1])
    is_discount = parts[2] == "1"

    tariff = await get_tariff_by_id(tariff_id)
    if not tariff:
        await callback.answer("❌ Tarif topilmadi!", show_alert=True)
        return

    # Narx doim qo'yilgan narx (chegirma yo'q, 2x yo'q). Flash sale faqat taymer/urgency;
    # haqiqiy chegirma qo'llanmagani uchun "chegirmali" demaymiz va is_discounted=False.
    price = tariff.price
    price_text = f"{price:,} so'm"
    with_discount = False

    # Karta ma'lumotlarini olish
    from apps.core.models import BotSettings
    settings = await get_bot_settings()

    card_number = esc(settings.card_number) if settings else '8600 1234 5678 9012'
    card_holder = esc(settings.card_holder) if settings else 'CARDHOLDER NAME'
    await callback.message.edit_text(
        await get_message_text(
            'payment_instructions',
            tariff_name=esc(tariff.name),
            days=tariff.days,
            price=price_text,
            amount=f"{price:,}",
            card_number=card_number,
            card_holder=card_holder,
            user_id=callback.from_user.id,
        ),
        reply_markup=back_kb()
    )

    # Pending payment saqlash (bu muhim!)
    await _save_pending_payment_for_flash(
        callback.from_user.id,
        tariff_id,
        price,
        with_discount
    )

    await callback.answer()


@sync_to_async
def _save_pending_payment_for_flash(user_id: int, tariff_id: int, amount: int, with_discount: bool):
    """Flash sale uchun pending to'lovni saqlash"""
    # Eski sessiyalarni tozalash
    PendingPaymentSession.cleanup_expired()

    try:
        user = User.objects.get(user_id=user_id)
        # Eski sessiyani o'chirish
        PendingPaymentSession.objects.filter(user=user).delete()

        # Yangi sessiya yaratish
        expires_at = dj_timezone.now() + timedelta(seconds=PENDING_PAYMENT_TIMEOUT)
        PendingPaymentSession.objects.create(
            user=user,
            tariff_id=tariff_id,
            amount=amount,
            is_discounted=with_discount,
            message_id=0,
            expires_at=expires_at
        )
    except User.DoesNotExist:
        logger.warning(f"Flash sale pending payment: user topilmadi {user_id}")


# ==================== PROFIL ====================

async def _build_profile_text(db_user: User, bot: Bot) -> str:
    """Profil xabari matnini yig'ish (profile_callback va profile_handler uchun yagona manba)."""
    if db_user.is_premium_active:
        status = f"💎 Premium ({db_user.days_left} kun)"
    elif db_user.is_trial_active:
        status = f"🎁 Trial ({db_user.days_left} kun)"
    else:
        status = "👤 Oddiy"

    referrals_count = await get_referrals_count(db_user.user_id)
    bot_username = await get_bot_username(bot)  # keshli - har profilда bot.me() urmaydi

    return await get_message_text(
        'profile_info',
        user_id=db_user.user_id,
        full_name=esc(db_user.full_name),
        status=status,
        premium_status=status,
        movies_watched=format_number(db_user.movies_watched),
        referral_code=db_user.referral_code,
        referrals_count=referrals_count,
        bot_username=bot_username,
        joined_date=format_date(db_user.created_at),
    )


@router.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery, db_user: User = None):
    """Profil"""
    if not db_user:
        await callback.answer("❌ Xatolik.", show_alert=True)
        return

    await callback.message.edit_text(
        await _build_profile_text(db_user, callback.bot),
        reply_markup=back_kb()
    )
    await callback.answer()


@router.message(Command("profile"))
async def profile_handler(message: Message, db_user: User = None):
    """Profil command"""
    if not db_user:
        await message.answer("❌ Xatolik.")
        return

    await message.answer(
        await _build_profile_text(db_user, message.bot),
        reply_markup=back_kb()
    )


# ==================== NOOP ====================

@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    """No operation"""
    await callback.answer()


# ==================== SAQLANGAN KINOLAR ====================

@router.callback_query(F.data == "saved_movies")
async def saved_movies_callback(callback: CallbackQuery, db_user: User = None):
    """Saqlangan kinolar"""
    if not db_user:
        await callback.answer("❌ Xatolik!", show_alert=True)
        return

    movies, total_pages = await get_saved_movies(db_user.user_id, page=1)

    if not movies:
        await callback.message.edit_text(
            "❤️ <b>Saqlangan kinolar</b>\n\n"
            "📭 Sizda hali saqlangan kinolar yo'q.\n\n"
            "Kino ko'rganingizda ❤️ Saqlash tugmasini bosing.",
            reply_markup=back_kb()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"❤️ <b>Saqlangan kinolar</b>\n\n"
        f"Jami: {len(movies)} ta kino\n"
        "Tanlang:",
        reply_markup=saved_movies_kb(movies, page=1, total_pages=total_pages)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("saved_page:"))
async def saved_movies_page_callback(callback: CallbackQuery, db_user: User = None):
    """Saqlangan kinolar pagination"""
    if not db_user:
        await callback.answer("❌ Xatolik!", show_alert=True)
        return

    page = int(callback.data.split(":")[1])
    movies, total_pages = await get_saved_movies(db_user.user_id, page=page)

    await callback.message.edit_text(
        f"❤️ <b>Saqlangan kinolar</b>\n\n"
        "Tanlang:",
        reply_markup=saved_movies_kb(movies, page=page, total_pages=total_pages)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("save:"))
async def save_movie_callback(callback: CallbackQuery, db_user: User = None):
    """Kinoni saqlash"""
    if not db_user:
        await callback.answer("❌ Avval ro'yxatdan o'ting!", show_alert=True)
        return

    movie_code = callback.data.split(":")[1]

    # Input validation
    if not movie_code.isdigit() or len(movie_code) > MAX_MOVIE_CODE_LENGTH:
        await callback.answer("❌ Noto'g'ri kod!", show_alert=True)
        return

    result = await save_movie_to_favorites(db_user.user_id, movie_code)

    if result:
        await callback.answer("❤️ Kino saqlandi!", show_alert=True)
        # Tugmani yangilash
        try:
            await callback.message.edit_reply_markup(
                reply_markup=movie_action_kb(movie_code, is_saved=True)
            )
        except TelegramBadRequest as e:
            logger.debug(f"Tugmani yangilashda xatolik: {e}")
    else:
        await callback.answer("❌ Xatolik yoki allaqachon saqlangan!", show_alert=True)


@router.callback_query(F.data.startswith("unsave:"))
async def unsave_movie_callback(callback: CallbackQuery, db_user: User = None):
    """Kinoni saqlanganlardan o'chirish"""
    if not db_user:
        await callback.answer("❌ Xatolik!", show_alert=True)
        return

    movie_code = callback.data.split(":")[1]

    # Input validation
    if not movie_code.isdigit() or len(movie_code) > MAX_MOVIE_CODE_LENGTH:
        await callback.answer("❌ Noto'g'ri kod!", show_alert=True)
        return

    result = await remove_movie_from_favorites(db_user.user_id, movie_code)

    if result:
        await callback.answer("💔 Saqlanganlardan o'chirildi!", show_alert=True)
        # Tugmani yangilash
        try:
            await callback.message.edit_reply_markup(
                reply_markup=movie_action_kb(movie_code, is_saved=False)
            )
        except TelegramBadRequest as e:
            logger.debug(f"Tugmani yangilashda xatolik: {e}")
    else:
        await callback.answer("❌ Xatolik!", show_alert=True)


@router.callback_query(F.data.startswith("saved_movie:"))
async def saved_movie_callback(callback: CallbackQuery, db_user: User = None, bot: Bot = None):
    """Saqlangan kinoni ko'rish"""
    code = callback.data.split(":")[1]
    movie = await get_movie_by_code_db(code)

    if not movie:
        await callback.answer("❌ Kino topilmadi!", show_alert=True)
        return

    # Premium check
    if movie.is_premium and not (db_user and db_user.is_premium_active):
        await callback.answer("💎 Bu Premium kino!", show_alert=True)
        return

    await callback.answer()

    try:
        bot_info = await bot.me()
        bot_link = f"https://t.me/{bot_info.username}"

        desc = f"\n📖 {esc(movie.description)}" if movie.description else ""
        year_text = f" • 📅 {movie.year}" if movie.year else ""

        await send_movie_or_notice(
            callback.message, movie,
            (
                f"❤️ <b>Saqlangan kino:</b>\n\n"
                f"🎬 <b>{esc(movie.display_title)}</b>{desc}\n\n"
                f"📝 Kod: <code>{esc(movie.code)}</code>\n"
                f"📺 {movie.get_quality_display()} • 🌐 {movie.get_language_display()}{year_text}\n"
                f"👁 {format_number(movie.views)}\n\n"
                f"🤖 <b>Bot:</b> {bot_link}"
            ),
            movie_action_kb(movie.code, is_saved=True)
        )
        await increment_movie_views(movie.id)
    except TelegramBadRequest:
        await callback.message.answer("❌ Xatolik.", reply_markup=back_kb())


@router.callback_query(F.data == "random_movie")
async def random_movie_callback(callback: CallbackQuery, db_user: User = None, bot: Bot = None):
    """Random kino callback"""
    user_id = callback.from_user.id

    # Obunani tekshirish (helper funksiya orqali)
    not_subscribed = await check_user_subscription(bot, user_id, db_user)
    if not_subscribed:
        await callback.answer("❌ Avval kanallarga obuna bo'ling!", show_alert=True)
        return

    movie = await get_random_movie()

    if not movie:
        await callback.answer("📭 Kinolar topilmadi.", show_alert=True)
        return

    if movie.is_premium and not (db_user and db_user.is_premium_active):
        await callback.answer("💎 Premium kino tushdi! Premium oling.", show_alert=True)
        return

    await callback.answer()

    try:
        bot_link = await get_bot_link(bot)

        desc = f"\n📖 {esc(movie.description)}" if movie.description else ""
        year_text = f" • 📅 {movie.year}" if movie.year else ""
        is_saved = await check_movie_saved(user_id, movie.code) if db_user else False

        await send_movie_or_notice(
            callback.message, movie,
            (
                f"🎲 <b>Random kino:</b>\n\n"
                f"🎬 <b>{esc(movie.display_title)}</b>{desc}\n\n"
                f"📝 Kod: <code>{esc(movie.code)}</code>\n"
                f"📺 {movie.get_quality_display()} • 🌐 {movie.get_language_display()}{year_text}\n\n"
                f"🤖 <b>Bot:</b> {bot_link}"
            ),
            movie_action_kb(movie.code, is_saved)
        )
        await increment_movie_views(movie.id)
    except TelegramBadRequest as e:
        logger.error(f"Random callback xatolik: {e}")
        await callback.message.answer("❌ Xatolik.", reply_markup=back_kb())


# ==================== HELP ====================

@router.message(Command("help"))
async def help_handler(message: Message):
    """Yordam"""
    await message.answer(
        "ℹ️ <b>Yordam</b>\n\n"
        "<b>Buyruqlar:</b>\n"
        "/start - Boshlash\n"
        "/top - Top kinolar\n"
        "/last - Yangilar\n"
        "/rand - Random\n"
        "/categories - Kategoriyalar\n"
        "/premium - Premium\n"
        "/profile - Profil\n\n"
        "🎬 Kino olish uchun kodini yuboring.",
        reply_markup=back_kb()
    )


# ==================== DATABASE FUNCTIONS ====================

async def check_subscription(bot: Bot, user_id: int) -> list:
    """
    Obunani tekshirish. Bajarilmagan barcha kanallar birga qaytadi (Telegram + Instagram).

    - Telegram kanal/guruh (checkable): MAJBURIY. get_chat_member bilan tekshiriladi.
      Yopiq kanalga qo'shilish so'rovi (chat_join_request) yuborgan bo'lsa ham
      obuna bo'lgan hisoblanadi (so'rovning o'zi kifoya).
    - Instagram / bot / tashqi (non-checkable): MAJBURIY, lekin bot tekshira olmaydi ->
      foydalanuvchi "obuna bo'ldim" -> Instagram'ga qayta o'tib tasdiqlaydi (ikki tashrif).

    Mantiq bot.utils.compute_missing_channels'да (middleware bilan bir xil).
    """
    channels = await get_active_channels()
    return await compute_missing_channels(bot, user_id, channels)


@sync_to_async
def get_active_channels():
    # Barcha aktiv kanallar (Instagram/tashqi ham) - non-checkable kanallar ham
    # tasdiq orqali majburiy qilinadi.
    return list(Channel.objects.filter(is_active=True).order_by('order'))


@sync_to_async
def get_channel_by_pk(pk: int):
    """Kanal olish (Django PK bo'yicha)"""
    try:
        return Channel.objects.get(id=pk)
    except Channel.DoesNotExist:
        return None


@sync_to_async
def get_user_db(user_id):
    try:
        return User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return None


@sync_to_async
def get_movie_by_code_db(code):
    try:
        return Movie.objects.select_related('category').get(code=code)
    except Movie.DoesNotExist:
        return None


@sync_to_async
def search_movies_by_name(query: str, limit: int = 10):
    """Kino nomini qidirish - bosh harfdan boshlab"""
    from django.db.models import Q

    # Qidiruv - nom boshlanishi yoki ichida bo'lishi
    return list(
        Movie.objects.filter(
            Q(title__icontains=query) | Q(title_uz__icontains=query),
            is_active=True
        ).order_by('-views')[:limit]
    )


@sync_to_async
def get_top_movies(limit=10):
    return list(Movie.objects.filter(is_active=True).order_by('-views')[:limit])


@sync_to_async
def get_premium_movies(limit=10):
    """Premium kinolarni olish"""
    return list(Movie.objects.filter(is_active=True, is_premium=True).order_by('-views')[:limit])


@sync_to_async
def get_premium_movies_paginated(page=1, per_page=5):
    """Premium kinolarni sahifalab olish"""
    movies = Movie.objects.filter(is_active=True, is_premium=True).order_by('-created_at')
    total = movies.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    return list(movies[start:start + per_page]), total_pages


@sync_to_async
def get_last_movies(limit=10):
    return list(Movie.objects.filter(is_active=True).order_by('-created_at')[:limit])


@sync_to_async
def get_random_movie():
    movies = Movie.objects.filter(is_active=True)
    count = movies.count()
    if count == 0:
        return None
    return movies[random.randint(0, count - 1)]


@sync_to_async
def get_all_movies(page=1, per_page=8):
    movies = Movie.objects.filter(is_active=True).order_by('-created_at')
    total = movies.count()
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    return list(movies[start:start + per_page]), total_pages


@sync_to_async
def get_categories():
    cache_key = 'categories'
    if cache_key in _categories_cache:
        return _categories_cache[cache_key]

    categories = list(Category.objects.filter(is_active=True).order_by('order'))
    _categories_cache[cache_key] = categories
    return categories


@sync_to_async
def get_movies_by_category(category_id, page=1, per_page=8):
    try:
        category = Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        return [], 0, ""

    movies = Movie.objects.filter(is_active=True, category_id=category_id).order_by('-created_at')
    total = movies.count()
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    return list(movies[start:start + per_page]), total_pages, category.name


@sync_to_async
def get_movies_by_filter(country: str = None, language: str = None, year: int = None, page: int = 1, per_page: int = 8):
    """Filtr bo'yicha kinolar"""
    movies = Movie.objects.filter(is_active=True)

    if country:
        movies = movies.filter(country=country)
    if language:
        movies = movies.filter(language=language)
    if year:
        movies = movies.filter(year=year)

    movies = movies.order_by('-created_at')
    total = movies.count()
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page

    return list(movies[start:start + per_page]), total_pages


@sync_to_async
def get_tariffs():
    return list(Tariff.objects.filter(is_active=True).order_by('order'))


@sync_to_async
def increment_movie_views(movie_id):
    from django.db.models import F
    Movie.objects.filter(id=movie_id).update(views=F('views') + 1)


@sync_to_async
def increment_user_movies(user_id):
    from django.db.models import F
    User.objects.filter(user_id=user_id).update(movies_watched=F('movies_watched') + 1)


@sync_to_async
def get_referrals_count(user_id):
    try:
        user = User.objects.get(user_id=user_id)
        return user.referrals.count()
    except User.DoesNotExist:
        return 0


# ==================== SAQLANGAN KINOLAR DB FUNKSIYALARI ====================

@sync_to_async
def check_movie_saved(user_id: int, movie_code: str) -> bool:
    """Kino saqlanganmi tekshirish"""
    from apps.movies.models import SavedMovie
    try:
        user = User.objects.get(user_id=user_id)
        movie = Movie.objects.get(code=movie_code)
        return SavedMovie.objects.filter(user=user, movie=movie).exists()
    except (User.DoesNotExist, Movie.DoesNotExist):
        return False


@sync_to_async
def save_movie_to_favorites(user_id: int, movie_code: str) -> bool:
    """Kinoni saqlangan ro'yxatga qo'shish"""
    from apps.movies.models import SavedMovie
    try:
        user = User.objects.get(user_id=user_id)
        movie = Movie.objects.get(code=movie_code)

        # Allaqachon saqlangan bo'lsa False qaytarish
        if SavedMovie.objects.filter(user=user, movie=movie).exists():
            return False

        SavedMovie.objects.create(user=user, movie=movie)
        return True
    except (User.DoesNotExist, Movie.DoesNotExist):
        return False


@sync_to_async
def remove_movie_from_favorites(user_id: int, movie_code: str) -> bool:
    """Kinoni saqlanganlardan o'chirish"""
    from apps.movies.models import SavedMovie
    try:
        user = User.objects.get(user_id=user_id)
        movie = Movie.objects.get(code=movie_code)
        deleted, _ = SavedMovie.objects.filter(user=user, movie=movie).delete()
        return deleted > 0
    except (User.DoesNotExist, Movie.DoesNotExist):
        return False


@sync_to_async
def get_saved_movies(user_id: int, page: int = 1, per_page: int = 8):
    """Foydalanuvchining saqlangan kinolarini olish"""
    from apps.movies.models import SavedMovie
    try:
        user = User.objects.get(user_id=user_id)
        saved = SavedMovie.objects.filter(user=user).select_related('movie').order_by('-created_at')
        total = saved.count()
        total_pages = (total + per_page - 1) // per_page
        start = (page - 1) * per_page

        # Movie obyektlarini olish
        movies = [s.movie for s in saved[start:start + per_page]]
        return movies, total_pages
    except User.DoesNotExist:
        return [], 0


# ==================== FLASH SALE FUNKSIYALARI ====================

@sync_to_async
def set_premium_first_view(user_id: int):
    """Foydalanuvchi premium sahifani birinchi marta ko'rganini belgilash"""
    from django.utils import timezone
    try:
        user = User.objects.get(user_id=user_id)
        if not user.premium_first_view:
            user.premium_first_view = timezone.now()
            user.save(update_fields=['premium_first_view'])
        return True
    except User.DoesNotExist:
        return False


@sync_to_async
def get_tariff_by_id(tariff_id: int):
    """Tarif olish"""
    try:
        return Tariff.objects.get(id=tariff_id)
    except Tariff.DoesNotExist:
        return None


@sync_to_async
def get_bot_settings():
    """Bot sozlamalarini olish"""
    from apps.core.models import BotSettings
    return BotSettings.get_settings()
