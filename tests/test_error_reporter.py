"""
Xatolikni bug kanaliga yuborish testlari.

MUHIM: report_error global error handler ichidan chaqiriladi - u HECH QACHON
xato tashlamasligi kerak (aks holda "xato ustiga xato" tsikli boshlanadi).
"""
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture(autouse=True)
def _clear_dedup():
    """Har test oldidan dedup keshini tozalash (modul darajasidagi TTLCache)."""
    from bot.utils import error_reporter
    error_reporter._recent_errors.clear()
    yield
    error_reporter._recent_errors.clear()


def _boom(msg='test xato'):
    """Haqiqiy traceback'li exception yaratish."""
    try:
        raise ValueError(msg)
    except ValueError as e:
        return e


class TestReportError:

    async def test_sends_to_channel(self, monkeypatch):
        from bot.utils.error_reporter import report_error
        from django.conf import settings

        monkeypatch.setattr(settings, 'BUG_CHANNEL_ID', '-100123', raising=False)
        bot = AsyncMock()

        ok = await report_error(bot, _boom('xato bor'), None)

        assert ok is True
        bot.send_message.assert_awaited_once()
        text = bot.send_message.call_args.kwargs['text']
        assert 'ValueError' in text
        assert 'xato bor' in text

    async def test_no_channel_configured_does_nothing(self, monkeypatch):
        """Kanal sozlanmagan bo'lsa - jimgina o'tadi, xato bermaydi."""
        from bot.utils.error_reporter import report_error
        from django.conf import settings

        monkeypatch.setattr(settings, 'BUG_CHANNEL_ID', '', raising=False)
        bot = AsyncMock()

        ok = await report_error(bot, _boom(), None)

        assert ok is False
        bot.send_message.assert_not_awaited()

    async def test_duplicate_error_not_spammed(self, monkeypatch):
        """Bir xil xato takrorlansa kanal spam bo'lmasligi kerak."""
        from bot.utils.error_reporter import report_error
        from django.conf import settings

        monkeypatch.setattr(settings, 'BUG_CHANNEL_ID', '-100123', raising=False)
        bot = AsyncMock()

        def same_error():
            try:
                raise ValueError('bir xil')
            except ValueError as e:
                return e

        first = await report_error(bot, same_error(), None)
        second = await report_error(bot, same_error(), None)

        assert first is True
        assert second is False  # dedup ishladi
        assert bot.send_message.await_count == 1

    async def test_different_errors_both_sent(self, monkeypatch):
        """Har xil joydagi xatolar alohida yuboriladi."""
        from bot.utils.error_reporter import report_error
        from django.conf import settings

        monkeypatch.setattr(settings, 'BUG_CHANNEL_ID', '-100123', raising=False)
        bot = AsyncMock()

        def err_a():
            try:
                raise ValueError('A')
            except ValueError as e:
                return e

        def err_b():
            try:
                raise KeyError('B')
            except KeyError as e:
                return e

        await report_error(bot, err_a(), None)
        await report_error(bot, err_b(), None)

        assert bot.send_message.await_count == 2

    async def test_never_raises_when_send_fails(self, monkeypatch):
        """Kanalga yuborish o'zi xato bersa ham report_error yiqilmasligi SHART."""
        from bot.utils.error_reporter import report_error
        from django.conf import settings

        monkeypatch.setattr(settings, 'BUG_CHANNEL_ID', '-100123', raising=False)
        bot = AsyncMock()
        bot.send_message = AsyncMock(side_effect=Exception("kanal topilmadi"))

        ok = await report_error(bot, _boom(), None)  # ko'tarilmasligi kerak

        assert ok is False

    async def test_includes_user_context(self, monkeypatch):
        """Xabarda kim/nima yuborgani bo'lsa - debug qilish oson."""
        from bot.utils.error_reporter import report_error
        from django.conf import settings

        monkeypatch.setattr(settings, 'BUG_CHANNEL_ID', '-100123', raising=False)
        bot = AsyncMock()

        update = SimpleNamespace(
            update_id=555,
            message=SimpleNamespace(
                from_user=SimpleNamespace(id=777, username='tester'),
                text='516',
            ),
            callback_query=None,
        )

        await report_error(bot, _boom(), update)

        text = bot.send_message.call_args.kwargs['text']
        assert '777' in text
        assert 'tester' in text
        assert '516' in text
        assert '555' in text

    async def test_long_traceback_truncated(self, monkeypatch):
        """Telegram limiti 4096 - uzun traceback qirqilishi kerak."""
        from bot.utils.error_reporter import report_error
        from django.conf import settings

        monkeypatch.setattr(settings, 'BUG_CHANNEL_ID', '-100123', raising=False)
        bot = AsyncMock()

        await report_error(bot, _boom('x' * 5000), None)

        text = bot.send_message.call_args.kwargs['text']
        assert len(text) < 4096

    async def test_bad_update_object_does_not_break(self, monkeypatch):
        """Kutilmagan update shakli kontekst yig'ishni buzsa ham hisobot ketishi kerak."""
        from bot.utils.error_reporter import report_error
        from django.conf import settings

        monkeypatch.setattr(settings, 'BUG_CHANNEL_ID', '-100123', raising=False)
        bot = AsyncMock()

        class Weird:
            @property
            def message(self):
                raise RuntimeError('bo`m')

        ok = await report_error(bot, _boom(), Weird())

        assert ok is True
        bot.send_message.assert_awaited_once()
