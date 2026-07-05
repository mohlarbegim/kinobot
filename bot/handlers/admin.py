from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.db.models import Count, Sum, Max

from apps.users.models import User, Admin
from apps.movies.models import Movie, Category
from apps.payments.models import Payment, Tariff
from apps.core.models import Broadcast
from bot.filters import IsAdmin, CanAddMovies, CanBroadcast, CanManageUsers, CanManagePayments, IsSuperAdmin
from bot.states import AddMovieState, EditMovieState, BroadcastState, AddChannelState, EditSettingsState, EditMessageState, UserSearchState, AddCategoryState, EditCategoryState, AddTariffState, EditTariffState
from bot.keyboards import (
    admin_categories_kb, movie_quality_kb, movie_language_kb, movie_country_kb,
    broadcast_target_kb, broadcast_ad_kb, confirm_broadcast_kb,
    cancel_inline_kb, admin_main_kb, skip_inline_kb,
    main_menu_inline_kb, back_kb, admin_messages_kb
)
from apps.channels.models import Channel
from bot.utils import format_number, esc
from bot.middlewares.database import clear_user_cache

router = Router()


# ==================== ADMIN PANEL ====================

@router.message(Command("admin"), IsAdmin())
async def admin_panel(message: Message, state: FSMContext):
    """Admin panel"""
    await state.clear()

    stats = await get_stats()

    text = (
        "👨‍💼 <b>Admin Panel</b>\n\n"
        f"👥 Userlar: {format_number(stats['total_users'])}\n"
        f"🆕 Bugun: +{format_number(stats['today_users'])}\n"
        f"💎 Premium: {format_number(stats['premium_users'])}\n"
        f"🎬 Kinolar: {format_number(stats['total_movies'])}\n"
        f"💳 Kutilmoqda: {format_number(stats['pending_payments'])}"
    )

    await message.answer(text, reply_markup=admin_main_kb())


@router.callback_query(F.data == "admin:panel", IsAdmin())
async def admin_panel_callback(callback: CallbackQuery, state: FSMContext):
    """Admin panel callback"""
    await state.clear()

    stats = await get_stats()

    text = (
        "👨‍💼 <b>Admin Panel</b>\n\n"
        f"👥 Userlar: {format_number(stats['total_users'])}\n"
        f"🆕 Bugun: +{format_number(stats['today_users'])}\n"
        f"💎 Premium: {format_number(stats['premium_users'])}\n"
        f"🎬 Kinolar: {format_number(stats['total_movies'])}\n"
        f"💳 Kutilmoqda: {format_number(stats['pending_payments'])}"
    )

    await callback.message.edit_text(text, reply_markup=admin_main_kb())
    await callback.answer()


# ==================== STATISTIKA ====================

@router.callback_query(F.data == "admin:stats", IsAdmin())
async def stats_handler(callback: CallbackQuery):
    """Batafsil statistika"""
    stats = await get_detailed_stats()

    text = (
        "📊 <b>Statistika</b>\n\n"
        f"👥 <b>Userlar:</b>\n"
        f"├ Jami: {format_number(stats['total_users'])}\n"
        f"├ Bugun: +{format_number(stats['today_users'])}\n"
        f"├ Hafta: +{format_number(stats['week_users'])}\n"
        f"└ Oy: +{format_number(stats['month_users'])}\n\n"
        f"💎 <b>Premium:</b>\n"
        f"├ Premium: {format_number(stats['premium_users'])}\n"
        f"└ Trial: {format_number(stats['trial_users'])}\n\n"
        f"🎬 <b>Kinolar:</b>\n"
        f"├ Jami: {format_number(stats['total_movies'])}\n"
        f"├ Premium: {format_number(stats['premium_movies'])}\n"
        f"└ Ko'rishlar: {format_number(stats['total_views'])}\n\n"
        f"💳 <b>To'lovlar:</b>\n"
        f"├ Kutilmoqda: {format_number(stats['pending_payments'])}\n"
        f"└ Tasdiqlangan: {format_number(stats['approved_payments'])}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Bugungi", callback_data="stats:today"),
         InlineKeyboardButton(text="📊 Haftalik", callback_data="stats:week")],
        [InlineKeyboardButton(text="📉 Oylik", callback_data="stats:month"),
         InlineKeyboardButton(text="📅 Yillik", callback_data="stats:year")],
        [InlineKeyboardButton(text="💎 Premium", callback_data="stats:premium")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ==================== KINOLAR ====================

@router.callback_query(F.data == "admin:movies", IsAdmin())
async def movies_menu(callback: CallbackQuery):
    """Kinolar menyusi"""
    stats = await get_movie_stats()

    text = (
        "🎬 <b>Kinolar</b>\n\n"
        f"📊 Jami: {format_number(stats['total'])}\n"
        f"✅ Aktiv: {format_number(stats['active'])}\n"
        f"💎 Premium: {format_number(stats['premium'])}"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="admin:add_movie")],
        [InlineKeyboardButton(text="📋 Barcha kinolar", callback_data="admin:movies_list:1")],
        [InlineKeyboardButton(text="💎 Premium kinolar", callback_data="admin:premium_movies:1")],
        [InlineKeyboardButton(text="📊 Kinolar statistikasi", callback_data="admin:movies_stats")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:movies_list:"), IsAdmin())
async def admin_movies_list(callback: CallbackQuery):
    """Barcha kinolar ro'yxati"""
    page = int(callback.data.split(":")[2])
    movies, total_pages = await get_admin_movies(page=page)

    if not movies:
        await callback.answer("📭 Kinolar yo'q", show_alert=True)
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()

    for movie in movies:
        prefix = "💎 " if movie.is_premium else "🎬 "
        builder.row(InlineKeyboardButton(
            text=f"{prefix}{movie.display_title} [{movie.code}]",
            callback_data=f"admin:movie_view:{movie.code}"
        ))

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"admin:movies_list:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"admin:movies_list:{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:movies"))

    await callback.message.edit_text(
        f"📋 <b>Barcha kinolar</b>\n\nSahifa: {page}/{total_pages}",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:premium_movies:"), IsAdmin())
async def admin_premium_movies(callback: CallbackQuery):
    """Premium kinolar ro'yxati"""
    page = int(callback.data.split(":")[2])
    movies, total_pages = await get_admin_movies(page=page, premium_only=True)

    if not movies:
        await callback.answer("📭 Premium kinolar yo'q", show_alert=True)
        return

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    for movie in movies:
        builder.row(InlineKeyboardButton(
            text=f"💎 {movie.display_title} [{movie.code}]",
            callback_data=f"admin:movie_view:{movie.code}"
        ))

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"admin:premium_movies:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"admin:premium_movies:{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:movies"))

    await callback.message.edit_text(
        f"💎 <b>Premium kinolar</b>\n\nSahifa: {page}/{total_pages}",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:movie_view:"), IsAdmin())
async def admin_movie_view(callback: CallbackQuery):
    """Kino ma'lumotlari"""
    code = callback.data.split(":")[2]
    movie = await get_movie_by_code(code)

    if not movie:
        await callback.answer("❌ Kino topilmadi", show_alert=True)
        return

    category_name = movie.category.name if movie.category else "Yo'q"
    year_text = str(movie.year) if movie.year else "Yo'q"
    country_text = movie.get_country_display() if hasattr(movie, 'get_country_display') else "Yo'q"

    text = (
        f"🎬 <b>{esc(movie.display_title)}</b>\n\n"
        f"📝 Kod: <code>{movie.code}</code>\n"
        f"🎭 Janr: {category_name}\n"
        f"📅 Yil: {year_text}\n"
        f"🌍 Davlat: {country_text}\n"
        f"📺 Sifat: {movie.get_quality_display()}\n"
        f"🌐 Til: {movie.get_language_display()}\n"
        f"💎 Premium: {'Ha' if movie.is_premium else 'Yo`q'}\n"
        f"👁 Ko'rishlar: {format_number(movie.views)}\n"
        f"✅ Aktiv: {'Ha' if movie.is_active else 'Yo`q'}"
    )

    toggle_text = "❌ Deaktiv" if movie.is_active else "✅ Aktiv"
    premium_text = "🆓 Oddiy qilish" if movie.is_premium else "💎 Premium qilish"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"admin:movie_edit:{movie.code}")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"admin:movie_toggle:{movie.code}")],
        [InlineKeyboardButton(text=premium_text, callback_data=f"admin:movie_premium:{movie.code}")],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin:movie_delete:{movie.code}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:movies_list:1")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:movie_toggle:"), IsAdmin())
async def admin_movie_toggle(callback: CallbackQuery):
    """Kino aktiv/deaktiv"""
    code = callback.data.split(":")[2]
    new_status = await toggle_movie_status(code)
    status_text = "aktiv" if new_status else "deaktiv"
    await callback.answer(f"✅ Kino {status_text} qilindi!", show_alert=True)


@router.callback_query(F.data.startswith("admin:movie_premium:"), IsAdmin())
async def admin_movie_premium(callback: CallbackQuery):
    """Kino premium/oddiy"""
    code = callback.data.split(":")[2]
    new_status = await toggle_movie_premium(code)
    status_text = "Premium" if new_status else "Oddiy"
    await callback.answer(f"✅ Kino {status_text} qilindi!", show_alert=True)


@router.callback_query(F.data.startswith("admin:movie_delete:"), IsAdmin())
async def admin_movie_delete(callback: CallbackQuery):
    """Kinoni o'chirish - tasdiqlash"""
    code = callback.data.split(":")[2]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"admin:movie_delete_confirm:{code}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data=f"admin:movie_view:{code}")
        ]
    ])

    await callback.message.edit_text(
        f"⚠️ <b>{code}</b> kodli kinoni o'chirishni tasdiqlaysizmi?\n\n"
        "Bu amalni qaytarib bo'lmaydi!",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:movie_delete_confirm:"), IsAdmin())
async def admin_movie_delete_confirm(callback: CallbackQuery):
    """Kinoni o'chirish - tasdiqlangan"""
    code = callback.data.split(":")[2]
    result = await delete_movie(code)

    if result:
        await callback.answer("✅ Kino o'chirildi!", show_alert=True)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Kinolar ro'yxati", callback_data="admin:movies_list:1")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:movies")]
        ])
        await callback.message.edit_text("✅ Kino muvaffaqiyatli o'chirildi!", reply_markup=kb)
    else:
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)


# ==================== KINO TAHRIRLASH ====================

_MEDIT_FIELD_LABELS = {
    'title': 'Nom',
    'video': 'Video',
    'poster': 'Poster',
    'category': 'Janr',
    'year': 'Yil',
    'description': 'Tavsif',
    'code': 'Kod',
}


@router.callback_query(F.data.startswith("admin:movie_edit:"), IsAdmin())
async def admin_movie_edit_menu(callback: CallbackQuery, state: FSMContext):
    """Kino tahrirlash menyusi — qaysi maydonni o'zgartirish tanlanadi."""
    await state.clear()
    code = callback.data.split(":", 2)[2]
    movie = await get_movie_by_code(code)
    if not movie:
        await callback.answer("❌ Kino topilmadi", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Nom", callback_data=f"admin:medit:title:{code}")],
        [InlineKeyboardButton(text="🎬 Video", callback_data=f"admin:medit:video:{code}")],
        [InlineKeyboardButton(text="🖼 Poster", callback_data=f"admin:medit:poster:{code}")],
        [InlineKeyboardButton(text="🎭 Janr", callback_data=f"admin:medit:category:{code}")],
        [InlineKeyboardButton(text="📅 Yil", callback_data=f"admin:medit:year:{code}")],
        [InlineKeyboardButton(text="📖 Tavsif", callback_data=f"admin:medit:description:{code}")],
        [InlineKeyboardButton(text="🔢 Kod", callback_data=f"admin:medit:code:{code}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"admin:movie_view:{code}")],
    ])
    await callback.message.edit_text(
        f"✏️ <b>{esc(movie.display_title)}</b>\n📝 Kod: <code>{movie.code}</code>\n\n"
        "Qaysi maydonni tahrirlaymiz?",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:medit:"), IsAdmin())
async def admin_movie_edit_field(callback: CallbackQuery, state: FSMContext):
    """Tahrirlash maydonini tanlash — matn/video so'raladi yoki janr klaviaturasi ko'rsatiladi."""
    # admin:medit:<field>:<code>
    parts = callback.data.split(":")
    field = parts[2]
    code = parts[3]

    if field not in _MEDIT_FIELD_LABELS:
        await callback.answer("❌ Noma'lum maydon", show_alert=True)
        return

    movie = await get_movie_by_code(code)
    if not movie:
        await callback.answer("❌ Kino topilmadi", show_alert=True)
        return

    await state.update_data(edit_code=code, edit_field=field)
    await state.set_state(EditMovieState.value)

    if field == 'category':
        categories = await get_categories()
        rows = [[InlineKeyboardButton(text=(c.name), callback_data=f"medit_cat:{c.id}")] for c in categories]
        rows.append([InlineKeyboardButton(text="🚫 Janrsiz", callback_data="medit_cat:none")])
        rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")])
        await callback.message.edit_text(
            f"🎭 <b>{esc(movie.display_title)}</b> uchun yangi janrni tanlang:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
        )
    elif field == 'video':
        await callback.message.edit_text(
            f"🎬 <b>{esc(movie.display_title)}</b> uchun yangi <b>video</b> faylini yuboring:",
            reply_markup=cancel_inline_kb()
        )
    elif field == 'poster':
        await callback.message.edit_text(
            f"🖼 <b>{esc(movie.display_title)}</b> uchun yangi <b>poster rasm</b>ni yuboring:",
            reply_markup=cancel_inline_kb()
        )
    else:
        prompts = {
            'title': "📝 Yangi nomni kiriting:",
            'year': "📅 Yangi yilni kiriting (masalan: 2020):",
            'description': "📖 Yangi tavsifni kiriting:",
            'code': "🔢 Yangi kodni kiriting (faqat raqam):",
        }
        await callback.message.edit_text(
            f"<b>{esc(movie.display_title)}</b>\n\n{prompts[field]}",
            reply_markup=cancel_inline_kb()
        )
    await callback.answer()


def _medit_result_kb(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Yana tahrirlash", callback_data=f"admin:movie_edit:{code}")],
        [InlineKeyboardButton(text="🎬 Kinoga qaytish", callback_data=f"admin:movie_view:{code}")],
    ])


@router.callback_query(EditMovieState.value, F.data.startswith("medit_cat:"), IsAdmin())
async def admin_movie_edit_category(callback: CallbackQuery, state: FSMContext):
    """Yangi janrni saqlash."""
    data = await state.get_data()
    code = data.get('edit_code')
    cat_raw = callback.data.split(":")[1]
    category_id = None if cat_raw == "none" else int(cat_raw)

    movie, err = await edit_movie_field(code, 'category_id', category_id)
    await state.clear()
    if err or not movie:
        await callback.answer("❌ Kino topilmadi", show_alert=True)
        return
    cat_name = movie.category.name if movie.category else "Janrsiz"
    await callback.message.edit_text(
        f"✅ Janr yangilandi: <b>{esc(cat_name)}</b>",
        reply_markup=_medit_result_kb(movie.code)
    )
    await callback.answer("✅ Saqlandi!")


@router.message(EditMovieState.value, F.video | F.document)
async def admin_movie_edit_video(message: Message, state: FSMContext):
    """Yangi videoni saqlash."""
    data = await state.get_data()
    code = data.get('edit_code')
    field = data.get('edit_field')
    if field != 'video':
        await message.answer("❌ Bu bosqichda matn kiriting.", reply_markup=cancel_inline_kb())
        return

    if message.video:
        file_id = message.video.file_id
    elif message.document and message.document.mime_type and message.document.mime_type.startswith('video/'):
        file_id = message.document.file_id
    else:
        await message.answer("❌ Faqat video fayl yuboring.", reply_markup=cancel_inline_kb())
        return

    movie, err = await edit_movie_field(code, 'file_id', file_id)
    await state.clear()
    if err or not movie:
        await message.answer("❌ Kino topilmadi.")
        return
    await message.answer("✅ Video yangilandi!", reply_markup=_medit_result_kb(movie.code))


@router.message(EditMovieState.value, F.photo)
async def admin_movie_edit_photo(message: Message, state: FSMContext):
    """Yangi poster rasmini saqlash."""
    data = await state.get_data()
    code = data.get('edit_code')
    field = data.get('edit_field')
    if field != 'poster':
        await message.answer("❌ Bu bosqichda rasm kutilmayapti.", reply_markup=cancel_inline_kb())
        return

    file_id = message.photo[-1].file_id
    movie, err = await edit_movie_field(code, 'thumbnail_file_id', file_id)
    await state.clear()
    if err or not movie:
        await message.answer("❌ Kino topilmadi.")
        return
    await message.answer("✅ Poster yangilandi!", reply_markup=_medit_result_kb(movie.code))


@router.message(EditMovieState.value, F.text)
async def admin_movie_edit_text(message: Message, state: FSMContext):
    """Matnli maydonlarni (nom/yil/tavsif/kod) saqlash."""
    data = await state.get_data()
    code = data.get('edit_code')
    field = data.get('edit_field')
    if not code or not field:
        await state.clear()
        return

    val = message.text.strip()

    if field == 'year':
        if not val.isdigit() or not (1900 <= int(val) <= 2100):
            await message.answer("❌ Yil noto'g'ri (1900-2100 oralig'ida raqam).", reply_markup=cancel_inline_kb())
            return
        value = int(val)
    elif field == 'code':
        if not val.isdigit():
            await message.answer("❌ Kod faqat raqam bo'lishi kerak.", reply_markup=cancel_inline_kb())
            return
        value = val
    elif field == 'title':
        if not val or len(val) > 255:
            await message.answer("❌ Nom 1-255 belgidan iborat bo'lishi kerak.", reply_markup=cancel_inline_kb())
            return
        value = val
    elif field == 'description':
        if len(val) > 2000:
            await message.answer("❌ Tavsif juda uzun (max 2000 belgi).", reply_markup=cancel_inline_kb())
            return
        value = val
    elif field == 'video':
        await message.answer("❌ Bu bosqichda video fayl yuboring (matn emas).", reply_markup=cancel_inline_kb())
        return
    elif field == 'poster':
        await message.answer("❌ Bu bosqichda poster rasm yuboring (matn emas).", reply_markup=cancel_inline_kb())
        return
    else:
        await state.clear()
        return

    movie, err = await edit_movie_field(code, field, value)
    if err == 'duplicate':
        await message.answer(
            f"❌ <code>{esc(val)}</code> kodi band. Boshqa kod kiriting:",
            reply_markup=cancel_inline_kb()
        )
        return
    if err or not movie:
        await state.clear()
        await message.answer("❌ Kino topilmadi.")
        return

    await state.clear()
    label = _MEDIT_FIELD_LABELS.get(field, field)
    await message.answer(f"✅ {label} yangilandi!", reply_markup=_medit_result_kb(movie.code))


@router.message(EditMovieState.value)
async def admin_movie_edit_invalid(message: Message, state: FSMContext):
    """Kutilmagan turdagi xabar (masalan video bosqichida rasm) — tushunarli xato."""
    data = await state.get_data()
    field = data.get('edit_field')
    if field == 'video':
        await message.answer(
            "❌ Bu yerga <b>video</b> kerak, rasm emas. Video fayl yuboring.",
            reply_markup=cancel_inline_kb()
        )
    else:
        await message.answer("❌ Iltimos matn kiriting.", reply_markup=cancel_inline_kb())


@router.callback_query(F.data == "admin:movies_stats", IsAdmin())
async def admin_movies_stats_handler(callback: CallbackQuery):
    """Kinolar statistikasi"""
    stats = await get_detailed_movie_stats()

    text = (
        "📊 <b>Kinolar statistikasi</b>\n\n"
        f"📈 Jami kinolar: {format_number(stats['total'])}\n"
        f"✅ Aktiv: {format_number(stats['active'])}\n"
        f"❌ Deaktiv: {format_number(stats['inactive'])}\n"
        f"💎 Premium: {format_number(stats['premium'])}\n"
        f"🆓 Oddiy: {format_number(stats['regular'])}\n\n"
        f"👁 Jami ko'rishlar: {format_number(stats['total_views'])}\n"
        f"📊 O'rtacha ko'rish: {stats['avg_views']}\n\n"
        f"🔝 <b>Eng ko'p ko'rilgan:</b>\n"
    )

    for i, movie in enumerate(stats['top_movies'], 1):
        text += f"{i}. {movie['title']} - {format_number(movie['views'])}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:movies")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.message(Command("addmovie"), CanAddMovies())
