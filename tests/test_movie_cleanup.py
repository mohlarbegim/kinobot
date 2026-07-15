"""
Yangi kino yuborilganда eskisi o'chirilishi testlari.

"Faqat oxirgisi qolib" - user yangi kod yuborsa, oldingi kino chatдан o'chadi.
Xabar id'lari DB'da (User.last_movie_message_ids) saqlanadi - bot qayta ishga
tushsa ham yo'qolmaydi.
"""
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from aiogram.exceptions import TelegramBadRequest

pytestmark = pytest.mark.django_db


def _msg_mock(message_id):
    """Telegram qaytaradigan Message (message_id butun son)."""
    m = MagicMock()
    m.message_id = message_id
    return m


def _mk_user(user_id):
    from apps.users.models import User
    User.objects.filter(user_id=user_id).delete()
    return User.objects.create(user_id=user_id, username='u', full_name='U')


async def _amk_user(user_id):
    """Async testda user yaratish.

    MUHIM: sync `db_user` fixture'i ishlatilmaydi - u test tranzaksiyasini ushlab
    turadi va sync_to_async boshqa oqimdan yozmoqchi bo'lganда SQLite
    "database table is locked" beradi.
    """
    from asgiref.sync import sync_to_async
    return await sync_to_async(_mk_user)(user_id)


# ==================== _message_ids ====================

class TestMessageIds:

    def test_collects_int_ids(self):
        from bot.handlers.user import _message_ids
        assert _message_ids([_msg_mock(5), _msg_mock(6)]) == [5, 6]

    def test_ignores_non_int(self):
        """AsyncMock .message_id Mock qaytaradi - u JSONField'ga tushmasligi kerak."""
        from bot.handlers.user import _message_ids
        bad = MagicMock()  # message_id = Mock, int emas
        assert _message_ids([bad]) == []

    def test_empty(self):
        from bot.handlers.user import _message_ids
        assert _message_ids([]) == []


# ==================== saqlash / o'qish ====================

class TestSaveLoadMessageIds:

    def test_save_and_get(self, db_user):
        from bot.handlers.user import save_last_movie_messages, get_last_movie_messages
        save_last_movie_messages.func(db_user.user_id, [11, 12])
        assert get_last_movie_messages.func(db_user.user_id) == [11, 12]

    def test_empty_when_never_sent(self, db_user):
        from bot.handlers.user import get_last_movie_messages
        assert get_last_movie_messages.func(db_user.user_id) == []

    def test_clearing(self, db_user):
        from bot.handlers.user import save_last_movie_messages, get_last_movie_messages
        save_last_movie_messages.func(db_user.user_id, [11])
        save_last_movie_messages.func(db_user.user_id, [])
        assert get_last_movie_messages.func(db_user.user_id) == []

    def test_unknown_user_does_not_crash(self):
        from bot.handlers.user import get_last_movie_messages, save_last_movie_messages
        save_last_movie_messages.func(999000111, [1])   # yo'q user - xato bermasligi kerak
        assert get_last_movie_messages.func(999000111) == []


# ==================== cleanup_previous_movie ====================

