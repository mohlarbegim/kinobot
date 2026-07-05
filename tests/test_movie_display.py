"""
send_movie_or_notice — poster/video ko'rsatish mantig'i testlari
"""
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

pytestmark = pytest.mark.django_db


def _movie(file_id='', thumbnail_file_id=''):
    return SimpleNamespace(file_id=file_id, thumbnail_file_id=thumbnail_file_id)


async def _run(movie):
    from bot.handlers.user import send_movie_or_notice
    target = AsyncMock()
    await send_movie_or_notice(target, movie, "CAP", reply_markup="KB")
    return target


class TestSendMovieOrNotice:

    async def test_video_only(self):
        t = await _run(_movie(file_id='VID'))
        t.answer_video.assert_awaited_once()
        t.answer_photo.assert_not_awaited()
        t.answer.assert_not_awaited()

    async def test_poster_only(self):
        t = await _run(_movie(thumbnail_file_id='POS'))
        t.answer_photo.assert_awaited_once()
        t.answer_video.assert_not_awaited()
        # Poster caption + tugmalar bilan yuboriladi
        _, kwargs = t.answer_photo.call_args
        assert kwargs.get('photo') == 'POS'
        assert kwargs.get('caption') == 'CAP'
        assert kwargs.get('reply_markup') == 'KB'

    async def test_poster_and_video_both_sent(self):
        """Poster ham video ham bo'lsa: poster (tugmalar bilan) + video"""
        t = await _run(_movie(file_id='VID', thumbnail_file_id='POS'))
        t.answer_photo.assert_awaited_once()
        t.answer_video.assert_awaited_once()
        # Poster caption/tugmalarni oladi, video esa sof (tomosha uchun)
        _, pkwargs = t.answer_photo.call_args
        assert pkwargs.get('reply_markup') == 'KB'
        _, vkwargs = t.answer_video.call_args
        assert vkwargs.get('video') == 'VID'

    async def test_neither_text_notice(self):
        t = await _run(_movie())
        t.answer.assert_awaited_once()
        t.answer_video.assert_not_awaited()
        t.answer_photo.assert_not_awaited()