async def add_movie_start(message: Message, state: FSMContext):
    """Kino qo'shishni boshlash"""
    await state.set_state(AddMovieState.code)
    await message.answer(
        "🎬 <b>Kino qo'shish</b>\n\n"
        "1️⃣ Kino kodini kiriting:\n"
        "<i>Masalan: 123</i>",
        reply_markup=cancel_inline_kb()
    )


@router.callback_query(F.data == "admin:add_movie", CanAddMovies())
async def add_movie_start_callback(callback: CallbackQuery, state: FSMContext):
    """Kino qo'shishni boshlash callback"""
    await state.set_state(AddMovieState.code)
    await callback.message.edit_text(
        "🎬 <b>Kino qo'shish</b>\n\n"
        "1️⃣ Kino kodini kiriting:\n"
        "<i>Masalan: 123</i>",
        reply_markup=cancel_inline_kb()
    )
    await callback.answer()


@router.message(AddMovieState.code, F.text)
async def add_movie_code(message: Message, state: FSMContext):
    """Kino kodi"""
    code = message.text.strip()

    # Faqat raqam bo'lishi kerak
    if not code.isdigit():
        await message.answer(
            "❌ Kod faqat raqam bo'lishi kerak!\n\n"
            "<i>Masalan: 123</i>",
            reply_markup=cancel_inline_kb()
        )
        return

    # Tekshirish
    exists = await check_movie_exists(code)
    if exists:
        await message.answer(
            f"❌ <code>{code}</code> kodi band.\n\n"
            "Boshqa kod kiriting:",
            reply_markup=cancel_inline_kb()
        )
        return

    await state.update_data(code=code)
    await state.set_state(AddMovieState.title)
    await message.answer(
        f"✅ Kod: <code>{code}</code>\n\n"
        "2️⃣ Kino nomini kiriting:",
        reply_markup=cancel_inline_kb()
    )


@router.message(AddMovieState.title, F.text)
async def add_movie_title(message: Message, state: FSMContext):
    """Kino nomi"""
    data = await state.get_data()
    await state.update_data(title=message.text.strip())
    await state.set_state(AddMovieState.video)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Videosiz o'tkazib yuborish", callback_data="video:skip")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])
    await message.answer(
        f"✅ Kod: <code>{data.get('code')}</code>\n"
        f"✅ Nom: {message.text.strip()}\n\n"
        "3️⃣ <b>Video</b> faylni <b>yoki poster rasmни</b> yuboring:\n"
        "<i>• Video yuborsangiz — kino o'sha video bo'ladi.\n"
        "• Rasm yuborsangiz — poster bo'ladi (videosiz kino).\n"
        "• Yoki «⏭ Videosiz o'tkazib yuborish»ni bosing.</i>",
        reply_markup=kb
    )


@router.message(AddMovieState.video, F.video | F.document)
async def add_movie_video(message: Message, state: FSMContext):
    """Video fayl"""
    if message.video:
        file_id = message.video.file_id
    elif message.document:
        if message.document.mime_type and message.document.mime_type.startswith('video/'):
            file_id = message.document.file_id
        else:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭ Videosiz o'tkazib yuborish", callback_data="video:skip")],
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
            ])
            await message.answer("❌ Faqat video fayl!", reply_markup=kb)
            return
    else:
        return

    data = await state.get_data()
    await state.update_data(file_id=file_id)
    await state.set_state(AddMovieState.category)

    categories = await get_categories()

    if categories:
        await message.answer(
            f"✅ Kod: <code>{data.get('code')}</code>\n"
            f"✅ Nom: {data.get('title')}\n"
            "✅ Video qabul qilindi\n\n"
            "4️⃣ Janrni tanlang:",
            reply_markup=admin_categories_kb(categories)
        )
    else:
        await state.update_data(category_id=None)
        await state.set_state(AddMovieState.quality)
        await message.answer(
            f"✅ Kod: <code>{data.get('code')}</code>\n"
            f"✅ Nom: {data.get('title')}\n"
            "✅ Video qabul qilindi\n\n"
            "4️⃣ Sifatni tanlang:",
            reply_markup=movie_quality_kb()
        )


@router.callback_query(AddMovieState.video, F.data == "video:skip")
async def add_movie_video_skip(callback: CallbackQuery, state: FSMContext):
    """Videoni o'tkazib yuborish - kino videosiz qo'shiladi (video keyin yuklanadi)."""
    data = await state.get_data()
    await state.update_data(file_id="")
    await state.set_state(AddMovieState.category)

    note = "⏭ Video o'tkazildi (keyin qo'shiladi)"
    categories = await get_categories()

    if categories:
        await callback.message.edit_text(
            f"✅ Kod: <code>{data.get('code')}</code>\n"
            f"✅ Nom: {data.get('title')}\n"
            f"{note}\n\n"
            "4️⃣ Janrni tanlang:",
            reply_markup=admin_categories_kb(categories)
        )
    else:
        await state.update_data(category_id=None)
        await state.set_state(AddMovieState.quality)
        await callback.message.edit_text(
            f"✅ Kod: <code>{data.get('code')}</code>\n"
            f"✅ Nom: {data.get('title')}\n"
            f"{note}\n\n"
            "4️⃣ Sifatni tanlang:",
            reply_markup=movie_quality_kb()
        )
    await callback.answer()


@router.message(AddMovieState.video, F.photo)
async def add_movie_photo(message: Message, state: FSMContext):
    """Rasm yuborilsa — poster (thumbnail) sifatida saqlaymiz, kino videosiz bo'ladi."""
    poster_id = message.photo[-1].file_id
    data = await state.get_data()
    await state.update_data(file_id="", thumbnail_file_id=poster_id)
    await state.set_state(AddMovieState.category)

    note = "🖼 Poster qabul qilindi (videosiz kino)"
    categories = await get_categories()
    if categories:
        await message.answer(
            f"✅ Kod: <code>{data.get('code')}</code>\n"
            f"✅ Nom: {data.get('title')}\n"
            f"{note}\n\n"
            "4️⃣ Janrni tanlang:",
            reply_markup=admin_categories_kb(categories)
        )
    else:
        await state.update_data(category_id=None)
        await state.set_state(AddMovieState.quality)
        await message.answer(
            f"✅ Kod: <code>{data.get('code')}</code>\n"
            f"✅ Nom: {data.get('title')}\n"
            f"{note}\n\n"
            "4️⃣ Sifatni tanlang:",
            reply_markup=movie_quality_kb()
        )


@router.message(AddMovieState.video)
async def add_movie_video_invalid(message: Message, state: FSMContext):
    """Video/rasm EMAS narsa (matn/stiker) yuborilsa tushunarli xato."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Videosiz o'tkazib yuborish", callback_data="video:skip")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])
    await message.answer(
        "❌ Bu bosqichda <b>video</b> yoki <b>poster rasm</b> kerak.\n\n"
        "🎬 Kino video faylini yoki poster rasmni yuboring "
        "(yoki «⏭ Videosiz o'tkazib yuborish»ni bosing).",
        reply_markup=kb
    )


@router.callback_query(AddMovieState.category, F.data.startswith("admin_category:"))
async def add_movie_category(callback: CallbackQuery, state: FSMContext):
    """Janr tanlash"""
    cat_data = callback.data.split(":")[1]
    data = await state.get_data()

    if cat_data == "skip":
        category_id = None
        cat_text = "O'tkazildi"
    else:
        category_id = int(cat_data)
        category = await get_category_by_id(category_id)
        cat_text = category.name if category else "Tanlandi"

    await state.update_data(category_id=category_id)
    await state.set_state(AddMovieState.year)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="year:skip")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])

    await callback.message.edit_text(
        f"✅ Kod: <code>{data.get('code')}</code>\n"
        f"✅ Nom: {data.get('title')}\n"
        f"✅ Janr: {cat_text}\n\n"
        "5️⃣ Kino yilini kiriting:\n"
        "<i>Masalan: 2024</i>",
        reply_markup=kb
    )
    await callback.answer()


@router.message(AddMovieState.year, F.text)
async def add_movie_year(message: Message, state: FSMContext):
    """Kino yili"""
    year_text = message.text.strip()

    if not year_text.isdigit() or len(year_text) != 4:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="year:skip")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
        ])
        await message.answer(
            "❌ Noto'g'ri format! 4 xonali yil kiriting.\n"
            "<i>Masalan: 2024</i>",
            reply_markup=kb
        )
        return

    year = int(year_text)
    if year < 1900 or year > 2030:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="year:skip")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
        ])
        await message.answer(
            "❌ Yil 1900-2030 oralig'ida bo'lishi kerak!",
            reply_markup=kb
        )
        return

    data = await state.get_data()
    await state.update_data(year=year)
    await state.set_state(AddMovieState.country)

    await message.answer(
        f"✅ Kod: <code>{data.get('code')}</code>\n"
        f"✅ Nom: {data.get('title')}\n"
        f"✅ Yil: {year}\n\n"
        "6️⃣ Davlatni tanlang:",
        reply_markup=movie_country_kb()
    )


@router.callback_query(AddMovieState.year, F.data == "year:skip")
async def add_movie_year_skip(callback: CallbackQuery, state: FSMContext):
    """Yilni o'tkazib yuborish"""
    data = await state.get_data()
    await state.update_data(year=None)
    await state.set_state(AddMovieState.country)

    await callback.message.edit_text(
        f"✅ Kod: <code>{data.get('code')}</code>\n"
        f"✅ Nom: {data.get('title')}\n"
        f"✅ Yil: O'tkazildi\n\n"
        "6️⃣ Davlatni tanlang:",
        reply_markup=movie_country_kb()
    )
    await callback.answer()


@router.callback_query(AddMovieState.country, F.data.startswith("country:"))
async def add_movie_country(callback: CallbackQuery, state: FSMContext):
    """Davlat tanlash"""
    country = callback.data.split(":")[1]
    data = await state.get_data()
    await state.update_data(country=country)
    await state.set_state(AddMovieState.quality)

    country_display = {
        'usa': '🇺🇸 AQSH', 'korea': '🇰🇷 Koreya', 'india': '🇮🇳 Hindiston',
        'turkey': '🇹🇷 Turkiya', 'russia': '🇷🇺 Rossiya', 'uzbekistan': '🇺🇿 O\'zbekiston',
        'uk': '🇬🇧 Britaniya', 'france': '🇫🇷 Fransiya', 'japan': '🇯🇵 Yaponiya',
        'china': '🇨🇳 Xitoy', 'other': '🌍 Boshqa'
    }.get(country, country)

    await callback.message.edit_text(
        f"✅ Kod: <code>{data.get('code')}</code>\n"
        f"✅ Nom: {data.get('title')}\n"
        f"✅ Davlat: {country_display}\n\n"
        "7️⃣ Sifatni tanlang:",
        reply_markup=movie_quality_kb()
    )
    await callback.answer()


@router.callback_query(AddMovieState.quality, F.data.startswith("quality:"))
async def add_movie_quality(callback: CallbackQuery, state: FSMContext):
    """Sifat tanlash"""
    quality = callback.data.split(":")[1]
    data = await state.get_data()
    await state.update_data(quality=quality)
    await state.set_state(AddMovieState.language)

    await callback.message.edit_text(
        f"✅ Kod: <code>{data.get('code')}</code>\n"
        f"✅ Nom: {data.get('title')}\n"
        f"✅ Sifat: {quality}\n\n"
        "6️⃣ Tilni tanlang:",
        reply_markup=movie_language_kb()
    )
    await callback.answer()


@router.callback_query(AddMovieState.language, F.data.startswith("language:"))
async def add_movie_language(callback: CallbackQuery, state: FSMContext):
    """Til tanlash - tavsif bosqichiga o'tish"""
    language = callback.data.split(":")[1]
    data = await state.get_data()
    await state.update_data(language=language)
    await state.set_state(AddMovieState.description)

    language_display = {
        'uzbek': "🇺🇿 O'zbek", 'rus': "🇷🇺 Rus", 'eng': "🇺🇸 English",
        'turk': "🇹🇷 Turk", 'korea': "🇰🇷 Koreys", 'other': "🌍 Boshqa"
    }.get(language, language)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="description:skip")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])

    await callback.message.edit_text(
        f"✅ Kod: <code>{data.get('code')}</code>\n"
        f"✅ Nom: {data.get('title')}\n"
        f"✅ Til: {language_display}\n\n"
        "9️⃣ Qisqa tavsif kiriting:\n"
        "<i>Kino haqida 1-2 jumla</i>",
        reply_markup=kb
    )
    await callback.answer()


@router.message(AddMovieState.description, F.text)
async def add_movie_description(message: Message, state: FSMContext):
    """Tavsif kiritish"""
    description = message.text.strip()

    if len(description) > 500:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="description:skip")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
        ])
        await message.answer(
            "❌ Tavsif 500 belgidan oshmasligi kerak!\n"
            "Qisqaroq tavsif kiriting:",
            reply_markup=kb
        )
        return

    data = await state.get_data()
    await state.update_data(description=description)
    await state.set_state(AddMovieState.is_premium)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Premium kino", callback_data="is_premium:yes")],
        [InlineKeyboardButton(text="🆓 Oddiy kino", callback_data="is_premium:no")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])

    await message.answer(
        f"✅ Kod: <code>{data.get('code')}</code>\n"
        f"✅ Nom: {data.get('title')}\n"
        f"✅ Tavsif: {description[:50]}...\n\n"
        "🔟 Kino turini tanlang:",
        reply_markup=kb
    )