class TestCleanupPreviousMovie:

    async def test_deletes_stored_messages(self):
        from bot.handlers.user import cleanup_previous_movie, save_last_movie_messages
        from asgiref.sync import sync_to_async

        user = await _amk_user(650001)
        await sync_to_async(save_last_movie_messages.func)(user.user_id, [21, 22])
        bot = AsyncMock()

        await cleanup_previous_movie(bot, user.user_id)

        assert bot.delete_message.await_count == 2
        deleted = {c.kwargs['message_id'] for c in bot.delete_message.await_args_list}
        assert deleted == {21, 22}

    async def test_clears_ids_after_delete(self):
        from bot.handlers.user import cleanup_previous_movie, save_last_movie_messages, get_last_movie_messages
        from asgiref.sync import sync_to_async

        user = await _amk_user(650002)
        await sync_to_async(save_last_movie_messages.func)(user.user_id, [31])
        await cleanup_previous_movie(AsyncMock(), user.user_id)

        assert await sync_to_async(get_last_movie_messages.func)(user.user_id) == []

    async def test_nothing_stored_does_nothing(self):
        from bot.handlers.user import cleanup_previous_movie
        user = await _amk_user(650003)
        bot = AsyncMock()
        await cleanup_previous_movie(bot, user.user_id)
        bot.delete_message.assert_not_awaited()

    async def test_already_deleted_message_tolerated(self):
        """Xabar allaqachon o'chirilgan / 48 soatdan eski -> Telegram xato beradi.

        Bu NORMAL holat: yiqilmasligi va qolgan xabarlarni o'chirishда davom etishi kerak.
        """
        from bot.handlers.user import cleanup_previous_movie, save_last_movie_messages
        from asgiref.sync import sync_to_async

        user = await _amk_user(650004)
        await sync_to_async(save_last_movie_messages.func)(user.user_id, [41, 42])
        bot = AsyncMock()
        bot.delete_message = AsyncMock(
            side_effect=TelegramBadRequest(method=MagicMock(), message="message to delete not found")
        )

        await cleanup_previous_movie(bot, user.user_id)  # ko'tarilmasligi kerak

        assert bot.delete_message.await_count == 2  # ikkalasi ham urinildi

    async def test_unexpected_error_tolerated(self):
        """O'chirishдаги kutilmagan xato kino yuborishni buzmasligi kerak."""
        from bot.handlers.user import cleanup_previous_movie, save_last_movie_messages
        from asgiref.sync import sync_to_async

        user = await _amk_user(650005)
        await sync_to_async(save_last_movie_messages.func)(user.user_id, [51])
        bot = AsyncMock()
        bot.delete_message = AsyncMock(side_effect=Exception("tarmoq"))

        await cleanup_previous_movie(bot, user.user_id)  # ko'tarilmasligi kerak


# ==================== send_movie_or_notice id qaytarishi ====================

class TestSendReturnsIds:

    async def test_video_only_returns_one_id(self):
        from bot.handlers.user import send_movie_or_notice
        target = AsyncMock()
        target.answer_video = AsyncMock(return_value=_msg_mock(61))
        movie = SimpleNamespace(file_id='V', thumbnail_file_id='')

        ids = await send_movie_or_notice(target, movie, 'CAP')

        assert ids == [61]

    async def test_poster_and_video_returns_two_ids(self):
        """Poster + video = 2 ta xabar -> ikkalasi ham o'chirilishi uchun 2 ta id."""
        from bot.handlers.user import send_movie_or_notice
        target = AsyncMock()
        target.answer_photo = AsyncMock(return_value=_msg_mock(71))
        target.answer_video = AsyncMock(return_value=_msg_mock(72))
        movie = SimpleNamespace(file_id='V', thumbnail_file_id='P')

        ids = await send_movie_or_notice(target, movie, 'CAP')

        assert ids == [71, 72]

    async def test_text_notice_returns_id(self):
        from bot.handlers.user import send_movie_or_notice
        target = AsyncMock()
        target.answer = AsyncMock(return_value=_msg_mock(81))
        movie = SimpleNamespace(file_id='', thumbnail_file_id='')

        ids = await send_movie_or_notice(target, movie, 'CAP')

        assert ids == [81]


# ==================== To'liq oqim: yangi kod -> eskisi o'chadi ====================

class TestNewCodeDeletesPrevious:

    async def test_previous_movie_deleted_on_new_code(self, movie_model, monkeypatch):
        import bot.handlers.user as u
        from asgiref.sync import sync_to_async

        user = await _amk_user(650010)
        await sync_to_async(movie_model.objects.create)(
            code='65001', title='Yangi kino', is_active=True, file_id='V',
        )
        # oldin yuborilgan kino xabarlari
        await sync_to_async(u.save_last_movie_messages.func)(user.user_id, [91, 92])

        monkeypatch.setattr(u, 'check_user_subscription', AsyncMock(return_value=[]))
        monkeypatch.setattr(u, 'get_bot_link', AsyncMock(return_value='@bot'))

        bot = AsyncMock()
        m = AsyncMock()
        m.from_user = MagicMock()
        m.from_user.id = user.user_id
        m.text = '65001'
        m.answer_video = AsyncMock(return_value=_msg_mock(93))

        await u.get_movie_by_code(m, db_user=user, bot=bot)

        # eskilari o'chirildi
        deleted = {c.kwargs['message_id'] for c in bot.delete_message.await_args_list}
        assert deleted == {91, 92}
        # yangisi saqlandi
        assert await sync_to_async(u.get_last_movie_messages.func)(user.user_id) == [93]
