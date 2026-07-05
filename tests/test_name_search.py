"""
Bot ichida avtomatik nom bo'yicha qidiruv testlari:
- search_movies_by_name (DB helper)
- name_search_auto (catch-all matn handleri)
- name_search_results_kb (natija tugmalari -> movie_view = BOT yetkazadi)
- handler registratsiya tartibi (Command'lar va kod qidiruvidan KEYIN)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from asgiref.sync import sync_to_async

pytestmark = pytest.mark.django_db


def _msg(text):
    """Minimal Message mock."""
    m = AsyncMock()
    m.from_user = MagicMock()
    m.from_user.id = 123456789
    m.text = text
    m.answer = AsyncMock()
    return m


def _mk(movie_model, code, title='', title_uz='', is_active=True, file_id='V', is_premium=False):
    return movie_model.objects.create(
        code=code, title=title, title_uz=title_uz,
        is_active=is_active, file_id=file_id, is_premium=is_premium,
    )


# ==================== search_movies_by_name (DB helper) ====================

class TestSearchMoviesByName:

    def test_match_by_title(self, movie_model):
        from bot.handlers.user import search_movies_by_name
        self._mk = _mk
        _mk(movie_model, '70001', title='Avatar 2')
        codes = [m.code for m in search_movies_by_name.func('avatar')]
        assert '70001' in codes

    def test_match_by_title_uz(self, movie_model):
        from bot.handlers.user import search_movies_by_name
        _mk(movie_model, '70002', title='The Lion King', title_uz='Sher Qirol')
        codes = [m.code for m in search_movies_by_name.func('sher')]
        assert '70002' in codes

    def test_case_insensitive_partial(self, movie_model):
        from bot.handlers.user import search_movies_by_name
        _mk(movie_model, '70003', title='Interstellar')
        codes = [m.code for m in search_movies_by_name.func('STELLA')]
        assert '70003' in codes

    def test_inactive_excluded(self, movie_model):
        from bot.handlers.user import search_movies_by_name
        _mk(movie_model, '70004', title='Hidden', is_active=False)
        codes = [m.code for m in search_movies_by_name.func('hidden')]
        assert '70004' not in codes

    def test_limit_respected(self, movie_model):
        from bot.handlers.user import search_movies_by_name
        for i in range(15):
            _mk(movie_model, f'7100{i}', title=f'Batman {i}')
        results = search_movies_by_name.func('batman', limit=10)
        assert len(results) == 10


# ==================== name_search_results_kb ====================

class TestNameSearchResultsKb:

    def test_buttons_use_movie_view(self, movie_model):
        """Natija tugmalari movie_view: bo'lishi shart -> kinoni BOT yuboradi (inline emas)."""
        from bot.keyboards import name_search_results_kb
        m1 = _mk(movie_model, '72001', title='Alpha')
        m2 = _mk(movie_model, '72002', title='Beta', is_premium=True)
        kb = name_search_results_kb([m1, m2])
        datas = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert 'movie_view:72001' in datas
        assert 'movie_view:72002' in datas
        # "Yana qidirish" search_by_name'ga qaytaradi
        assert 'search_by_name' in datas


# ==================== name_search_auto (handler) ====================

class TestNameSearchAuto:

    async def test_short_query_hint(self):
        """3 harfdan kam -> maslahat, qidiruv yo'q."""
        from bot.handlers.user import name_search_auto
        m = _msg('ab')
        await name_search_auto(m, db_user=None, bot=AsyncMock())
        m.answer.assert_awaited_once()
        text = m.answer.call_args.args[0] if m.answer.call_args.args else m.answer.call_args.kwargs.get('text', '')
        assert '3' in text  # "kamida 3 harf"

    async def test_command_ignored(self):
        """Noma'lum /buyruq -> hech narsa qilmaydi (Command handlerlar tutmagan)."""
        from bot.handlers.user import name_search_auto
        m = _msg('/foobar')
        await name_search_auto(m, db_user=None, bot=AsyncMock())
        m.answer.assert_not_awaited()

    async def test_spaced_numeric_routes_to_code(self, monkeypatch):
        """' 516 ' (bo'shliqli kod) nom emas -> kod handleriga yo'naltiriladi."""
        import bot.handlers.user as u
        called = {}

        async def fake_code(message, db_user=None, bot=None):
            called['code'] = message.text.strip()

        monkeypatch.setattr(u, 'get_movie_by_code', fake_code)
        m = _msg('  516  ')
        await u.name_search_auto(m, db_user=None, bot=AsyncMock())
        assert called.get('code') == '516'
        m.answer.assert_not_awaited()

    async def test_results_use_name_search_kb(self, movie_model, monkeypatch):
        """Natija bo'lsa -> name_search_results_kb (movie_view tugmalari) bilan javob."""
        import bot.handlers.user as u
        monkeypatch.setattr(u, 'check_user_subscription', AsyncMock(return_value=[]))
        await sync_to_async(_mk)(movie_model, '73001', title='Avatar')
        m = _msg('avatar')
        await u.name_search_auto(m, db_user=None, bot=AsyncMock())
        m.answer.assert_awaited_once()
        kb = m.answer.call_args.kwargs.get('reply_markup')
        datas = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert any(d.startswith('movie_view:') for d in datas)

    async def test_no_results_offers_request(self, monkeypatch):
        """Topilmasa -> 'Kino so'rash' (request_movie) tugmasi taklif qilinadi."""
        import bot.handlers.user as u
        monkeypatch.setattr(u, 'check_user_subscription', AsyncMock(return_value=[]))
        m = _msg('zzznotexistqwerty')
        await u.name_search_auto(m, db_user=None, bot=AsyncMock())
        m.answer.assert_awaited_once()
        kb = m.answer.call_args.kwargs.get('reply_markup')
        datas = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert 'request_movie' in datas

    async def test_not_subscribed_blocks(self, movie_model, monkeypatch):
        """Obuna bo'lmagan user -> obuna so'raladi, qidiruv natijasi ko'rsatilmaydi."""
        import bot.handlers.user as u
        monkeypatch.setattr(u, 'check_user_subscription', AsyncMock(return_value=['fake_channel']))
        monkeypatch.setattr(u, 'subscription_prompt_text', lambda ch: 'SUBSCRIBE_TEXT')
        monkeypatch.setattr(u, 'channels_kb', lambda ch: 'SUBSCRIBE_KB')
        await sync_to_async(_mk)(movie_model, '74001', title='Avatar')
        m = _msg('avatar')
        await u.name_search_auto(m, db_user=None, bot=AsyncMock())
        m.answer.assert_awaited_once()
        assert m.answer.call_args.kwargs.get('reply_markup') == 'SUBSCRIBE_KB'


# ==================== Registratsiya tartibi (regression guard) ====================

class TestHandlerRegistrationOrder:

    def test_name_search_is_last_message_handler(self):
        """name_search_auto (catch-all) barcha Command va kod handlerlaridan KEYIN
        bo'lishi SHART - aks holda /top, /help kabi buyruqlarni yutib yuboradi."""
        from bot.handlers import user as u
        names = [h.callback.__name__ for h in u.router.message.handlers]
        assert names[-1] == 'name_search_auto'
        assert names.index('get_movie_by_code') < names.index('name_search_auto')