@router.callback_query(AddMovieState.description, F.data == "description:skip")
async def add_movie_description_skip(callback: CallbackQuery, state: FSMContext):
    """Tavsifni o'tkazib yuborish"""
    data = await state.get_data()
    await state.update_data(description="")
    await state.set_state(AddMovieState.is_premium)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Premium kino", callback_data="is_premium:yes")],
        [InlineKeyboardButton(text="🆓 Oddiy kino", callback_data="is_premium:no")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])

    await callback.message.edit_text(
        f"✅ Kod: <code>{data.get('code')}</code>\n"
        f"✅ Nom: {data.get('title')}\n"
        f"✅ Tavsif: O'tkazildi\n\n"
        "🔟 Kino turini tanlang:",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(AddMovieState.is_premium, F.data.startswith("is_premium:"))
async def add_movie_is_premium(callback: CallbackQuery, state: FSMContext):
    """Premium tanlash - tasdiqlash bosqichi"""
    is_premium = callback.data.split(":")[1] == "yes"
    data = await state.get_data()
    await state.update_data(is_premium=is_premium)
    await state.set_state(AddMovieState.confirm)

    # Ma'lumotlarni tayyorlash
    category_name = "Yo'q"
    if data.get('category_id'):
        category = await get_category_by_id(data['category_id'])
        if category:
            category_name = category.name

    year_text = str(data.get('year')) if data.get('year') else "Yo'q"

    country_display = {
        'usa': '🇺🇸 AQSH', 'korea': '🇰🇷 Koreya', 'india': '🇮🇳 Hindiston',
        'turkey': '🇹🇷 Turkiya', 'russia': '🇷🇺 Rossiya', 'uzbekistan': '🇺🇿 O\'zbekiston',
        'uk': '🇬🇧 Britaniya', 'france': '🇫🇷 Fransiya', 'japan': '🇯🇵 Yaponiya',
        'china': '🇨🇳 Xitoy', 'other': '🌍 Boshqa'
    }.get(data.get('country', 'other'), 'Boshqa')

    quality_display = {
        '360p': '360p', '480p': '480p', '720p': '720p HD',
        '1080p': '1080p FHD', '4k': '4K Ultra'
    }.get(data.get('quality', '720p'), data.get('quality'))

    language_display = {
        'uzbek': "🇺🇿 O'zbek", 'rus': "🇷🇺 Rus", 'eng': "🇺🇸 English",
        'turk': "🇹🇷 Turk", 'korea': "🇰🇷 Koreys", 'other': "🌍 Boshqa"
    }.get(data.get('language', 'uzbek'), data.get('language'))

    desc_text = data.get('description', '')[:100] + "..." if len(data.get('description', '')) > 100 else (data.get('description') or "Yo'q")
    premium_text = "💎 Premium" if is_premium else "🆓 Oddiy"
    video_text = "✅ Yuklangan" if data.get('file_id') else "⏭ Yo'q (keyin qo'shiladi)"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_movie")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])

    await callback.message.edit_text(
        f"📋 <b>Kino ma'lumotlarini tasdiqlang:</b>\n\n"
        f"📝 Kod: <code>{data.get('code')}</code>\n"
        f"🎬 Nom: <b>{data.get('title')}</b>\n"
        f"🎭 Janr: {category_name}\n"
        f"📅 Yil: {year_text}\n"
        f"🌍 Davlat: {country_display}\n"
        f"📺 Sifat: {quality_display}\n"
        f"🌐 Til: {language_display}\n"
        f"📖 Tavsif: {desc_text}\n"
        f"💎 Turi: {premium_text}\n"
        f"🎥 Video: {video_text}\n\n"
        f"<i>Hammasi to'g'rimi?</i>",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(AddMovieState.confirm, F.data == "confirm_movie")
async def add_movie_confirm(callback: CallbackQuery, state: FSMContext, db_user: User = None):
    """Kinoni tasdiqlash va saqlash"""
    data = await state.get_data()
    await state.clear()

    # Kino yaratish
    movie = await create_movie(
        code=data['code'],
        title=data['title'],
        file_id=data.get('file_id', ''),
        thumbnail_file_id=data.get('thumbnail_file_id', ''),
        category_id=data.get('category_id'),
        year=data.get('year'),
        country=data.get('country', 'usa'),
        quality=data.get('quality', '720p'),
        language=data.get('language', 'uzbek'),
        description=data.get('description', ''),
        is_premium=data.get('is_premium', False),
        added_by_id=db_user.user_id if db_user else None
    )

    # Kategoriya nomini olish
    category_name = "Yo'q"
    if data.get('category_id'):
        category = await get_category_by_id(data['category_id'])
        if category:
            category_name = category.name

    premium_text = "💎 Premium" if movie.is_premium else "🆓 Oddiy"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Foydalanuvchilarga xabar berish", callback_data=f"notify_movie:{movie.code}")],
        [InlineKeyboardButton(text="➕ Yana qo'shish", callback_data="admin:add_movie")],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
    ])

    await callback.message.edit_text(
        f"✅ <b>Kino muvaffaqiyatli qo'shildi!</b>\n\n"
        f"📝 Kod: <code>{esc(movie.code)}</code>\n"
        f"🎬 Nom: {esc(movie.title)}\n"
        f"🎭 Janr: {esc(category_name)}\n"
        f"📅 Yil: {movie.year or 'Yo`q'}\n"
        f"🌍 Davlat: {movie.get_country_display()}\n"
        f"📺 Sifat: {movie.get_quality_display()}\n"
        f"🌐 Til: {movie.get_language_display()}\n"
        f"💎 Turi: {premium_text}",
        reply_markup=kb
    )
    await callback.answer("✅ Kino qo'shildi!")


# ==================== YANGI KINO BILDIRISHNOMASI ====================

@router.callback_query(F.data.startswith("notify_movie:"), CanAddMovies())
async def notify_movie_confirm(callback: CallbackQuery):
    """Yangi kino haqida xabar yuborishни tasdiqlash (ommaviy yuborish oldidan)."""
    code = callback.data.split(":", 1)[1]
    movie = await get_movie_by_code(code)
    if not movie:
        await callback.answer("❌ Kino topilmadi", show_alert=True)
        return

    total = await count_active_users()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Ha, yuborish ({total})", callback_data=f"notify_go:{code}")],
        [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin:panel")],
    ])
    await callback.message.edit_text(
        f"🔔 <b>Yangi kino bildirishnomasi</b>\n\n"
        f"🎬 {esc(movie.display_title)} (kod: <code>{movie.code}</code>)\n\n"
        f"Bu xabar <b>{total}</b> ta faol foydalanuvchiga yuboriladi. Tasdiqlaysizmi?",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("notify_go:"), CanAddMovies())
async def notify_movie_send(callback: CallbackQuery, bot: Bot = None):
    """Yangi kino haqida barcha faol userlarga xabar yuborish (rate-limited)."""
    import asyncio
    code = callback.data.split(":", 1)[1]
    movie = await get_movie_by_code(code)
    if not movie:
        await callback.answer("❌ Kino topilmadi", show_alert=True)
        return

    users = await get_active_user_ids()
    await callback.message.edit_text(f"🔔 Yuborilmoqda... 0/{len(users)}")
    await callback.answer()

    premium_note = "💎 <i>Premium kino</i>\n" if movie.is_premium else ""
    text = (
        f"🆕 <b>Yangi kino qo'shildi!</b>\n\n"
        f"🎬 <b>{esc(movie.display_title)}</b>\n"
        f"{premium_note}"
        f"📝 Kod: <code>{esc(movie.code)}</code>\n\n"
        f"Ko'rish uchun kodni yuboring 👆"
    )

    sent = 0
    failed = 0
    for uid in users:
        try:
            await bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
        if (sent + failed) % 20 == 0:
            try:
                await callback.message.edit_text(f"🔔 Yuborilmoqda... {sent + failed}/{len(users)}")
            except TelegramBadRequest:
                pass
        await asyncio.sleep(0.05)  # Rate limit

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
    ])
    await callback.message.edit_text(
        f"✅ <b>Bildirishnoma yuborildi!</b>\n\n"
        f"📊 Jami: {len(users)}\n✅ Yuborildi: {sent}\n❌ Xato: {failed}",
        reply_markup=kb
    )


@router.callback_query(F.data == "cancel", IsAdmin())
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    """Bekor qilish"""
    await state.clear()

    await callback.message.edit_text(
        "❌ Bekor qilindi.",
        reply_markup=admin_main_kb()
    )
    await callback.answer()


@router.message(F.text == "❌ Bekor qilish", IsAdmin())
async def cancel_message_handler(message: Message, state: FSMContext):
    """Bekor qilish message"""
    await state.clear()
    await message.answer("❌ Bekor qilindi.", reply_markup=main_menu_inline_kb(is_admin=True))


@router.callback_query(F.data == "cancel_old")
async def cancel_handler_old(event, state: FSMContext):
    """Bekor qilish old"""
    await state.clear()

    if isinstance(event, CallbackQuery):
        await event.message.edit_text("❌ Bekor qilindi.", reply_markup=admin_main_kb())
        await event.answer()


# ==================== JANRLAR (KATEGORIYALAR) ====================

@router.callback_query(F.data == "admin:categories", IsAdmin())
async def categories_menu(callback: CallbackQuery):
    """Janrlar menyusi"""
    categories = await get_all_categories()

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()

    if categories:
        for cat in categories:
            status = "✅" if cat.is_active else "❌"
            emoji = cat.emoji or "🎬"
            movies_count = await get_category_movies_count(cat.id)
            builder.row(InlineKeyboardButton(
                text=f"{status} {emoji} {cat.name} ({movies_count})",
                callback_data=f"cat:view:{cat.id}"
            ))

    builder.row(InlineKeyboardButton(text="➕ Janr qo'shish", callback_data="cat:add"))
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel"))

    text = "🎭 <b>Janrlar boshqaruvi</b>\n\n"
    if categories:
        text += f"Jami: {len(categories)} ta janr\n"
        text += "Janrni bosib tahrirlang."
    else:
        text += "📭 Hozircha janrlar yo'q.\n➕ Janr qo'shish tugmasini bosing."

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "cat:add", IsAdmin())
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    """Janr qo'shishni boshlash"""
    await state.set_state(AddCategoryState.name)
    await callback.message.edit_text(
        "🎭 <b>Yangi janr qo'shish</b>\n\n"
        "Janr nomini kiriting:\n"
        "Masalan: <code>Komediya</code>",
        reply_markup=cancel_inline_kb()
    )
    await callback.answer()


@router.message(AddCategoryState.name, F.text)
async def add_category_name(message: Message, state: FSMContext):
    """Janr nomi"""
    name = message.text.strip()

    if len(name) < 2:
        await message.answer(
            "❌ Janr nomi kamida 2 ta harfdan iborat bo'lishi kerak!",
            reply_markup=cancel_inline_kb()
        )
        return

    # Mavjudligini tekshirish
    exists = await check_category_exists(name)
    if exists:
        await message.answer(
            f"❌ <b>{name}</b> nomli janr allaqachon mavjud!",
            reply_markup=cancel_inline_kb()
        )
        return

    await state.update_data(name=name)
    await state.set_state(AddCategoryState.emoji)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="cat:skip_emoji")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])

    await message.answer(
        f"✅ Nom: <b>{name}</b>\n\n"
        "Janr uchun emoji kiriting:\n"
        "Masalan: 😂 🎬 🔥 💀",
        reply_markup=kb
    )


@router.message(AddCategoryState.emoji, F.text)
async def add_category_emoji(message: Message, state: FSMContext):
    """Janr emoji"""
    emoji = message.text.strip()

    if len(emoji) > 5:
        await message.answer(
            "❌ Emoji juda uzun! Faqat 1-2 ta emoji kiriting.",
            reply_markup=cancel_inline_kb()
        )
        return

    data = await state.get_data()
    await state.clear()

    # Janrni saqlash
    category = await create_category(data['name'], emoji)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yana qo'shish", callback_data="cat:add")],
        [InlineKeyboardButton(text="🎭 Janrlar", callback_data="admin:categories")],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
    ])

    await message.answer(
        f"✅ <b>Janr muvaffaqiyatli qo'shildi!</b>\n\n"
        f"🎭 {emoji} {data['name']}",
        reply_markup=kb
    )


@router.callback_query(AddCategoryState.emoji, F.data == "cat:skip_emoji")
async def add_category_skip_emoji(callback: CallbackQuery, state: FSMContext):
    """Emojini o'tkazib yuborish"""
    data = await state.get_data()
    await state.clear()

    # Janrni saqlash (emojisiz)
    category = await create_category(data['name'], "")

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yana qo'shish", callback_data="cat:add")],
        [InlineKeyboardButton(text="🎭 Janrlar", callback_data="admin:categories")],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
    ])

    await callback.message.edit_text(
        f"✅ <b>Janr muvaffaqiyatli qo'shildi!</b>\n\n"
        f"🎬 {data['name']}",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat:view:"), IsAdmin())
async def view_category(callback: CallbackQuery):
    """Janr ma'lumotlari"""
    cat_id = int(callback.data.split(":")[2])
    category = await get_category_by_id(cat_id)

    if not category:
        await callback.answer("❌ Janr topilmadi", show_alert=True)
        return

    movies_count = await get_category_movies_count(cat_id)
    status = "✅ Aktiv" if category.is_active else "❌ Noaktiv"
    emoji = category.emoji or "🎬"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"cat:edit:{cat_id}"),
            InlineKeyboardButton(
                text="❌ Noaktiv" if category.is_active else "✅ Aktiv",
                callback_data=f"cat:toggle:{cat_id}"
            )
        ],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"cat:delete:{cat_id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:categories")]
    ])

    await callback.message.edit_text(
        f"🎭 <b>Janr ma'lumotlari</b>\n\n"
        f"📝 Nomi: {emoji} {esc(category.name)}\n"
        f"📊 Holati: {status}\n"
        f"🎬 Kinolar: {movies_count} ta\n"
        f"🔢 Tartib: {category.order}",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat:toggle:"), IsAdmin())
async def toggle_category(callback: CallbackQuery):
    """Janr holatini o'zgartirish"""
    cat_id = int(callback.data.split(":")[2])
    result = await toggle_category_status(cat_id)

    if result:
        await callback.answer("✅ Holat o'zgartirildi!")
        # Qayta ko'rsatish
        await view_category(callback)
    else:
        await callback.answer("❌ Xatolik!", show_alert=True)


@router.callback_query(F.data.startswith("cat:edit:"), IsAdmin())
async def edit_category_start(callback: CallbackQuery, state: FSMContext):
    """Janrni tahrirlash"""
    cat_id = int(callback.data.split(":")[2])
    category = await get_category_by_id(cat_id)

    if not category:
        await callback.answer("❌ Janr topilmadi", show_alert=True)
        return

    await state.set_state(EditCategoryState.name)
    await state.update_data(category_id=cat_id, old_name=category.name)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ O'zgarishsiz", callback_data="cat:keep_name")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:categories")]
    ])

    await callback.message.edit_text(
        f"✏️ <b>Janrni tahrirlash</b>\n\n"
        f"Hozirgi nom: <b>{esc(category.name)}</b>\n\n"
        "Yangi nomni kiriting yoki o'zgarishsiz qoldiring:",
        reply_markup=kb
    )
    await callback.answer()


@router.message(EditCategoryState.name, F.text)
async def edit_category_name(message: Message, state: FSMContext):
    """Yangi nom"""
    new_name = message.text.strip()
    data = await state.get_data()

    if len(new_name) < 2:
        await message.answer(
            "❌ Janr nomi kamida 2 ta harfdan iborat bo'lishi kerak!",
            reply_markup=cancel_inline_kb()
        )
        return

    await state.update_data(new_name=new_name)
    await state.set_state(EditCategoryState.emoji)

    category = await get_category_by_id(data['category_id'])
    current_emoji = category.emoji if category else ""

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ O'zgarishsiz", callback_data="cat:keep_emoji")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:categories")]
    ])

    await message.answer(
        f"✅ Yangi nom: <b>{new_name}</b>\n\n"
        f"Hozirgi emoji: {current_emoji or 'Yo`q'}\n"
        "Yangi emoji kiriting yoki o'zgarishsiz qoldiring:",
        reply_markup=kb
    )


@router.callback_query(EditCategoryState.name, F.data == "cat:keep_name")
async def keep_category_name(callback: CallbackQuery, state: FSMContext):
    """Nomni o'zgarishsiz qoldirish"""
    data = await state.get_data()
    await state.update_data(new_name=data['old_name'])
    await state.set_state(EditCategoryState.emoji)

    category = await get_category_by_id(data['category_id'])
    current_emoji = category.emoji if category else ""

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ O'zgarishsiz", callback_data="cat:keep_emoji")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:categories")]
    ])

    await callback.message.edit_text(
        f"✅ Nom: <b>{data['old_name']}</b> (o'zgarishsiz)\n\n"
        f"Hozirgi emoji: {current_emoji or 'Yo`q'}\n"
        "Yangi emoji kiriting yoki o'zgarishsiz qoldiring:",
        reply_markup=kb
    )
    await callback.answer()


@router.message(EditCategoryState.emoji, F.text)
async def edit_category_emoji(message: Message, state: FSMContext):
    """Yangi emoji"""
    new_emoji = message.text.strip()
    data = await state.get_data()

    if len(new_emoji) > 5:
        await message.answer("❌ Emoji juda uzun!", reply_markup=cancel_inline_kb())
        return

    await state.clear()

    # Saqlash
    await update_category(data['category_id'], data['new_name'], new_emoji)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Janrlar", callback_data="admin:categories")],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
    ])

    await message.answer(
        f"✅ <b>Janr yangilandi!</b>\n\n"
        f"🎭 {new_emoji} {data['new_name']}",
        reply_markup=kb
    )


@router.callback_query(EditCategoryState.emoji, F.data == "cat:keep_emoji")
async def keep_category_emoji(callback: CallbackQuery, state: FSMContext):
    """Emojini o'zgarishsiz qoldirish"""
    data = await state.get_data()
    await state.clear()

    category = await get_category_by_id(data['category_id'])
    old_emoji = category.emoji if category else ""

    # Faqat nomni yangilash
    await update_category(data['category_id'], data['new_name'], old_emoji)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Janrlar", callback_data="admin:categories")],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
    ])

    await callback.message.edit_text(
        f"✅ <b>Janr yangilandi!</b>\n\n"
        f"🎭 {old_emoji} {data['new_name']}",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat:delete:"), IsAdmin())
async def delete_category_confirm(callback: CallbackQuery):
    """Janrni o'chirish - tasdiqlash"""
    cat_id = int(callback.data.split(":")[2])
    category = await get_category_by_id(cat_id)

    if not category:
        await callback.answer("❌ Janr topilmadi", show_alert=True)
        return

    movies_count = await get_category_movies_count(cat_id)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"cat:delete_confirm:{cat_id}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data=f"cat:view:{cat_id}")
        ]
    ])

    warning = ""
    if movies_count > 0:
        warning = f"\n\n⚠️ Bu janrda {movies_count} ta kino bor. O'chirilganda kinolarning janri yo'qoladi."

    await callback.message.edit_text(
        f"🗑 <b>Janrni o'chirish</b>\n\n"
        f"Rostdan ham <b>{esc(category.name)}</b> janrini o'chirmoqchimisiz?{warning}",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat:delete_confirm:"), IsAdmin())
async def delete_category_execute(callback: CallbackQuery):
    """Janrni o'chirish"""
    cat_id = int(callback.data.split(":")[2])
    result = await delete_category(cat_id)

    if result:
        await callback.answer("✅ Janr o'chirildi!")
        await categories_menu(callback)
    else:
        await callback.answer("❌ Xatolik!", show_alert=True)


# ==================== XABAR YUBORISH ====================

@router.callback_query(F.data == "admin:broadcast", CanBroadcast())
async def broadcast_start_callback(callback: CallbackQuery, state: FSMContext):
    """Broadcast boshlash inline"""
    await state.set_state(BroadcastState.target)
    await callback.message.edit_text(
        "📨 <b>Xabar yuborish</b>\n\n"
        "Kimga yubormoqchisiz?",
        reply_markup=broadcast_target_kb()
    )
    await callback.answer()


@router.callback_query(BroadcastState.target, F.data.startswith("broadcast_target:"))
async def broadcast_target(callback: CallbackQuery, state: FSMContext):
    """Target tanlash"""
    target = callback.data.split(":")[1]
    await state.update_data(target=target)
    await state.set_state(BroadcastState.is_ad)

    target_text = {"all": "Hammaga", "premium": "Premium", "regular": "Oddiy"}

    await callback.message.edit_text(
        f"✅ Tanlandi: {target_text[target]}\n\n"
        "Bu reklama xabarimi?\n"
        "(Reklama xabari premium foydalanuvchilarga yuborilmaydi)",
        reply_markup=broadcast_ad_kb()
    )


@router.callback_query(BroadcastState.is_ad, F.data.startswith("broadcast_ad:"))
async def broadcast_is_ad(callback: CallbackQuery, state: FSMContext):
    """Reklama tanash"""
    is_ad = callback.data.split(":")[1] == "yes"
    await state.update_data(is_ad=is_ad)
    await state.set_state(BroadcastState.content)

    await callback.message.edit_text(
        "✅ Tanlandi.\n\n"
        "📝 Endi xabarni yuboring (matn, rasm, video yoki fayl):\n\n"
        "<i>Bekor qilish uchun /cancel buyrug'ini yuboring</i>"
    )
    await callback.answer()


@router.message(Command("cancel"), IsAdmin())
async def cancel_broadcast_cmd(message: Message, state: FSMContext):
    """Broadcast bekor qilish"""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())
    else:
        await message.answer("Bekor qilinadigan amal yo'q.")


