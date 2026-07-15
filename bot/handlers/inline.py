from aiogram import Router
from aiogram.types import (
    InlineQuery, InlineQueryResultArticle, InlineQueryResultCachedVideo,
    InlineQueryResultCachedPhoto, InputTextMessageContent,
)
from asgiref.sync import sync_to_async
from hashlib import md5

from apps.movies.models import Movie
from bot.utils import esc, safe_html

router = Router()


@router.inline_query()
async def inline_search(inline_query: InlineQuery):
    """Inline rejimda kino qidirish"""
    query = inline_query.query.strip()

    # Bo'sh query bo'lsa
    if not query:
        await inline_query.answer(
            results=[],
            cache_time=1,
            switch_pm_text="🔍 Kino nomini yozing...",
            switch_pm_parameter="start"
        )
        return

    # Qisqa query
    if len(query) < 2:
        await inline_query.answer(
            results=[],
            cache_time=1,
            switch_pm_text="⚠️ Kamida 2 ta harf kiriting",
            switch_pm_parameter="start"
        )
        return

    # Qidirish
    movies = await search_movies_inline(query, limit=20)

    if not movies:
        await inline_query.answer(
            results=[],
            cache_time=10,
            switch_pm_text=f"😕 «{query}» topilmadi",
            switch_pm_parameter="start"
        )
        return

    # Foydalanuvchi premium kinolarni ko'ra oladimi (haqiqiy premium, trial EMAS)
    user_is_premium = await user_can_watch_premium(inline_query.from_user.id)

    # Natijalarni tayyorlash
    results = []

    for movie in movies:
        # Unique ID yaratish
        result_id = md5(f"{movie.id}_{movie.code}".encode()).hexdigest()

        # Premium kino + premium bo'lmagan foydalanuvchi -> videoni BERMAYMIZ.
        # O'rniga "Premium sotib oling" natijasi ko'rsatiladi (paywall bypass'ni oldini oladi).
        if movie.is_premium and not user_is_premium:
            results.append(InlineQueryResultArticle(
                id=result_id,
                title=f"💎 {movie.display_title} (Premium)",
                description="Premium kino — ko'rish uchun Premium sotib oling",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        f"💎 <b>{safe_html(movie.display_title)}</b>\n\n"
                        "Bu <b>Premium</b> kino. Ko'rish uchun Premium sotib oling.\n"
                        "👉 /premium"
                    ),
                    parse_mode="HTML"
                )
            ))
            continue

        caption = f"🎬 <b>{safe_html(movie.display_title)}</b>\n📝 Kod: <code>{esc(movie.code)}</code>"

        if movie.file_id:
            # Video bor -> cached video natija
            results.append(InlineQueryResultCachedVideo(
                id=result_id,
                video_file_id=movie.file_id,
                title=movie.display_title,
                description=f"📝 Kod: {movie.code}",
                caption=caption,
                parse_mode="HTML",
            ))
        elif movie.thumbnail_file_id:
            # Video yo'q, poster bor -> cached photo natija
            results.append(InlineQueryResultCachedPhoto(
                id=result_id,
                photo_file_id=movie.thumbnail_file_id,
                title=movie.display_title,
                description=f"📝 Kod: {movie.code}",
                caption=caption,
                parse_mode="HTML",
            ))
        else:
            # Media yo'q -> matn natija (kod bilan). MUHIM: bo'sh file_id bilan
            # CachedVideo yaratmaymiz - u butun inline javobni buzardi.
            results.append(InlineQueryResultArticle(
                id=result_id,
                title=movie.display_title,
                description=f"📝 Kod: {movie.code}",
                input_message_content=InputTextMessageContent(
                    message_text=caption,
                    parse_mode="HTML",
                )
            ))

    await inline_query.answer(
        results=results,
        cache_time=60,
        is_personal=True
    )


@sync_to_async
def search_movies_inline(query: str, limit: int = 20):
    """Inline uchun kino qidirish"""
    from django.db.models import Q

    return list(
        Movie.objects.filter(
            Q(title__icontains=query) | Q(title_uz__icontains=query),
            is_active=True
        ).order_by('-views')[:limit]
    )


@sync_to_async
def user_can_watch_premium(user_id: int) -> bool:
    """Foydalanuvchi premium kinolarni ko'ra oladimi (haqiqiy premium, trial emas)."""
    from apps.users.models import User
    u = User.objects.filter(user_id=user_id).first()
    return bool(u and u.is_premium_active)
