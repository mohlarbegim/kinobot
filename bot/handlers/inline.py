from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultArticle, InlineQueryResultCachedVideo, InputTextMessageContent
from asgiref.sync import sync_to_async
from hashlib import md5

from apps.movies.models import Movie
from bot.utils import esc

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

    # Natijalarni tayyorlash
    results = []

    for movie in movies:
        # Unique ID yaratish
        result_id = md5(f"{movie.id}_{movie.code}".encode()).hexdigest()

        # Video natija
        try:
            result = InlineQueryResultCachedVideo(
                id=result_id,
                video_file_id=movie.file_id,
                title=movie.display_title,
                description=f"📝 Kod: {movie.code}",
                caption=f"🎬 <b>{esc(movie.display_title)}</b>\n📝 Kod: <code>{esc(movie.code)}</code>",
                parse_mode="HTML"
            )
            results.append(result)
        except Exception:
            # Video ishlamasa, matn natija
            result = InlineQueryResultArticle(
                id=result_id,
                title=movie.display_title,
                description=f"📝 Kod: {movie.code}",
                input_message_content=InputTextMessageContent(
                    message_text=f"🎬 <b>{esc(movie.display_title)}</b>\n📝 Kod: <code>{esc(movie.code)}</code>",
                    parse_mode="HTML"
                )
            )
            results.append(result)

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