@router.message(BroadcastState.content)
async def broadcast_content(message: Message, state: FSMContext):
    """Xabar kontenti"""
    data = await state.get_data()

    # Kontent turini aniqlash
    content_type = "text"
    file_id = ""
    text = ""

    if message.text:
        content_type = "text"
        text = message.text
    elif message.photo:
        content_type = "photo"
        file_id = message.photo[-1].file_id
        text = message.caption or ""
    elif message.video:
        content_type = "video"
        file_id = message.video.file_id
        text = message.caption or ""
    elif message.document:
        content_type = "document"
        file_id = message.document.file_id
        text = message.caption or ""

    await state.update_data(
        content_type=content_type,
        file_id=file_id,
        text=text
    )
    await state.set_state(BroadcastState.confirm)

    # Preview ko'rsatish
    target_text = {"all": "Hammaga", "premium": "Premium", "regular": "Oddiy"}

    preview_text = (
        "📨 <b>Xabar preview:</b>\n\n"
        f"📍 Kimga: {target_text[data['target']]}\n"
        f"📢 Reklama: {'Ha' if data['is_ad'] else 'Yoq'}\n"
        f"📝 Tur: {content_type}\n\n"
        "Yuborishni tasdiqlaysizmi?"
    )

    await message.answer(preview_text, reply_markup=confirm_broadcast_kb())


@router.callback_query(BroadcastState.confirm, F.data == "confirm_broadcast")
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext, db_user: User = None, bot: Bot = None):
    """Broadcast tasdiqlash va yuborish"""
    data = await state.get_data()
    await state.clear()

    await callback.message.edit_text("📨 Xabar yuborilmoqda...")

    # Broadcast yaratish
    broadcast = await create_broadcast(
        target=data['target'],
        content_type=data['content_type'],
        text=data['text'],
        file_id=data['file_id'],
        is_ad=data['is_ad'],
        sent_by_id=db_user.user_id if db_user else None
    )

    # Foydalanuvchilarni olish
    users = await get_broadcast_users(data['target'], data['is_ad'])

    await update_broadcast_total(broadcast.id, len(users))

    # Yuborish
    sent = 0
    failed = 0

    async def _deliver(user_id, parse_mode="__default__"):
        # parse_mode="__default__" -> botning standart HTML rejimidan foydalanish.
        # parse_mode=None -> HTML tahlilini o'chirish (oddiy matn).
        kwargs = {} if parse_mode == "__default__" else {'parse_mode': parse_mode}
        if data['content_type'] == 'text':
            await bot.send_message(user_id, data['text'], **kwargs)
        elif data['content_type'] == 'photo':
            await bot.send_photo(user_id, data['file_id'], caption=data['text'], **kwargs)
        elif data['content_type'] == 'video':
            await bot.send_video(user_id, data['file_id'], caption=data['text'], **kwargs)
        elif data['content_type'] == 'document':
            await bot.send_document(user_id, data['file_id'], caption=data['text'], **kwargs)

    for user in users:
        try:
            try:
                await _deliver(user.user_id)
            except TelegramBadRequest:
                # HTML tahlili muvaffaqiyatsiz (masalan matnda '&' yoki yopilmagan teg) ->
                # oddiy matn sifatida qayta yuborish, shunda xabar baribir yetib boradi.
                await _deliver(user.user_id, parse_mode=None)
            sent += 1
        except Exception:
            failed += 1

        # Har 20 ta xabardan keyin progress
        if (sent + failed) % 20 == 0:
            await callback.message.edit_text(
                f"📨 Yuborilmoqda... {sent + failed}/{len(users)}"
            )

    # Yakunlash
    await complete_broadcast(broadcast.id, sent, failed)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
    ])

    await callback.message.edit_text(
        f"✅ <b>Xabar yuborish yakunlandi!</b>\n\n"
        f"📊 Jami: {len(users)}\n"
        f"✅ Yuborildi: {sent}\n"
        f"❌ Xato: {failed}",
        reply_markup=kb
    )


# ==================== TO'LOVLAR ====================

@router.callback_query(F.data == "admin:payments", CanManagePayments())
async def payments_menu(callback: CallbackQuery):
    """To'lovlar"""
    pending = await get_pending_payments()

    if not pending:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel")]
        ])
        await callback.message.edit_text("📭 Kutilayotgan to'lovlar yo'q.", reply_markup=kb)
        await callback.answer()
        return

    await callback.message.edit_text(f"💳 Kutilayotgan: {len(pending)}")
    await callback.answer()

    for payment in pending[:10]:
        text = (
            f"💳 <b>To'lov #{payment.id}</b>\n\n"
            f"👤 {payment.user.full_name}\n"
            f"🆔 <code>{payment.user.user_id}</code>\n"
            f"💰 {payment.amount:,} so'm\n"
            f"📅 {payment.created_at.strftime('%d.%m.%Y %H:%M')}"
        )

        from bot.keyboards import payment_confirm_kb
        await callback.message.answer_photo(
            photo=payment.screenshot_file_id,
            caption=text,
            reply_markup=payment_confirm_kb(payment.id)
        )


# ==================== KINO SO'ROVLARI ====================

@router.callback_query(F.data == "admin:requests", IsAdmin())
async def movie_requests_menu(callback: CallbackQuery):
    """Foydalanuvchi kino so'rovlari (kutilayotganlar)."""
    requests = await get_pending_requests()

    if not requests:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel")]
        ])
        try:
            await callback.message.edit_text("📭 Kutilayotgan kino so'rovlari yo'q.", reply_markup=kb)
        except TelegramBadRequest:
            pass
        await callback.answer()
        return

    text = f"🙋 <b>Kino so'rovlari</b> (kutilmoqda: {len(requests)})\n\n"
    rows = []
    for req in requests:
        text += (
            f"🎬 <b>{esc(req.title)}</b>\n"
            f"👤 <code>{req.user.user_id}</code> • 📅 {req.created_at.strftime('%d.%m %H:%M')}\n\n"
        )
        rows.append([InlineKeyboardButton(
            text=f"✅ Bajarildi: {req.title[:25]}",
            callback_data=f"admin:req_done:{req.id}"
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel")])

    try:
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except TelegramBadRequest:
        pass  # ikki marta bosish - "message is not modified"
    await callback.answer()


@router.callback_query(F.data.startswith("admin:req_done:"), IsAdmin())
async def movie_request_done(callback: CallbackQuery):
    """So'rovni 'bajarildi' deb belgilash."""
    req_id = int(callback.data.split(":")[2])
    await mark_request_done(req_id)
    await callback.answer("✅ Bajarildi deb belgilandi!", show_alert=True)
    # Ro'yxatni yangilash
    await movie_requests_menu(callback)


# ==================== KANALLAR ====================

@router.callback_query(F.data == "admin:channels", IsAdmin())
async def channels_menu(callback: CallbackQuery):
    """Kanallar"""
    channels = await get_channels()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()

    type_icons = {
        'telegram_channel': '📢',
        'telegram_group': '👥',
        'telegram_bot': '🤖',
        'instagram': '📸',
        'external': '🔗',
        'public': '📢',
        'private': '🔒',
        'group': '👥',
    }

    if channels:
        for channel in channels:
            status = "✅" if channel.is_active else "❌"
            icon = type_icons.get(channel.channel_type, '📢')
            builder.row(InlineKeyboardButton(
                text=f"{status} {icon} {channel.title}",
                callback_data=f"ch:view:{channel.id}"
            ))

    builder.row(InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="ch:add"))
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel"))

    text = "📢 <b>Majburiy obuna kanallari</b>\n\n"
    if channels:
        text += f"Jami: {len(channels)} ta\n"
        text += "Kanalni bosib tahrirlang."
    else:
        text += "📭 Hozircha kanallar yo'q.\n➕ Kanal qo'shish tugmasini bosing."

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "ch:add", IsAdmin())
async def add_channel_start(callback: CallbackQuery, state: FSMContext):
    """Kanal qo'shishni boshlash - tur tanlash"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Telegram kanal", callback_data="ch:type:telegram_channel")],
        [InlineKeyboardButton(text="👥 Telegram guruh", callback_data="ch:type:telegram_group")],
        [InlineKeyboardButton(text="🤖 Telegram bot", callback_data="ch:type:telegram_bot")],
        [InlineKeyboardButton(text="📸 Instagram", callback_data="ch:type:instagram")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:channels")]
    ])

    await callback.message.edit_text(
        "📢 <b>Kanal qo'shish</b>\n\n"
        "Kanal turini tanlang:",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ch:type:"), IsAdmin())
async def add_channel_type(callback: CallbackQuery, state: FSMContext):
    """Kanal turini tanlash"""
    channel_type = callback.data.split(":")[2]
    await state.update_data(channel_type=channel_type)
    await state.set_state(AddChannelState.channel_input)

    if channel_type == "instagram":
        await callback.message.edit_text(
            "📸 <b>Instagram qo'shish</b>\n\n"
            "Instagram profilingiz havolasini kiriting:\n\n"
            "Masalan:\n"
            "• <code>https://instagram.com/username</code>\n"
            "• <code>https://www.instagram.com/username</code>",
            reply_markup=cancel_inline_kb()
        )
    elif channel_type == "telegram_bot":
        await callback.message.edit_text(
            "🤖 <b>Bot qo'shish</b>\n\n"
            "Bot username yoki havolasini kiriting:\n\n"
            "Masalan:\n"
            "• <code>@bot_username</code>\n"
            "• <code>https://t.me/bot_username</code>",
            reply_markup=cancel_inline_kb()
        )
    else:
        await callback.message.edit_text(
            "📢 <b>Kanal/Guruh qo'shish</b>\n\n"
            "Kanalni forward qiling yoki kanal username/ID kiriting:\n\n"
            "Masalan:\n"
            "• <code>@channel_username</code>\n"
            "• <code>-1001234567890</code>\n"
            "• Yoki kanaldan xabar forward qiling",
            reply_markup=cancel_inline_kb()
        )
    await callback.answer()


@router.message(AddChannelState.channel_input, IsAdmin())
async def add_channel_input(message: Message, state: FSMContext, bot: Bot):
    """Kanal ma'lumotlarini olish"""
    data = await state.get_data()
    channel_type = data.get('channel_type', 'telegram_channel')

    channel_id = None
    username = ""
    title = ""
    invite_link = ""

    # Instagram uchun
    if channel_type == "instagram":
        text = message.text.strip() if message.text else ""
        if "instagram.com" in text:
            # Instagram username olish
            parts = text.rstrip("/").split("/")
            username = parts[-1] if parts else ""
            invite_link = text if text.startswith("http") else f"https://instagram.com/{username}"

            # Dublikat oldini olish (channel_id yo'q -> havola bo'yicha tekshiramiz)
            if await check_channel_link_exists(invite_link):
                await message.answer(
                    "❌ Bu havola allaqachon qo'shilgan!",
                    reply_markup=cancel_inline_kb()
                )
                await state.clear()
                return

            # Havolani saqlab, ko'rinadigan NOM so'raymiz. Foydalanuvchilar shu nomni
            # ko'radi - Instagram ekani va username bilinmasligi uchun oddiy nom.
            await state.update_data(channel_id=None, username=username, invite_link=invite_link)
            await state.set_state(AddChannelState.name)
            await message.answer(
                "✏️ <b>Sahifa nomini kiriting</b>\n\n"
                "Foydalanuvchilar majburiy obuna ro'yxatida <b>shu nomni</b> ko'radi.\n"
                "Instagram ekani bilinmasligi uchun oddiy nom yozing.\n\n"
                "Masalan: <code>Rasmiy sahifamiz</code>",
                reply_markup=cancel_inline_kb()
            )
            return
        else:
            await message.answer(
                "❌ Noto'g'ri format. Instagram havolasini kiriting:\n"
                "<code>https://instagram.com/username</code>",
                reply_markup=cancel_inline_kb()
            )
            return

    # Telegram bot uchun
    if channel_type == "telegram_bot":
        text = message.text.strip() if message.text else ""
        if text.startswith("@"):
            username = text[1:]
        elif "t.me/" in text:
            username = text.split("t.me/")[-1].rstrip("/")
        else:
            username = text

        title = f"Bot: @{username}"
        invite_link = f"https://t.me/{username}"

        await save_channel_with_type(None, username, title, invite_link, "telegram_bot")
        await state.clear()

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanallar", callback_data="admin:channels")],
            [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
        ])

        await message.answer(
            f"✅ <b>Bot qo'shildi!</b>\n\n"
            f"🤖 {title}\n"
            f"🔗 {invite_link}",
            reply_markup=kb
        )
        return

    # Telegram kanal/guruh uchun
    # Forward qilingan xabar
    if message.forward_from_chat:
        chat = message.forward_from_chat
        channel_id = chat.id
        username = chat.username or ""
        title = chat.title or ""
        if username:
            invite_link = f"https://t.me/{username}"
    # Username kiritilgan
    elif message.text:
        text = message.text.strip()
        if text.startswith("@"):
            username = text[1:]
            try:
                chat = await bot.get_chat(f"@{username}")
                channel_id = chat.id
                title = chat.title or username
                invite_link = f"https://t.me/{username}"
            except Exception:
                await message.answer(
                    "❌ Kanal topilmadi. Username to'g'ri ekanligini tekshiring.\n"
                    "Bot kanalda admin bo'lishi kerak!",
                    reply_markup=cancel_inline_kb()
                )
                return
        # ID kiritilgan
        elif text.lstrip("-").isdigit():
            try:
                chat = await bot.get_chat(int(text))
                channel_id = chat.id
                username = chat.username or ""
                title = chat.title or ""
                if username:
                    invite_link = f"https://t.me/{username}"
                else:
                    try:
                        invite_link = await bot.export_chat_invite_link(channel_id)
                    except Exception:
                        invite_link = ""
            except Exception:
                await message.answer(
                    "❌ Kanal topilmadi. ID to'g'ri ekanligini tekshiring.\n"
                    "Bot kanalda admin bo'lishi kerak!",
                    reply_markup=cancel_inline_kb()
                )
                return
        else:
            await message.answer(
                "❌ Noto'g'ri format. Qaytadan urinib ko'ring.",
                reply_markup=cancel_inline_kb()
            )
            return

    if not channel_id:
        await message.answer(
            "❌ Kanal ma'lumotlarini olib bo'lmadi.",
            reply_markup=cancel_inline_kb()
        )
        return

    # Mavjudligini tekshirish
    exists = await check_channel_exists(channel_id)
    if exists:
        await message.answer(
            "❌ Bu kanal allaqachon qo'shilgan!",
            reply_markup=cancel_inline_kb()
        )
        await state.clear()
        return

    await state.update_data(
        channel_id=channel_id,
        username=username,
        title=title,
        invite_link=invite_link
    )

    if not invite_link:
        await state.set_state(AddChannelState.title)
        await message.answer(
            f"✅ Kanal topildi: <b>{title}</b>\n\n"
            "Kanal uchun havola kiriting (https://t.me/...):",
            reply_markup=cancel_inline_kb()
        )
    else:
        # Saqlash
        await save_channel_with_type(channel_id, username, title, invite_link, channel_type)
        await state.clear()

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanallar", callback_data="admin:channels")],
            [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
        ])

        await message.answer(
            f"✅ <b>Kanal qo'shildi!</b>\n\n"
            f"📢 {title}\n"
            f"🆔 <code>{channel_id}</code>\n"
            f"🔗 {invite_link}",
            reply_markup=kb
        )


@router.message(AddChannelState.title, IsAdmin())
async def add_channel_link(message: Message, state: FSMContext):
    """Kanal havolasini olish"""
    invite_link = message.text.strip()

    if not invite_link.startswith("http"):
        await message.answer(
            "❌ Noto'g'ri havola. https://t.me/... formatida kiriting:",
            reply_markup=cancel_inline_kb()
        )
        return

    data = await state.get_data()
    channel_type = data.get('channel_type', 'telegram_channel')

    await save_channel_with_type(
        data['channel_id'],
        data['username'],
        data['title'],
        invite_link,
        channel_type
    )
    await state.clear()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanallar", callback_data="admin:channels")],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
    ])

    await message.answer(
        f"✅ <b>Kanal qo'shildi!</b>\n\n"
        f"📢 {data['title']}\n"
        f"🆔 <code>{data['channel_id']}</code>\n"
        f"🔗 {invite_link}",
        reply_markup=kb
    )


@router.message(AddChannelState.name, IsAdmin())
async def add_channel_name(message: Message, state: FSMContext):
    """Instagram/tashqi sahifa uchun foydalanuvchilarga ko'rinadigan nom."""
    title = message.text.strip() if message.text else ""
    if not title:
        await message.answer(
            "❌ Nom bo'sh bo'lmasligi kerak. Qayta kiriting:",
            reply_markup=cancel_inline_kb()
        )
        return

    # Channel.title max_length=255 - oshib ketsa DataError (FSM tiqilib qolardi)
    if len(title) > 255:
        await message.answer(
            "❌ Nom juda uzun (255 belgidan ko'p). Qisqaroq nom kiriting:",
            reply_markup=cancel_inline_kb()
        )
        return

    data = await state.get_data()
    channel_type = data.get('channel_type', 'instagram')

    await save_channel_with_type(
        data.get('channel_id'),
        data.get('username', ''),
        title,
        data.get('invite_link', ''),
        channel_type
    )
    await state.clear()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanallar", callback_data="admin:channels")],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
    ])

    await message.answer(
        f"✅ <b>Qo'shildi!</b>\n\n"
        f"📢 {esc(title)}\n"
        f"🔗 {esc(data.get('invite_link', ''))}\n\n"
        f"ℹ️ Foydalanuvchilar «{esc(title)}» nomini ko'radi.",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("ch:view:"), IsAdmin())
async def view_channel(callback: CallbackQuery):
    """Kanal ma'lumotlari"""
    channel_id = int(callback.data.split(":")[2])
    channel = await get_channel_by_id(channel_id)

    if not channel:
        await callback.answer("❌ Kanal topilmadi", show_alert=True)
        return

    # Kanal obunachilari sonini olish (yangi model)
    subscribers_count = await get_channel_subscribers_count(channel_id)
    # Eski usul - kanal orqali kelganlar
    joined_users_count = await get_channel_joined_users_count(channel_id)

    status = "✅ Aktiv" if channel.is_active else "❌ O'chirilgan"
    checkable = "✅ Ha" if channel.is_checkable else "❌ Yo'q"

    type_names = {
        'telegram_channel': '📢 Telegram kanal',
        'telegram_group': '👥 Telegram guruh',
        'telegram_bot': '🤖 Telegram bot',
        'instagram': '📸 Instagram',
        'external': '🔗 Tashqi',
        'public': '📢 Ochiq kanal',
        'private': '🔒 Yopiq kanal',
        'group': '👥 Guruh',
    }
    type_text = type_names.get(channel.channel_type, channel.channel_type)

    text = (
        f"📢 <b>{esc(channel.title)}</b>\n\n"
        f"📋 Turi: {type_text}\n"
        f"🆔 ID: <code>{channel.channel_id or 'yo`q'}</code>\n"
        f"👤 Username: @{esc(channel.username or 'yo`q')}\n"
        f"🔗 Havola: {channel.invite_link}\n"
        f"📊 Holat: {status}\n"
        f"✅ Tekshirish: {checkable}\n\n"
        f"📈 <b>Statistika:</b>\n"
        f"👥 Bot orqali obuna bo'lgan: <b>{subscribers_count}</b> ta\n"
        f"📥 Birinchi kanal sifatida: <b>{joined_users_count}</b> ta"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    toggle_text = "❌ O'chirish" if channel.is_active else "✅ Yoqish"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"ch:toggle:{channel.id}")],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"ch:delete:{channel.id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:channels")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("ch:toggle:"), IsAdmin())
async def toggle_channel(callback: CallbackQuery):
    """Kanal holatini o'zgartirish"""
    channel_id = int(callback.data.split(":")[2])
    result = await toggle_channel_status(channel_id)

    if result:
        await callback.answer("✅ Holat o'zgartirildi!")
        # Qayta ko'rsatish
        await view_channel(callback)
    else:
        await callback.answer("❌ Xatolik", show_alert=True)


@router.callback_query(F.data.startswith("ch:delete:"), IsAdmin())
async def delete_channel_confirm(callback: CallbackQuery):
    """Kanalni o'chirishni tasdiqlash"""
    channel_id = int(callback.data.split(":")[2])

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"ch:delete_yes:{channel_id}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data=f"ch:view:{channel_id}")
        ]
    ])

    await callback.message.edit_text(
        "⚠️ <b>Kanalni o'chirishni tasdiqlaysizmi?</b>\n\n"
        "Bu amalni qaytarib bo'lmaydi!",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ch:delete_yes:"), IsAdmin())
async def delete_channel_yes(callback: CallbackQuery):
    """Kanalni o'chirish"""
    channel_id = int(callback.data.split(":")[2])
    result = await delete_channel(channel_id)

    if result:
        await callback.answer("✅ Kanal o'chirildi!")
        # Kanallar ro'yxatiga qaytish
        await channels_menu(callback)
    else:
        await callback.answer("❌ Xatolik", show_alert=True)


# ==================== FOYDALANUVCHILAR ====================

@router.callback_query(F.data == "admin:users", CanManageUsers())
async def users_menu(callback: CallbackQuery):
    """Userlar"""
    stats = await get_user_stats()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Barcha userlar", callback_data="users:list:all:1")],
        [InlineKeyboardButton(text="💎 Premium", callback_data="users:list:premium:1"),
         InlineKeyboardButton(text="👤 Oddiy", callback_data="users:list:regular:1")],
        [InlineKeyboardButton(text="🆕 Yangi (bugun)", callback_data="users:list:today:1"),
         InlineKeyboardButton(text="⛔️ Banlangan", callback_data="users:list:banned:1")],
        [InlineKeyboardButton(text="🔍 Qidirish", callback_data="users:search")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel")]
    ])

    text = (
        "👥 <b>Userlar boshqaruvi</b>\n\n"
        f"📊 <b>Statistika:</b>\n"
        f"├ Jami: {format_number(stats['total'])}\n"
        f"├ Aktiv (24s): {format_number(stats['active_24h'])}\n"
        f"├ Premium: {format_number(stats['premium'])}\n"
        f"├ Trial: {format_number(stats['trial'])}\n"
        f"└ Banlangan: {format_number(stats['banned'])}\n\n"
        "📝 <b>Buyruqlar:</b>\n"
        "<code>/user 123456</code> - Ma'lumot\n"
        "<code>/ban 123456</code> - Bloklash\n"
        "<code>/unban 123456</code> - Ochish"
    )

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("users:list:"), CanManageUsers())
async def users_list(callback: CallbackQuery):
    """Userlar ro'yxati"""
    parts = callback.data.split(":")
    filter_type = parts[2]  # all, premium, regular, today, banned
    page = int(parts[3])

    users, total_pages, total_count = await get_users_list(filter_type, page)

    if not users:
        await callback.answer("📭 Userlar topilmadi", show_alert=True)
        return

    filter_names = {
        'all': '📋 Barcha userlar',
        'premium': '💎 Premium userlar',
        'regular': '👤 Oddiy userlar',
        'today': '🆕 Bugungi userlar',
        'banned': '⛔️ Banlangan userlar'
    }

    text = f"{filter_names.get(filter_type, 'Userlar')}\n"
    text += f"📊 Jami: {format_number(total_count)} ta | Sahifa: {page}/{total_pages}\n\n"

    for user in users:
        status = "💎" if user.is_premium_active else ("🎁" if user.is_trial_active else "👤")
        banned = " ⛔️" if user.is_banned else ""
        text += f"{status} <code>{user.user_id}</code> - {esc(user.full_name[:20])}{banned}\n"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    # User tugmalari
    for user in users[:5]:  # Faqat birinchi 5 ta uchun tugma
        builder.row(InlineKeyboardButton(
            text=f"👤 {user.full_name[:15]} ({user.user_id})",
            callback_data=f"user:view:{user.user_id}"
        ))

    # Pagination
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"users:list:{filter_type}:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"users:list:{filter_type}:{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:users"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("user:view:"), CanManageUsers())
async def user_view(callback: CallbackQuery):
    """User ma'lumotlari"""
    user_id = int(callback.data.split(":")[2])

    user_data = await get_user_full_info(user_id)
    if not user_data:
        await callback.answer("❌ User topilmadi", show_alert=True)
        return

    user = user_data['user']
    referrals_count = user_data['referrals_count']

    status = "💎 Premium" if user.is_premium_active else ("🎁 Trial" if user.is_trial_active else "👤 Oddiy")

    text = (
        f"👤 <b>Foydalanuvchi ma'lumotlari</b>\n\n"
        f"🆔 ID: <code>{user.user_id}</code>\n"
        f"👤 Ism: {esc(user.full_name)}\n"
        f"📛 Username: @{esc(user.username or 'yo`q')}\n"
        f"📊 Status: {status}\n"
    )

    if user.is_premium_active:
        text += f"⏰ Premium tugaydi: {user.premium_expires.strftime('%d.%m.%Y') if user.premium_expires else 'Muddatsiz'}\n"
        text += f"📅 Qolgan kun: {user.days_left}\n"

    text += (
        f"\n⛔️ Bloklangan: {'Ha' if user.is_banned else 'Yo`q'}\n"
    )

    if user.is_banned and user.ban_reason:
        text += f"📝 Sabab: {esc(user.ban_reason)}\n"

    text += (
        f"\n🎬 Ko'rilgan kinolar: {user.movies_watched}\n"
        f"👥 Referal kod: <code>{user.referral_code}</code>\n"
        f"👥 Taklif qilganlar: {referrals_count} ta\n"
        f"\n📅 Ro'yxatdan o'tgan: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"🕐 Oxirgi faollik: {user.last_active.strftime('%d.%m.%Y %H:%M')}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⛔️ Bloklash" if not user.is_banned else "✅ Blokdan chiqarish",
            callback_data=f"user:{'unban' if user.is_banned else 'ban'}:{user.user_id}"
        )],
        [InlineKeyboardButton(text="💎 Premium berish", callback_data=f"user:give_premium:{user.user_id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:users")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("user:ban:"), CanManageUsers())
async def user_ban_callback(callback: CallbackQuery):
    """Userni bloklash"""
    user_id = int(callback.data.split(":")[2])
    result = await ban_user(user_id, "Admin tomonidan bloklangan")

    if result:
        await callback.answer("✅ User bloklandi!", show_alert=True)
    else:
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)

    await user_view(callback)


@router.callback_query(F.data.startswith("user:unban:"), CanManageUsers())
async def user_unban_callback(callback: CallbackQuery):
    """Userni blokdan chiqarish"""
    user_id = int(callback.data.split(":")[2])
    result = await unban_user(user_id)

    if result:
        await callback.answer("✅ User blokdan chiqarildi!", show_alert=True)
    else:
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)

    await user_view(callback)


@router.callback_query(F.data.startswith("user:give_premium:"), CanManageUsers())
async def user_give_premium_menu(callback: CallbackQuery):
    """Premium berish menyusi"""
    user_id = int(callback.data.split(":")[2])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="7 kun", callback_data=f"user:add_premium:{user_id}:7"),
         InlineKeyboardButton(text="30 kun", callback_data=f"user:add_premium:{user_id}:30")],
        [InlineKeyboardButton(text="90 kun", callback_data=f"user:add_premium:{user_id}:90"),
         InlineKeyboardButton(text="365 kun", callback_data=f"user:add_premium:{user_id}:365")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"user:view:{user_id}")]
    ])

    await callback.message.edit_text(
        f"💎 <b>Premium berish</b>\n\nUser ID: <code>{user_id}</code>\n\nNecha kun premium berasiz?",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user:add_premium:"), CanManageUsers())
async def user_add_premium(callback: CallbackQuery):
    """Userga premium berish"""
    parts = callback.data.split(":")
    user_id = int(parts[2])
    days = int(parts[3])

    result = await give_user_premium(user_id, days)

    if result:
        await callback.answer(f"✅ {days} kun premium berildi!", show_alert=True)
    else:
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)

    # User view ga qaytish
    callback.data = f"user:view:{user_id}"
    await user_view(callback)


@router.callback_query(F.data == "users:search", CanManageUsers())
async def users_search_prompt(callback: CallbackQuery, state: FSMContext):
    """User qidirish"""
    from bot.states import UserSearchState

    await state.set_state(UserSearchState.query)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:users")]
    ])

    await callback.message.edit_text(
        "🔍 <b>User qidirish</b>\n\n"
        "User ID yoki username kiriting:\n"
        "<i>Masalan: 123456789 yoki @username</i>",
        reply_markup=kb
    )
    await callback.answer()


@router.message(UserSearchState.query, F.text, CanManageUsers())
async def users_search_handler(message: Message, state: FSMContext):
    """User qidirish natijasi"""

    await state.clear()

    query = message.text.strip()

    # ID bo'yicha qidirish
    if query.isdigit():
        user = await get_user_by_telegram_id(int(query))
    # Username bo'yicha qidirish
    elif query.startswith("@"):
        user = await search_user_by_username(query[1:])
    else:
        user = await search_user_by_username(query)

    if not user:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Qayta qidirish", callback_data="users:search")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:users")]
        ])
        await message.answer("❌ Foydalanuvchi topilmadi.", reply_markup=kb)
        return

    # User ma'lumotlarini ko'rsatish
    status = "💎 Premium" if user.is_premium_active else ("🎁 Trial" if user.is_trial_active else "👤 Oddiy")

    text = (
        f"👤 <b>Foydalanuvchi topildi!</b>\n\n"
        f"🆔 ID: <code>{user.user_id}</code>\n"
        f"👤 Ism: {esc(user.full_name)}\n"
        f"📛 Username: @{esc(user.username or 'yo`q')}\n"
        f"📊 Status: {status}\n"
        f"⛔️ Bloklangan: {'Ha' if user.is_banned else 'Yo`q'}\n"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁 Batafsil", callback_data=f"user:view:{user.user_id}")],
        [InlineKeyboardButton(text="🔍 Qayta qidirish", callback_data="users:search")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:users")]
    ])

    await message.answer(text, reply_markup=kb)


@router.message(Command("user"), CanManageUsers())
async def user_info_cmd(message: Message):
    """Foydalanuvchi ma'lumotlari"""
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Foydalanish: /user [user_id]")
        return

    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ Noto'g'ri user_id")
        return

    user = await get_user_by_telegram_id(user_id)
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi")
        return

    status = "⭐️ Premium" if user.is_premium_active else ("🎁 Trial" if user.is_trial_active else "👤 Oddiy")
    banned = "⛔️ Ha" if user.is_banned else "✅ Yo'q"

    text = (
        f"👤 <b>Foydalanuvchi ma'lumotlari</b>\n\n"
        f"🆔 ID: <code>{user.user_id}</code>\n"
        f"👤 Ism: {esc(user.full_name)}\n"
        f"📛 Username: @{esc(user.username or 'yo`q')}\n"
        f"📊 Status: {status}\n"
        f"⛔️ Bloklangan: {banned}\n"
        f"🎬 Ko'rilgan kinolar: {user.movies_watched}\n"
        f"📅 Ro'yxatdan o'tgan: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"🕐 Oxirgi faollik: {user.last_active.strftime('%d.%m.%Y %H:%M')}"
    )

    await message.answer(text)


@router.message(Command("ban"), CanManageUsers())
async def ban_user_cmd(message: Message):
    """Foydalanuvchini bloklash"""
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer("❌ Foydalanish: /ban [user_id] [sabab]")
        return

    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ Noto'g'ri user_id")
        return

    reason = args[2] if len(args) > 2 else None
    result = await ban_user(user_id, reason)

    if result:
        await message.answer(f"✅ Foydalanuvchi <code>{user_id}</code> bloklandi.")
    else:
        await message.answer("❌ Foydalanuvchi topilmadi.")


@router.message(Command("unban"), CanManageUsers())
async def unban_user_cmd(message: Message):
    """Foydalanuvchini blokdan chiqarish"""
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Foydalanish: /unban [user_id]")
        return

    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ Noto'g'ri user_id")
        return

    result = await unban_user(user_id)

    if result:
        await message.answer(f"✅ Foydalanuvchi <code>{user_id}</code> blokdan chiqarildi.")
    else:
        await message.answer("❌ Foydalanuvchi topilmadi.")


# ==================== SOZLAMALAR ====================

@router.callback_query(F.data == "admin:settings", IsSuperAdmin())
async def settings_menu_callback(callback: CallbackQuery):
    """Bot sozlamalari inline"""
    settings = await get_bot_settings()

    status = "✅ Aktiv" if settings.is_active else "❌ O'chirilgan"
    discount_status = "✅ Aktiv" if settings.discount_active else "❌ O'chirilgan"
    referral = f"✅ +{settings.referral_bonus} kun" if settings.referral_active else "❌ O'chirilgan"

    # Chegirma vaqtini formatlash
    _total = settings.discount_duration
    if _total < 60:
        discount_time = f"{_total} sekund"
    else:
        discount_mins = _total // 60
        discount_secs = _total % 60
        discount_time = f"{discount_mins} daqiqa" + (f" {discount_secs} sekund" if discount_secs else "")

    text = (
        "⚙️ <b>Bot sozlamalari</b>\n\n"
        f"🤖 Bot holati: {status}\n"
        f"🎁 Bepul muddat: {settings.free_trial_days} kun\n"
        f"🔗 Referal bonus: {referral}\n\n"
        f"💰 <b>Chegirma sozlamalari:</b>\n"
        f"├ Holati: {discount_status}\n"
        f"├ Foiz: {settings.discount_percent}%\n"
        f"└ Muddat: {discount_time}\n\n"
        f"💳 <b>To'lov ma'lumotlari:</b>\n"
        f"Karta: <code>{esc(settings.card_number)}</code>\n"
        f"Egasi: {esc(settings.card_holder)}"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Karta raqami", callback_data="settings:card_number"),
         InlineKeyboardButton(text="👤 Karta egasi", callback_data="settings:card_holder")],
        [InlineKeyboardButton(text="🎁 Trial kunlar", callback_data="settings:trial_days"),
         InlineKeyboardButton(text="🔗 Referal bonus", callback_data="settings:referral_bonus")],
        [InlineKeyboardButton(text="🤖 Bot on/off", callback_data="settings:toggle_bot"),
         InlineKeyboardButton(text="💰 Chegirma on/off", callback_data="settings:toggle_discount")],
        [InlineKeyboardButton(text="📊 Chegirma foizi", callback_data="settings:discount_percent"),
         InlineKeyboardButton(text="⏱ Chegirma muddati", callback_data="settings:discount_duration")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ==================== SOZLAMALARNI TAHRIRLASH ====================

@router.callback_query(F.data == "settings:card_number", IsSuperAdmin())
async def edit_card_number_start(callback: CallbackQuery, state: FSMContext):
    """Karta raqamini o'zgartirish"""
    await state.set_state(EditSettingsState.card_number)
    await callback.message.edit_text(
        "💳 <b>Karta raqamini kiriting:</b>\n\n"
        "Masalan: <code>8600 1234 5678 9012</code>",
        reply_markup=cancel_inline_kb()
    )
    await callback.answer()


@router.message(EditSettingsState.card_number, F.text, IsSuperAdmin())
async def edit_card_number_save(message: Message, state: FSMContext):
    """Karta raqamini saqlash"""
    card_number = message.text.strip()

    # Validatsiya - faqat raqam va bo'sh joy
    clean_number = card_number.replace(" ", "")
    if not clean_number.isdigit() or len(clean_number) < 14:
        await message.answer(
            "❌ Noto'g'ri format!\n\n"
            "Karta raqami faqat raqamlardan iborat bo'lishi kerak.\n"
            "Masalan: <code>8600 1234 5678 9012</code>",
            reply_markup=cancel_inline_kb()
        )
        return

    await update_bot_setting('card_number', card_number)
    await state.clear()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin:settings")]
    ])

    await message.answer(
        f"✅ <b>Karta raqami yangilandi!</b>\n\n"
        f"Yangi raqam: <code>{card_number}</code>",
        reply_markup=kb
    )


@router.callback_query(F.data == "settings:card_holder", IsSuperAdmin())
async def edit_card_holder_start(callback: CallbackQuery, state: FSMContext):
    """Karta egasini o'zgartirish"""
    await state.set_state(EditSettingsState.card_holder)
    await callback.message.edit_text(
        "👤 <b>Karta egasining ismini kiriting:</b>\n\n"
        "Masalan: <code>ABDULLAYEV ABDULLA</code>",
        reply_markup=cancel_inline_kb()
    )
    await callback.answer()


@router.message(EditSettingsState.card_holder, F.text, IsSuperAdmin())
async def edit_card_holder_save(message: Message, state: FSMContext):
    """Karta egasini saqlash"""
    card_holder = message.text.strip().upper()

    if len(card_holder) < 3:
        await message.answer(
            "❌ Ism juda qisqa!\n\n"
            "Masalan: <code>ABDULLAYEV ABDULLA</code>",
            reply_markup=cancel_inline_kb()
        )
        return

    await update_bot_setting('card_holder', card_holder)
    await state.clear()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin:settings")]
    ])

    await message.answer(
        f"✅ <b>Karta egasi yangilandi!</b>\n\n"
        f"Yangi egasi: <code>{card_holder}</code>",
        reply_markup=kb
    )


@router.callback_query(F.data == "settings:trial_days", IsSuperAdmin())
async def edit_trial_days_start(callback: CallbackQuery, state: FSMContext):
    """Trial kunlarni o'zgartirish"""
    await state.set_state(EditSettingsState.trial_days)
    await callback.message.edit_text(
        "🎁 <b>Bepul kunlar sonini kiriting:</b>\n\n"
        "Masalan: <code>7</code> (kunlar soni)",
        reply_markup=cancel_inline_kb()
    )
    await callback.answer()


@router.message(EditSettingsState.trial_days, F.text, IsSuperAdmin())
async def edit_trial_days_save(message: Message, state: FSMContext):
    """Trial kunlarni saqlash"""
    try:
        days = int(message.text.strip())
        if days < 0 or days > 365:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri son!\n\n"
            "0 dan 365 gacha raqam kiriting.",
            reply_markup=cancel_inline_kb()
        )
        return

    await update_bot_setting('free_trial_days', days)
    await state.clear()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin:settings")]
    ])

    await message.answer(
        f"✅ <b>Bepul muddat yangilandi!</b>\n\n"
        f"Yangi muddat: <code>{days}</code> kun",
        reply_markup=kb
    )


@router.callback_query(F.data == "settings:referral_bonus", IsSuperAdmin())
async def edit_referral_bonus_start(callback: CallbackQuery, state: FSMContext):
    """Referal bonusni o'zgartirish"""
    await state.set_state(EditSettingsState.referral_bonus)

    await callback.message.edit_text(
        "🔗 <b>Referal bonus kunlarini kiriting:</b>\n\n"
        "Har bir referal uchun beriladigan bonus kunlar.\n"
        "Masalan: <code>3</code> (kunlar soni)",
        reply_markup=cancel_inline_kb()
    )
    await callback.answer()


@router.message(EditSettingsState.referral_bonus, F.text, IsSuperAdmin())
async def edit_referral_bonus_save(message: Message, state: FSMContext):
    """Referal bonusni saqlash"""
    try:
        days = int(message.text.strip())
        if days < 0 or days > 30:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri son!\n\n"
            "0 dan 30 gacha raqam kiriting.",
            reply_markup=cancel_inline_kb()
        )
        return

    await update_bot_setting('referral_bonus', days)
    await state.clear()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin:settings")]
    ])

    await message.answer(
        f"✅ <b>Referal bonus yangilandi!</b>\n\n"
        f"Yangi bonus: <code>{days}</code> kun",
        reply_markup=kb
    )


@router.callback_query(F.data == "settings:toggle_bot", IsSuperAdmin())
async def toggle_bot_status(callback: CallbackQuery):
    """Bot holatini o'zgartirish"""
    settings = await get_bot_settings()
    new_status = not settings.is_active
    await update_bot_setting('is_active', new_status)

    status_text = "yoqildi ✅" if new_status else "o'chirildi ❌"
    await callback.answer(f"Bot {status_text}", show_alert=True)

    # Sozlamalarni qayta ko'rsatish
    await settings_menu_callback(callback)


@router.callback_query(F.data == "settings:toggle_discount", IsSuperAdmin())
async def toggle_discount_status(callback: CallbackQuery):
    """Chegirma holatini o'zgartirish"""
    settings = await get_bot_settings()
    new_status = not settings.discount_active
    await update_bot_setting('discount_active', new_status)

    status_text = "yoqildi ✅" if new_status else "o'chirildi ❌"
    await callback.answer(f"Chegirma {status_text}", show_alert=True)

    # Sozlamalarni qayta ko'rsatish
    await settings_menu_callback(callback)


@router.callback_query(F.data == "settings:discount_percent", IsSuperAdmin())
async def edit_discount_percent_start(callback: CallbackQuery, state: FSMContext):
    """Chegirma foizini o'zgartirish"""
    settings = await get_bot_settings()
    await state.set_state(EditSettingsState.discount_percent)
    await callback.message.edit_text(
        f"📊 <b>Chegirma foizini kiriting:</b>\n\n"
        f"Hozirgi: <code>{settings.discount_percent}%</code>\n\n"
        f"1 dan 99 gacha son kiriting:",
        reply_markup=cancel_inline_kb()
    )
    await callback.answer()


@router.message(EditSettingsState.discount_percent, F.text, IsSuperAdmin())
async def edit_discount_percent_save(message: Message, state: FSMContext):
    """Chegirma foizini saqlash"""
    try:
        percent = int(message.text.strip())
        if percent < 1 or percent > 99:
            raise ValueError()
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format!\n\n"
            "1 dan 99 gacha son kiriting.\n"
            "Masalan: <code>50</code>",
            reply_markup=cancel_inline_kb()
        )
        return

    await update_bot_setting('discount_percent', percent)
    await state.clear()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin:settings")]
    ])

    await message.answer(
        f"✅ <b>Chegirma foizi yangilandi!</b>\n\n"
        f"Yangi foiz: <code>{percent}%</code>",
        reply_markup=kb
    )


@router.callback_query(F.data == "settings:discount_duration", IsSuperAdmin())
async def edit_discount_duration_start(callback: CallbackQuery, state: FSMContext):
    """Chegirma muddatini o'zgartirish"""
    settings = await get_bot_settings()
    current = settings.discount_duration
    await state.set_state(EditSettingsState.discount_duration)
    await callback.message.edit_text(
        f"⏱ <b>Chegirma muddatini kiriting (soniyada):</b>\n\n"
        f"Hozirgi: <code>{current}</code> soniya\n\n"
        f"10 dan 3600 gacha son kiriting (masalan: <code>30</code>):",
        reply_markup=cancel_inline_kb()
    )
    await callback.answer()


@router.message(EditSettingsState.discount_duration, F.text, IsSuperAdmin())
async def edit_discount_duration_save(message: Message, state: FSMContext):
    """Chegirma muddatini saqlash (soniyada — web dashboard bilan bir xil birlik)"""
    try:
        duration_seconds = int(message.text.strip())
        if duration_seconds < 10 or duration_seconds > 3600:
            raise ValueError()
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format!\n\n"
            "10 dan 3600 gacha son kiriting.\n"
            "Masalan: <code>30</code> (30 soniya)",
            reply_markup=cancel_inline_kb()
        )
        return

    await update_bot_setting('discount_duration', duration_seconds)
    await state.clear()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin:settings")]
    ])

    await message.answer(
        f"✅ <b>Chegirma muddati yangilandi!</b>\n\n"
        f"Yangi muddat: <code>{duration_seconds}</code> soniya",
        reply_markup=kb
    )


# ==================== TARIFLAR ====================

@sync_to_async
def get_all_tariffs():
    """Barcha tariflarni olish"""
    return list(Tariff.objects.all().order_by('order', 'days'))


@sync_to_async
def get_tariff_by_id(tariff_id: int):
    """Tarifni ID bo'yicha olish"""
    try:
        return Tariff.objects.get(id=tariff_id)
    except Tariff.DoesNotExist:
        return None


@sync_to_async
def create_tariff(name: str, days: int, price: int):
    """Yangi tarif yaratish"""
    order = Tariff.objects.count()
    return Tariff.objects.create(name=name, days=days, price=price, order=order)


@sync_to_async
def update_tariff(tariff_id: int, **kwargs):
    """Tarifni yangilash"""
    Tariff.objects.filter(id=tariff_id).update(**kwargs)


@sync_to_async
def delete_tariff(tariff_id: int):
    """Tarifni o'chirish"""
    Tariff.objects.filter(id=tariff_id).delete()


@sync_to_async
def toggle_tariff_status(tariff_id: int):
    """Tarif holatini o'zgartirish"""
    tariff = Tariff.objects.get(id=tariff_id)
    tariff.is_active = not tariff.is_active
    tariff.save()
    return tariff.is_active


@router.callback_query(F.data == "admin:tariffs", IsSuperAdmin())
async def tariffs_menu_callback(callback: CallbackQuery, state: FSMContext = None):
    """Tariflar menyusi"""
    # state ichki chaqiruvlarda None bo'lishi mumkin (masalan tarif o'chirilgandan keyin)
    if state:
        await state.clear()
    tariffs = await get_all_tariffs()

    if not tariffs:
        text = (
            "💎 <b>Tariflar</b>\n\n"
            "📭 Hozircha tariflar mavjud emas.\n\n"
            "Yangi tarif qo'shish uchun tugmani bosing."
        )
    else:
        text = "💎 <b>Tariflar</b>\n\n"
        for i, tariff in enumerate(tariffs, 1):
            status = "✅" if tariff.is_active else "❌"
            text += f"{i}. {status} <b>{esc(tariff.name)}</b> - {tariff.days} kun - {tariff.price:,} so'm\n"
        text += "\nTarifni tanlang yoki yangi qo'shing:"

    kb = InlineKeyboardMarkup(inline_keyboard=[])

    # Mavjud tariflar
    for tariff in tariffs:
        status = "✅" if tariff.is_active else "❌"
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"{status} {tariff.name}", callback_data=f"tariff:view:{tariff.id}")
        ])

    # Tugmalar
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="➕ Yangi tarif", callback_data="tariff:add")
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel")
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("tariff:view:"), IsSuperAdmin())
async def tariff_view_callback(callback: CallbackQuery):
    """Tarifni ko'rish"""
    tariff_id = int(callback.data.split(":")[2])
    tariff = await get_tariff_by_id(tariff_id)

    if not tariff:
        await callback.answer("❌ Tarif topilmadi!", show_alert=True)
        return

    status = "✅ Aktiv" if tariff.is_active else "❌ Deaktiv"
    text = (
        f"💎 <b>{esc(tariff.name)}</b>\n\n"
        f"📅 Muddat: {tariff.days} kun\n"
        f"💰 Narx: {tariff.price:,} so'm\n"
        f"📊 Holat: {status}\n"
        f"📋 Tartib: {tariff.order}"
    )

    toggle_text = "❌ Deaktiv qilish" if tariff.is_active else "✅ Aktiv qilish"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"tariff:toggle:{tariff.id}")],
        [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"tariff:edit:{tariff.id}"),
         InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"tariff:delete:{tariff.id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:tariffs")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("tariff:toggle:"), IsSuperAdmin())
async def tariff_toggle_callback(callback: CallbackQuery):
    """Tarif holatini o'zgartirish"""
    tariff_id = int(callback.data.split(":")[2])
    new_status = await toggle_tariff_status(tariff_id)

    status_text = "aktivlashtirildi ✅" if new_status else "deaktiv qilindi ❌"
    await callback.answer(f"Tarif {status_text}", show_alert=True)

    # Qayta ko'rsatish
    await tariff_view_callback(callback)


@router.callback_query(F.data.startswith("tariff:delete:"), IsSuperAdmin())
async def tariff_delete_callback(callback: CallbackQuery):
    """Tarifni o'chirish"""
    tariff_id = int(callback.data.split(":")[2])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"tariff:confirm_delete:{tariff_id}"),
         InlineKeyboardButton(text="❌ Yo'q", callback_data=f"tariff:view:{tariff_id}")]
    ])

    await callback.message.edit_text(
        "⚠️ <b>Tarifni o'chirishni tasdiqlaysizmi?</b>\n\n"
        "Bu amalni qaytarib bo'lmaydi!",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tariff:confirm_delete:"), IsSuperAdmin())
async def tariff_confirm_delete_callback(callback: CallbackQuery):
    """Tarifni o'chirishni tasdiqlash"""
    tariff_id = int(callback.data.split(":")[2])
    await delete_tariff(tariff_id)
    await callback.answer("✅ Tarif o'chirildi!", show_alert=True)

    # Tariflar ro'yxatiga qaytish
    await tariffs_menu_callback(callback, None)


@router.callback_query(F.data == "tariff:add", IsSuperAdmin())
async def tariff_add_callback(callback: CallbackQuery, state: FSMContext):
    """Yangi tarif qo'shish"""
    await state.set_state(AddTariffState.name)
    await callback.message.edit_text(
        "💎 <b>Yangi tarif qo'shish</b>\n\n"
        "📝 Tarif nomini kiriting:\n"
        "Masalan: <code>7 kun</code> yoki <code>1 oy</code>",
        reply_markup=cancel_inline_kb()
    )
    await callback.answer()


@router.message(AddTariffState.name, F.text)
async def tariff_add_name(message: Message, state: FSMContext):
    """Tarif nomi"""
    name = message.text.strip()

    if len(name) < 2 or len(name) > 50:
        await message.answer(
            "❌ Nom 2-50 belgidan iborat bo'lishi kerak!",
            reply_markup=cancel_inline_kb()
        )
        return

    await state.update_data(name=name)
    await state.set_state(AddTariffState.days)

    await message.answer(
        f"✅ Nom: <b>{name}</b>\n\n"
        "📅 Kunlar sonini kiriting:\n"
        "Masalan: <code>7</code> yoki <code>30</code>",
        reply_markup=cancel_inline_kb()
    )


@router.message(AddTariffState.days, F.text)
async def tariff_add_days(message: Message, state: FSMContext):
    """Tarif kunlari"""
    try:
        days = int(message.text.strip())
        if days < 1 or days > 365:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ 1 dan 365 gacha son kiriting!",
            reply_markup=cancel_inline_kb()
        )
        return

    await state.update_data(days=days)
    await state.set_state(AddTariffState.price)

    data = await state.get_data()
    await message.answer(
        f"✅ Nom: <b>{data['name']}</b>\n"
        f"✅ Kunlar: <b>{days}</b>\n\n"
        "💰 Narxni kiriting (so'mda):\n"
        "Masalan: <code>25000</code>",
        reply_markup=cancel_inline_kb()
    )


@router.message(AddTariffState.price, F.text)
async def tariff_add_price(message: Message, state: FSMContext):
    """Tarif narxi"""
    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if price < 1000:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Kamida 1000 so'm kiriting!",
            reply_markup=cancel_inline_kb()
        )
        return

    data = await state.get_data()
    name = data['name']
    days = data['days']

    # Tarifni yaratish
    tariff = await create_tariff(name=name, days=days, price=price)

    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yana qo'shish", callback_data="tariff:add")],
        [InlineKeyboardButton(text="💎 Tariflar", callback_data="admin:tariffs")],
        [InlineKeyboardButton(text="⬅️ Admin panel", callback_data="admin:panel")]
    ])

    await message.answer(
        f"✅ <b>Tarif yaratildi!</b>\n\n"
        f"📝 Nom: {name}\n"
        f"📅 Muddat: {days} kun\n"
        f"💰 Narx: {price:,} so'm",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("tariff:edit:"), IsSuperAdmin())
async def tariff_edit_callback(callback: CallbackQuery, state: FSMContext):
    """Tarifni tahrirlash"""
    tariff_id = int(callback.data.split(":")[2])
    tariff = await get_tariff_by_id(tariff_id)

    if not tariff:
        await callback.answer("❌ Tarif topilmadi!", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Nomni o'zgartirish", callback_data=f"tariff:edit_name:{tariff.id}")],
        [InlineKeyboardButton(text="📅 Kunlarni o'zgartirish", callback_data=f"tariff:edit_days:{tariff.id}")],
        [InlineKeyboardButton(text="💰 Narxni o'zgartirish", callback_data=f"tariff:edit_price:{tariff.id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"tariff:view:{tariff.id}")]
    ])

    await callback.message.edit_text(
        f"✏️ <b>{esc(tariff.name)} tarifini tahrirlash</b>\n\n"
        f"📅 Muddat: {tariff.days} kun\n"
        f"💰 Narx: {tariff.price:,} so'm\n\n"
        "Nimani o'zgartirmoqchisiz?",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tariff:edit_name:"), IsSuperAdmin())
async def tariff_edit_name_start(callback: CallbackQuery, state: FSMContext):
    """Tarif nomini tahrirlash - boshlash"""
    tariff_id = int(callback.data.split(":")[2])
    await state.update_data(tariff_id=tariff_id)
    await state.set_state(EditTariffState.name)

    await callback.message.edit_text(
        "📝 <b>Yangi nomni kiriting:</b>",
        reply_markup=cancel_inline_kb()
    )
    await callback.answer()


@router.message(EditTariffState.name, F.text)
async def tariff_edit_name_save(message: Message, state: FSMContext):
    """Tarif nomini saqlash"""
    name = message.text.strip()

    if len(name) < 2 or len(name) > 50:
        await message.answer(
            "❌ Nom 2-50 belgidan iborat bo'lishi kerak!",
            reply_markup=cancel_inline_kb()
        )
        return

    data = await state.get_data()
    tariff_id = data['tariff_id']
    await update_tariff(tariff_id, name=name)
    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Tariflar", callback_data="admin:tariffs")]
    ])

    await message.answer(f"✅ Tarif nomi yangilandi: <b>{name}</b>", reply_markup=kb)


@router.callback_query(F.data.startswith("tariff:edit_days:"), IsSuperAdmin())
async def tariff_edit_days_start(callback: CallbackQuery, state: FSMContext):
    """Tarif kunlarini tahrirlash - boshlash"""
    tariff_id = int(callback.data.split(":")[2])
    await state.update_data(tariff_id=tariff_id)
    await state.set_state(EditTariffState.days)

    await callback.message.edit_text(
        "📅 <b>Yangi kunlar sonini kiriting:</b>",
        reply_markup=cancel_inline_kb()
    )
    await callback.answer()


@router.message(EditTariffState.days, F.text)
async def tariff_edit_days_save(message: Message, state: FSMContext):
    """Tarif kunlarini saqlash"""
    try:
        days = int(message.text.strip())
        if days < 1 or days > 365:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ 1 dan 365 gacha son kiriting!",
            reply_markup=cancel_inline_kb()
        )
        return

    data = await state.get_data()
    tariff_id = data['tariff_id']
    await update_tariff(tariff_id, days=days)
    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Tariflar", callback_data="admin:tariffs")]
    ])

    await message.answer(f"✅ Muddat yangilandi: <b>{days} kun</b>", reply_markup=kb)


@router.callback_query(F.data.startswith("tariff:edit_price:"), IsSuperAdmin())
async def tariff_edit_price_start(callback: CallbackQuery, state: FSMContext):
    """Tarif narxini tahrirlash - boshlash"""
    tariff_id = int(callback.data.split(":")[2])
    await state.update_data(tariff_id=tariff_id)
    await state.set_state(EditTariffState.price)

    await callback.message.edit_text(
        "💰 <b>Yangi narxni kiriting (so'mda):</b>",
        reply_markup=cancel_inline_kb()
    )
    await callback.answer()


@router.message(EditTariffState.price, F.text)
async def tariff_edit_price_save(message: Message, state: FSMContext):
    """Tarif narxini saqlash"""
    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if price < 1000:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Kamida 1000 so'm kiriting!",
            reply_markup=cancel_inline_kb()
        )
        return

    data = await state.get_data()
    tariff_id = data['tariff_id']
    await update_tariff(tariff_id, price=price)
    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Tariflar", callback_data="admin:tariffs")]
    ])

    await message.answer(f"✅ Narx yangilandi: <b>{price:,} so'm</b>", reply_markup=kb)


# ==================== CHIQISH ====================

@router.message(F.text.in_({"🔙 Chiqish", "🏠 Asosiy menyu"}), IsAdmin())
async def exit_admin(message: Message, state: FSMContext):
    """Admin paneldan chiqish"""
    await state.clear()
    await message.answer("🏠 Asosiy menyu:", reply_markup=main_menu_inline_kb(is_admin=True))


# ==================== HELPER FUNCTIONS ====================

@sync_to_async
def get_category_by_id(category_id: int):
    """Kategoriyani ID bo'yicha olish"""
    try:
        return Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        return None


@sync_to_async
def get_stats():
    from django.utils import timezone
    today = timezone.now().date()

    return {
        'total_users': User.objects.count(),
        'today_users': User.objects.filter(created_at__date=today).count(),
        'premium_users': User.objects.filter(is_premium=True, premium_expires__gt=timezone.now()).count(),
        'total_movies': Movie.objects.count(),
        'pending_payments': Payment.objects.filter(status='pending').count(),
    }


@sync_to_async
def get_detailed_stats():
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    return {
        'total_users': User.objects.count(),
        'today_users': User.objects.filter(created_at__date=today).count(),
        'week_users': User.objects.filter(created_at__gte=week_ago).count(),
        'month_users': User.objects.filter(created_at__gte=month_ago).count(),
        'premium_users': User.objects.filter(is_premium=True, premium_expires__gt=now).count(),
        'trial_users': User.objects.filter(free_trial_expires__gt=now, is_premium=False).count(),
        'total_movies': Movie.objects.count(),
        'premium_movies': Movie.objects.filter(is_premium=True).count(),
        'total_views': Movie.objects.aggregate(total=Sum('views'))['total'] or 0,
        'pending_payments': Payment.objects.filter(status='pending').count(),
        'approved_payments': Payment.objects.filter(status='approved').count(),
    }


@sync_to_async
def get_movie_stats():
    return {
        'total': Movie.objects.count(),
        'active': Movie.objects.filter(is_active=True).count(),
        'premium': Movie.objects.filter(is_premium=True).count(),
    }


@sync_to_async
def check_movie_exists(code: str):
    return Movie.objects.filter(code=code).exists()


@sync_to_async
def get_categories():
    return list(Category.objects.filter(is_active=True).order_by('order'))


@sync_to_async
def create_movie(code, title, file_id, category_id, year, country, quality, language, description, is_premium, added_by_id, thumbnail_file_id=''):
    added_by = None
    if added_by_id:
        try:
            added_by = User.objects.get(user_id=added_by_id)
        except User.DoesNotExist:
            pass

    return Movie.objects.create(
        code=code,
        title=title,
        file_id=file_id,
        thumbnail_file_id=thumbnail_file_id,
        category_id=category_id,
        year=year,
        country=country,
        quality=quality,
        language=language,
        description=description,
        is_premium=is_premium,
        added_by=added_by
    )


@sync_to_async
def create_broadcast(target, content_type, text, file_id, is_ad, sent_by_id):
    sent_by = None
    if sent_by_id:
        try:
            sent_by = User.objects.get(user_id=sent_by_id)
        except User.DoesNotExist:
            pass

    return Broadcast.objects.create(
        target=target,
        content_type=content_type,
        text=text,
        file_id=file_id,
        is_advertisement=is_ad,
        sent_by=sent_by
    )


@sync_to_async
def get_broadcast_users(target, is_ad):
    from django.utils import timezone

    qs = User.objects.filter(is_banned=False)

    if target == 'premium':
        qs = qs.filter(is_premium=True, premium_expires__gt=timezone.now())
    elif target == 'regular':
        qs = qs.exclude(is_premium=True, premium_expires__gt=timezone.now())

    if is_ad:
        # Reklama xabari premium ga bormaydi
        qs = qs.exclude(is_premium=True, premium_expires__gt=timezone.now())

    return list(qs)


@sync_to_async
def count_active_users():
    """Faol (bloklanmagan) foydalanuvchilar soni."""
    return User.objects.filter(is_banned=False).count()


@sync_to_async
def get_active_user_ids():
    """Bildirishnoma uchun barcha faol foydalanuvchilarning Telegram ID lari."""
    return list(User.objects.filter(is_banned=False).values_list('user_id', flat=True))


@sync_to_async
def update_broadcast_total(broadcast_id, total):
    Broadcast.objects.filter(id=broadcast_id).update(total_users=total)


@sync_to_async
def complete_broadcast(broadcast_id, sent, failed):
    Broadcast.objects.filter(id=broadcast_id).update(
        sent_count=sent,
        failed_count=failed,
        is_completed=True,
        completed_at=timezone.now()
    )


@sync_to_async
def get_pending_payments():
    return list(Payment.objects.filter(status='pending').select_related('user', 'tariff').order_by('-created_at')[:10])


@sync_to_async
def get_pending_requests():
    from apps.movies.models import MovieRequest
    return list(
        MovieRequest.objects.filter(status='pending')
        .select_related('user')
        .order_by('-created_at')[:15]
    )


@sync_to_async
def mark_request_done(request_id: int):
    from apps.movies.models import MovieRequest
    MovieRequest.objects.filter(id=request_id).update(status='done')


@sync_to_async
def get_channels():
    from apps.channels.models import Channel
    return list(Channel.objects.all().order_by('order'))


@sync_to_async
def get_user_stats():
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    day_ago = now - timedelta(hours=24)

    return {
        'total': User.objects.count(),
        'active_24h': User.objects.filter(last_active__gte=day_ago).count(),
        'premium': User.objects.filter(is_premium=True, premium_expires__gt=now).count(),
        'trial': User.objects.filter(free_trial_expires__gt=now, is_premium=False).count(),
        'banned': User.objects.filter(is_banned=True).count(),
    }


@sync_to_async
def get_user_by_telegram_id(user_id: int):
    try:
        return User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return None


@sync_to_async
def search_user_by_username(username: str):
    """Username bo'yicha user qidirish"""
    try:
        return User.objects.filter(username__iexact=username).first()
    except Exception:
        return None


@sync_to_async
def ban_user(user_id: int, reason: str = None) -> bool:
    try:
        user = User.objects.get(user_id=user_id)
        user.is_banned = True
        user.ban_reason = reason
        user.save(update_fields=['is_banned', 'ban_reason'])
        # Cache'ni tozalaymiz, aks holda ban 60s davomida kuchga kirmaydi.
        clear_user_cache(user_id)
        return True
    except User.DoesNotExist:
        return False


@sync_to_async
def get_bot_settings():
    from apps.core.models import BotSettings
    return BotSettings.get_settings()


@sync_to_async
def update_bot_setting(field: str, value):
    """Bot sozlamasini yangilash"""
    from apps.core.models import BotSettings
    from django.core.cache import cache
    from bot.middlewares.database import clear_settings_cache

    settings = BotSettings.get_settings()
    setattr(settings, field, value)
    settings.save(update_fields=[field])

    # Cache tozalash
    cache.delete('bot_settings')
    clear_settings_cache()

    return settings


@sync_to_async
def check_channel_exists(channel_id: int) -> bool:
    """Kanal mavjudligini tekshirish"""
    from apps.channels.models import Channel
    return Channel.objects.filter(channel_id=channel_id).exists()


@sync_to_async
def check_channel_link_exists(invite_link: str) -> bool:
    """Havola bo'yicha kanal mavjudligini tekshirish (Instagram/tashqi - channel_id yo'q)."""
    from apps.channels.models import Channel
    return Channel.objects.filter(invite_link=invite_link).exists()


@sync_to_async
def save_channel(channel_id: int, username: str, title: str, invite_link: str):
    """Yangi kanal saqlash"""
    from apps.channels.models import Channel
    return Channel.objects.create(
        channel_id=channel_id,
        username=username,
        title=title,
        invite_link=invite_link,
        channel_type='telegram_channel' if username else 'telegram_channel'
    )


@sync_to_async
def save_channel_with_type(channel_id: int, username: str, title: str, invite_link: str, channel_type: str):
    """Yangi kanal saqlash (tur bilan)"""
    from apps.channels.models import Channel
    return Channel.objects.create(
        channel_id=channel_id,
        username=username,
        title=title,
        invite_link=invite_link,
        channel_type=channel_type
    )


@sync_to_async
def get_channel_by_id(pk: int):
    """Kanal olish (Django PK bo'yicha)"""
    from apps.channels.models import Channel
    try:
        return Channel.objects.get(id=pk)
    except Channel.DoesNotExist:
        return None


@sync_to_async
def get_channel_joined_users_count(channel_pk: int) -> int:
    """Kanal orqali kelgan userlar sonini olish"""
    return User.objects.filter(joined_from_channel_id=channel_pk).count()


@sync_to_async
def get_channel_subscribers_count(channel_pk: int) -> int:
    """Kanal obunachilari soni (ChannelSubscription modelidan)"""
    from apps.channels.models import ChannelSubscription
    return ChannelSubscription.objects.filter(channel_id=channel_pk).count()


@sync_to_async
def get_admin_movies(page: int = 1, per_page: int = 8, premium_only: bool = False):
    """Admin uchun kinolar ro'yxati"""
    movies = Movie.objects.all().order_by('-created_at')
    if premium_only:
        movies = movies.filter(is_premium=True)

    total = movies.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page

    return list(movies[start:start + per_page]), total_pages


@sync_to_async
def get_movie_by_code(code: str):
    """Kodni bo'yicha kino olish"""
    try:
        return Movie.objects.select_related('category').get(code=code)
    except Movie.DoesNotExist:
        return None


@sync_to_async
def toggle_movie_status(code: str) -> bool:
    """Kino aktiv/deaktiv"""
    try:
        movie = Movie.objects.get(code=code)
        movie.is_active = not movie.is_active
        movie.save(update_fields=['is_active'])
        return movie.is_active
    except Movie.DoesNotExist:
        return False


@sync_to_async
def toggle_movie_premium(code: str) -> bool:
    """Kino premium/oddiy"""
    try:
        movie = Movie.objects.get(code=code)
        movie.is_premium = not movie.is_premium
        movie.save(update_fields=['is_premium'])
        return movie.is_premium
    except Movie.DoesNotExist:
        return False


@sync_to_async
def delete_movie(code: str) -> bool:
    """Kinoni o'chirish"""
    try:
        movie = Movie.objects.get(code=code)
        movie.delete()
        return True
    except Movie.DoesNotExist:
        return False


@sync_to_async
def edit_movie_field(code: str, field: str, value):
    """Kino bitta maydonini yangilash. field: title/description/year/file_id/code/category_id.
    Qaytaradi: (movie yoki None, error yoki None). error: 'not_found' | 'duplicate'."""
    ALLOWED = {'title', 'description', 'year', 'file_id', 'code', 'category_id', 'thumbnail_file_id'}
    if field not in ALLOWED:
        return None, "not_found"
    try:
        movie = Movie.objects.select_related('category').get(code=code)
    except Movie.DoesNotExist:
        return None, "not_found"

    if field == 'code' and Movie.objects.filter(code=value).exclude(pk=movie.pk).exists():
        return None, "duplicate"

    setattr(movie, field, value)
    # FK uchun update_fields'da model maydon nomi ('category') beriladi, ustun emas.
    save_field = 'category' if field == 'category_id' else field
    movie.save(update_fields=[save_field])
    # category tafsilotini yangilab olamiz (natija xabarida ko'rsatish uchun)
    movie = Movie.objects.select_related('category').get(pk=movie.pk)
    return movie, None


@sync_to_async
def get_detailed_movie_stats():
    """Batafsil kino statistikasi"""
    from django.db.models import Sum, Avg

    total = Movie.objects.count()
    active = Movie.objects.filter(is_active=True).count()
    inactive = total - active
    premium = Movie.objects.filter(is_premium=True).count()
    regular = total - premium

    agg = Movie.objects.aggregate(
        total_views=Sum('views'),
        avg_views=Avg('views')
    )

    top_movies = list(Movie.objects.filter(is_active=True).order_by('-views')[:5].values('title', 'views'))

    return {
        'total': total,
        'active': active,
        'inactive': inactive,
        'premium': premium,
        'regular': regular,
        'total_views': agg['total_views'] or 0,
        'avg_views': int(agg['avg_views'] or 0),
        'top_movies': top_movies
    }


@sync_to_async
def toggle_channel_status(pk: int) -> bool:
    """Kanal holatini o'zgartirish"""
    from apps.channels.models import Channel
    try:
        channel = Channel.objects.get(id=pk)
        channel.is_active = not channel.is_active
        channel.save(update_fields=['is_active'])
        return True
    except Channel.DoesNotExist:
        return False


@sync_to_async
def delete_channel(pk: int) -> bool:
    """Kanalni o'chirish"""
    from apps.channels.models import Channel
    try:
        channel = Channel.objects.get(id=pk)
        channel.delete()
        return True
    except Channel.DoesNotExist:
        return False


# ==================== XABAR SHABLONLARI ====================

@router.callback_query(F.data == "admin:messages", IsAdmin())
async def messages_menu(callback: CallbackQuery):
    """Xabar shablonlari menyusi"""
    from apps.core.models import MessageTemplate

    messages = await sync_to_async(list)(MessageTemplate.objects.all())

    # Agar xabarlar yo'q bo'lsa, default xabarlarni yaratamiz
    if not messages:
        await sync_to_async(MessageTemplate.init_defaults)()
        messages = await sync_to_async(list)(MessageTemplate.objects.all())

    text = (
        "✏️ <b>Xabar shablonlari</b>\n\n"
        "Bu yerda botdagi barcha xabarlarni o'zgartirishingiz mumkin.\n"
        "Har bir xabarni bosing va yangi matn kiriting."
    )

    await callback.message.edit_text(text, reply_markup=admin_messages_kb(messages))
    await callback.answer()


@router.callback_query(F.data.startswith("edit_msg:"), IsAdmin())
async def edit_message_start(callback: CallbackQuery, state: FSMContext):
    """Xabarni tahrirlash"""
    from apps.core.models import MessageTemplate

    msg_type = callback.data.split(":")[1]

    try:
        template = await sync_to_async(MessageTemplate.objects.get)(message_type=msg_type)
    except MessageTemplate.DoesNotExist:
        await callback.answer("Xabar topilmadi", show_alert=True)
        return

    await state.set_state(EditMessageState.content)
    await state.update_data(message_type=msg_type)

    text = (
        f"✏️ <b>{esc(template.title)}</b>\n\n"
        f"📝 <b>Hozirgi xabar:</b>\n"
        f"<code>{template.content}</code>\n\n"
    )

    if template.placeholders_help:
        text += f"💡 <b>Placeholders:</b>\n{template.placeholders_help}\n\n"

    text += "📨 Yangi xabarni yuboring:"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:messages")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.message(EditMessageState.content, IsAdmin())
async def edit_message_content(message: Message, state: FSMContext):
    """Yangi xabar matnini saqlash"""
    from apps.core.models import MessageTemplate

    data = await state.get_data()
    msg_type = data.get('message_type')

    if not msg_type:
        await state.clear()
        return

    new_content = message.text
    if not new_content:
        # Rasm/stiker/ovoz kabi matnsiz xabar -> template.content=None IntegrityError
        # berardi yoki shablonni "None" ga aylantirardi. State'ni saqlab, qayta so'raymiz.
        await message.answer("❌ Iltimos, xabar matnini (oddiy matn) yuboring.")
        return

    @sync_to_async
    def update_message():
        template = MessageTemplate.objects.get(message_type=msg_type)
        template.content = new_content
        template.save()
        return template.title

    title = await update_message()
    await state.clear()

    text = f"✅ <b>{title}</b> xabari yangilandi!"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Xabarlarga qaytish", callback_data="admin:messages")],
        [InlineKeyboardButton(text="🏠 Admin panel", callback_data="admin:panel")]
    ])

    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "reset_messages", IsAdmin())
async def reset_messages(callback: CallbackQuery):
    """Barcha xabarlarni default holatga qaytarish"""
    from apps.core.models import MessageTemplate

    @sync_to_async
    def reset_all():
        MessageTemplate.objects.all().delete()
        MessageTemplate.init_defaults()

    await reset_all()

    await callback.answer("✅ Barcha xabarlar tiklandi!", show_alert=True)
    await messages_menu(callback)


# ==================== BATAFSIL STATISTIKA ====================

@router.callback_query(F.data == "stats:today", IsAdmin())
async def stats_today(callback: CallbackQuery):
    """Bugungi statistika"""
    stats = await get_today_stats()

    text = (
        "📈 <b>Bugungi statistika</b>\n\n"
        f"👥 <b>Yangi obunchilar:</b> +{format_number(stats['new_users'])}\n"
        f"💎 <b>Yangi premium:</b> +{format_number(stats['new_premium'])}\n"
        f"💰 <b>Tushumlar:</b> {format_number(stats['total_income'])} so'm\n"
        f"🎬 <b>Ko'rishlar:</b> {format_number(stats['total_views'])}\n\n"
        f"⏰ <b>Eng faol soat:</b> {stats['peak_hour']}:00\n"
        f"📊 <b>O'rtacha aktivlik:</b> {format_number(stats['avg_activity'])}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:stats")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "stats:week", IsAdmin())
async def stats_week(callback: CallbackQuery):
    """Haftalik statistika"""
    stats = await get_period_stats(days=7)

    text = (
        f"📊 <b>Haftalik statistika</b>\n"
        f"📅 {stats['start_date']} - {stats['end_date']}\n\n"
        f"👥 <b>Yangi obunchilar:</b> +{format_number(stats['new_users'])}\n"
        f"💎 <b>Yangi premium:</b> +{format_number(stats['new_premium'])}\n"
        f"💰 <b>Tushumlar:</b> {format_number(stats['total_income'])} so'm\n\n"
        f"📈 <b>Kunlik o'rtacha:</b>\n"
        f"├ Obunchilar: +{format_number(stats['avg_users_per_day'])}\n"
        f"└ Premium: +{format_number(stats['avg_premium_per_day'])}\n\n"
        f"📅 <b>Kunlik statistika:</b>\n"
    )

    for day in stats['daily_stats']:
        text += f"├ {day['date']} ({day['weekday']}): +{format_number(day['users'])} user, +{format_number(day['premium'])} premium\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:stats")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "stats:month", IsAdmin())
async def stats_month(callback: CallbackQuery):
    """Oylik statistika"""
    stats = await get_period_stats(days=30)

    text = (
        f"📉 <b>Oylik statistika</b>\n"
        f"📅 {stats['start_date']} - {stats['end_date']}\n\n"
        f"👥 <b>Yangi obunchilar:</b> +{format_number(stats['new_users'])}\n"
        f"💎 <b>Yangi premium:</b> +{format_number(stats['new_premium'])}\n"
        f"💰 <b>Tushumlar:</b> {format_number(stats['total_income'])} so'm\n\n"
        f"📈 <b>Kunlik o'rtacha:</b>\n"
        f"├ Obunchilar: +{format_number(stats['avg_users_per_day'])}\n"
        f"└ Premium: +{format_number(stats['avg_premium_per_day'])}\n\n"
        f"📊 <b>Haftalik ko'rsatkichlar:</b>\n"
    )

    for week in stats['weekly_stats']:
        text += f"├ {week['week']}-hafta ({week['start']} - {week['end']}): +{format_number(week['users'])} user, +{format_number(week['premium'])} premium\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:stats")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "stats:premium", IsAdmin())
async def stats_premium(callback: CallbackQuery):
    """Premium statistika"""
    stats = await get_premium_stats()

    text = (
        "💎 <b>Premium statistika</b>\n\n"
        f"👥 <b>Jami premium:</b> {format_number(stats['total_premium'])}\n"
        f"✅ <b>Aktiv:</b> {format_number(stats['active_premium'])}\n"
        f"⏰ <b>Tugagan:</b> {format_number(stats['expired_premium'])}\n\n"
        f"📈 <b>So'nggi 30 kun:</b>\n"
        f"├ Yangi premium: +{format_number(stats['new_premium_30d'])}\n"
        f"├ Tushumlar: {format_number(stats['income_30d'])} so'm\n"
        f"└ O'rtacha kun: {format_number(stats['avg_premium_days'])}\n\n"
        f"🏆 <b>Top tariflar:</b>\n"
    )

    for i, tariff in enumerate(stats['top_tariffs'], 1):
        text += f"{i}. {tariff['name']}: {format_number(tariff['count'])} ta\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:stats")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "stats:year", IsAdmin())
async def stats_year(callback: CallbackQuery):
    """Yillik statistika - oyma-oy"""
    stats = await get_yearly_stats()

    text = (
        f"📅 <b>Yillik statistika - {stats['year']}</b>\n\n"
        f"👥 <b>Jami yangi obunchilar:</b> +{format_number(stats['total_users'])}\n"
        f"💎 <b>Jami yangi premium:</b> +{format_number(stats['total_premium'])}\n"
        f"💰 <b>Jami tushumlar:</b> {format_number(stats['total_income'])} so'm\n\n"
        f"📊 <b>Oylik o'rtacha:</b>\n"
        f"├ Obunchilar: +{format_number(stats['avg_users_per_month'])}\n"
        f"└ Premium: +{format_number(stats['avg_premium_per_month'])}\n\n"
        f"📈 <b>Oyma-oy statistika:</b>\n"
    )

    for month in stats['monthly_stats']:
        if month['users'] > 0 or month['premium'] > 0:
            text += f"├ {month['month_name']}: +{format_number(month['users'])} user, +{format_number(month['premium'])} premium, {format_number(month['income'])} so'm\n"

    if not any(m['users'] > 0 or m['premium'] > 0 for m in stats['monthly_stats']):
        text += "├ Ma'lumot yo'q\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:stats")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ==================== STATISTIKA HELPER FUNCTIONS ====================

@sync_to_async
def get_today_stats():
    """Bugungi statistika"""
    from django.db.models import Count, Sum
    from django.db.models.functions import ExtractHour
    from datetime import datetime, timedelta

    today = timezone.now().date()
    today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))

    new_users = User.objects.filter(created_at__gte=today_start).count()
    new_premium = Payment.objects.filter(
        status='approved',
        created_at__gte=today_start
    ).count()

    total_income = Payment.objects.filter(
        status='approved',
        created_at__gte=today_start
    ).aggregate(total=Sum('tariff__price'))['total'] or 0

    # Jami ko'rishlar (bugungi ko'rishlarni alohida track qilish imkoni yo'q)
    total_views = Movie.objects.aggregate(total=Sum('views'))['total'] or 0

    # Eng faol soat
    hourly = User.objects.filter(
        created_at__gte=today_start
    ).annotate(
        hour=ExtractHour('created_at')
    ).values('hour').annotate(count=Count('id')).order_by('-count')

    peak_hour = hourly[0]['hour'] if hourly else 12
    avg_activity = new_users // max(1, (timezone.now().hour or 1))

    return {
        'new_users': new_users,
        'new_premium': new_premium,
        'total_income': total_income,
        'total_views': total_views,
        'peak_hour': peak_hour,
        'avg_activity': avg_activity
    }


@sync_to_async
def get_period_stats(days: int):
    """Davr statistikasi"""
    from django.db.models import Count, Sum
    from datetime import datetime, timedelta

    # Hafta kunlari nomlari
    weekdays = ['Du', 'Se', 'Chor', 'Pay', 'Ju', 'Sha', 'Yak']

    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)

    new_users = User.objects.filter(created_at__gte=start_date).count()
    new_premium = Payment.objects.filter(
        status='approved',
        created_at__gte=start_date
    ).count()

    total_income = Payment.objects.filter(
        status='approved',
        created_at__gte=start_date
    ).aggregate(total=Sum('tariff__price'))['total'] or 0

    avg_users_per_day = new_users // max(1, days)
    avg_premium_per_day = new_premium // max(1, days)

    # Kunlik statistika
    daily_stats = []
    for i in range(min(7, days)):
        day_start = (end_date - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        day_users = User.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count()
        day_premium = Payment.objects.filter(
            status='approved',
            created_at__gte=day_start,
            created_at__lt=day_end
        ).count()

        daily_stats.append({
            'date': day_start.strftime('%d.%m'),
            'weekday': weekdays[day_start.weekday()],
            'users': day_users,
            'premium': day_premium
        })

    # Haftalik statistika (faqat 30 kun uchun)
    weekly_stats = []
    if days >= 7:
        for week in range(min(4, days // 7)):
            week_end = end_date - timedelta(days=week * 7)
            week_start = end_date - timedelta(days=(week + 1) * 7)

            week_users = User.objects.filter(created_at__gte=week_start, created_at__lt=week_end).count()
            week_premium = Payment.objects.filter(
                status='approved',
                created_at__gte=week_start,
                created_at__lt=week_end
            ).count()

            weekly_stats.append({
                'week': week + 1,
                'start': week_start.strftime('%d.%m'),
                'end': week_end.strftime('%d.%m'),
                'users': week_users,
                'premium': week_premium
            })

    return {
        'new_users': new_users,
        'new_premium': new_premium,
        'total_income': total_income,
        'avg_users_per_day': avg_users_per_day,
        'avg_premium_per_day': avg_premium_per_day,
        'daily_stats': daily_stats,
        'weekly_stats': weekly_stats,
        'start_date': start_date.strftime('%d.%m.%Y'),
        'end_date': end_date.strftime('%d.%m.%Y')
    }


@sync_to_async
def get_premium_stats():
    """Premium statistikasi"""
    from django.db.models import Count, Sum, Avg
    from datetime import timedelta
    from apps.payments.models import Tariff

    now = timezone.now()
    month_ago = now - timedelta(days=30)

    total_premium = User.objects.filter(is_premium=True).count()
    active_premium = User.objects.filter(is_premium=True, premium_expires__gt=now).count()
    expired_premium = total_premium - active_premium

    new_premium_30d = Payment.objects.filter(
        status='approved',
        created_at__gte=month_ago
    ).count()

    income_30d = Payment.objects.filter(
        status='approved',
        created_at__gte=month_ago
    ).aggregate(total=Sum('tariff__price'))['total'] or 0

    # O'rtacha premium kunlari
    avg_days = Payment.objects.filter(
        status='approved'
    ).aggregate(avg=Avg('tariff__days'))['avg'] or 0

    # Top tariflar
    top_tariffs = list(
        Payment.objects.filter(status='approved')
        .values('tariff__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    return {
        'total_premium': total_premium,
        'active_premium': active_premium,
        'expired_premium': expired_premium,
        'new_premium_30d': new_premium_30d,
        'income_30d': income_30d,
        'avg_premium_days': int(avg_days),
        'top_tariffs': [{'name': t['tariff__name'], 'count': t['count']} for t in top_tariffs]
    }


@sync_to_async
def get_yearly_stats():
    """Yillik statistika - oyma-oy"""
    from django.db.models import Count, Sum
    from datetime import datetime

    # Oy nomlari
    month_names = [
        'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
        'Iyul', 'Avgust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr'
    ]

    now = timezone.now()
    current_year = now.year

    # Yil boshidan hozirgi kungacha
    year_start = timezone.make_aware(datetime(current_year, 1, 1, 0, 0, 0))

    total_users = User.objects.filter(created_at__gte=year_start).count()
    total_premium = Payment.objects.filter(
        status='approved',
        created_at__gte=year_start
    ).count()

    total_income = Payment.objects.filter(
        status='approved',
        created_at__gte=year_start
    ).aggregate(total=Sum('tariff__price'))['total'] or 0

    # Oyma-oy statistika
    monthly_stats = []
    months_passed = now.month

    for month in range(1, 13):
        month_start = timezone.make_aware(datetime(current_year, month, 1, 0, 0, 0))

        # Keyingi oy boshi
        if month == 12:
            month_end = timezone.make_aware(datetime(current_year + 1, 1, 1, 0, 0, 0))
        else:
            month_end = timezone.make_aware(datetime(current_year, month + 1, 1, 0, 0, 0))

        # Faqat o'tgan oylar uchun statistika
        if month <= now.month:
            month_users = User.objects.filter(
                created_at__gte=month_start,
                created_at__lt=month_end
            ).count()

            month_premium = Payment.objects.filter(
                status='approved',
                created_at__gte=month_start,
                created_at__lt=month_end
            ).count()

            month_income = Payment.objects.filter(
                status='approved',
                created_at__gte=month_start,
                created_at__lt=month_end
            ).aggregate(total=Sum('tariff__price'))['total'] or 0
        else:
            month_users = 0
            month_premium = 0
            month_income = 0

        monthly_stats.append({
            'month': month,
            'month_name': month_names[month - 1],
            'users': month_users,
            'premium': month_premium,
            'income': month_income
        })

    avg_users_per_month = total_users // max(1, months_passed)
    avg_premium_per_month = total_premium // max(1, months_passed)

    return {
        'year': current_year,
        'total_users': total_users,
        'total_premium': total_premium,
        'total_income': total_income,
        'avg_users_per_month': avg_users_per_month,
        'avg_premium_per_month': avg_premium_per_month,
        'monthly_stats': monthly_stats
    }


# ==================== USER HELPER FUNCTIONS ====================

@sync_to_async
def get_users_list(filter_type: str, page: int = 1, per_page: int = 10):
    """Userlar ro'yxatini olish"""
    from datetime import timedelta

    queryset = User.objects.all()

    if filter_type == 'premium':
        queryset = queryset.filter(is_premium=True, premium_expires__gt=timezone.now())
    elif filter_type == 'regular':
        queryset = queryset.filter(is_premium=False)
    elif filter_type == 'today':
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        queryset = queryset.filter(created_at__gte=today_start)
    elif filter_type == 'banned':
        queryset = queryset.filter(is_banned=True)

    total_count = queryset.count()
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    offset = (page - 1) * per_page
    users = list(queryset.order_by('-created_at')[offset:offset + per_page])

    return users, total_pages, total_count


@sync_to_async
def give_user_premium(user_id: int, days: int) -> bool:
    """Userga premium berish"""
    from datetime import timedelta

    try:
        user = User.objects.get(user_id=user_id)

        if user.is_premium_active and user.premium_expires:
            # Mavjud premiumga qo'shish
            user.premium_expires = user.premium_expires + timedelta(days=days)
        else:
            # Yangi premium
            user.is_premium = True
            user.premium_expires = timezone.now() + timedelta(days=days)

        # Yangi davr -> tugash eslatmasi qayta yuborilishi mumkin
        user.premium_expiry_notified = False
        user.save()
        # Cache'ni tozalaymiz, aks holda premium 60s davomida ko'rinmaydi.
        clear_user_cache(user_id)
        return True
    except User.DoesNotExist:
        return False


@sync_to_async
def unban_user(user_id: int) -> bool:
    """Userni blokdan chiqarish"""
    try:
        user = User.objects.get(user_id=user_id)
        user.is_banned = False
        user.ban_reason = None
        user.save()
        clear_user_cache(user_id)
        return True
    except User.DoesNotExist:
        return False


@sync_to_async
def get_user_full_info(user_id: int):
    """User to'liq ma'lumotlarini olish"""
    try:
        user = User.objects.get(user_id=user_id)
        referrals_count = user.referrals.count()
        return {
            'user': user,
            'referrals_count': referrals_count
        }
    except User.DoesNotExist:
        return None


# ==================== KATEGORIYA FUNKSIYALARI ====================

@sync_to_async
def get_all_categories():
    """Barcha kategoriyalarni olish (aktiv va noaktiv)"""
    return list(Category.objects.all().order_by('order', 'name'))


@sync_to_async
def get_category_movies_count(category_id: int) -> int:
    """Kategoriyaga tegishli kinolar sonini olish"""
    return Movie.objects.filter(category_id=category_id).count()


@sync_to_async
def check_category_exists(name: str) -> bool:
    """Kategoriya mavjudligini tekshirish"""
    return Category.objects.filter(name__iexact=name).exists()


@sync_to_async
def create_category(name: str, emoji: str = ""):
    """Yangi kategoriya yaratish"""
    from django.utils.text import slugify

    # Slug yaratish
    base_slug = slugify(name)
    if not base_slug:
        base_slug = f"category-{Category.objects.count() + 1}"

    slug = base_slug
    counter = 1
    while Category.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    # Tartib raqamini aniqlash
    max_order = Category.objects.aggregate(max_order=Max('order'))['max_order'] or 0

    return Category.objects.create(
        name=name,
        emoji=emoji,
        slug=slug,
        order=max_order + 1,
        is_active=True
    )


@sync_to_async
def update_category(category_id: int, name: str, emoji: str) -> bool:
    """Kategoriyani yangilash"""
    try:
        category = Category.objects.get(id=category_id)
        category.name = name
        category.emoji = emoji
        category.save(update_fields=['name', 'emoji'])
        return True
    except Category.DoesNotExist:
        return False


@sync_to_async
def toggle_category_status(category_id: int) -> bool:
    """Kategoriya holatini o'zgartirish"""
    try:
        category = Category.objects.get(id=category_id)
        category.is_active = not category.is_active
        category.save(update_fields=['is_active'])
        return True
    except Category.DoesNotExist:
        return False


@sync_to_async
def delete_category(category_id: int) -> bool:
    """Kategoriyani o'chirish"""
    try:
        category = Category.objects.get(id=category_id)
        category.delete()
        return True
    except Category.DoesNotExist:
        return False
