"""
Matn formatlash testlari:
- safe_html  — admin yozgan bold/italic SAQLANADI, xavfli narsa escape bo'ladi
- esc        — user yozgan matn HAR DOIM escape (xavfsizlik: OLIB TASHLAMANG)
- to_plain   — Telegram alert uchun sof matn
- html_text_of — Telegram formatlashini yo'qotmaslik
- premium_required shabloni botga ULANGANmi
"""
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.django_db


# ==================== safe_html ====================

class TestSafeHtml:
    """Admin yozgan matn: formatlash saqlanadi, lekin parse xatosi bo'lmaydi."""

    def test_bold_preserved(self):
        from bot.utils import safe_html
        assert safe_html('<b>Qalin</b>') == '<b>Qalin</b>'

    def test_italic_preserved(self):
        from bot.utils import safe_html
        assert safe_html('<i>Qiya</i>') == '<i>Qiya</i>'

    def test_mixed_tags_preserved(self):
        from bot.utils import safe_html
        out = safe_html('<b>A</b> va <i>B</i> va <u>C</u> va <s>D</s>')
        assert out == '<b>A</b> va <i>B</i> va <u>C</u> va <s>D</s>'

    def test_code_and_pre_preserved(self):
        from bot.utils import safe_html
        assert safe_html('<code>x</code>') == '<code>x</code>'
        assert safe_html('<pre>y</pre>') == '<pre>y</pre>'

    def test_link_preserved(self):
        from bot.utils import safe_html
        assert safe_html('<a href="https://t.me/x">link</a>') == '<a href="https://t.me/x">link</a>'

    def test_link_with_query_ampersand(self):
        """Havoladagi & escape bo'lib link buzilmasligi kerak."""
        from bot.utils import safe_html
        out = safe_html('<a href="https://x.uz/?a=1&b=2">l</a>')
        assert out == '<a href="https://x.uz/?a=1&b=2">l</a>'

    def test_disallowed_tag_escaped(self):
        """Telegram qo'llab-quvvatlamaydigan teg MATNGA aylanadi (parse xatosi bermaydi)."""
        from bot.utils import safe_html
        out = safe_html('<script>alert(1)</script>')
        assert '<script>' not in out
        assert '&lt;script&gt;' in out

    def test_stray_ampersand_escaped(self):
        """Kino nomidagi tasodifiy & Telegram parse xatosini bermasligi kerak."""
        from bot.utils import safe_html
        assert safe_html('Tom & Jerry') == 'Tom &amp; Jerry'

    def test_stray_lt_escaped(self):
        from bot.utils import safe_html
        assert safe_html('5 < 10') == '5 &lt; 10'

    def test_none_returns_empty(self):
        from bot.utils import safe_html
        assert safe_html(None) == ''


class TestEscStillEscapes:
    """XAVFSIZLIK: user kiritgan matn HAR DOIM escape bo'lishi shart."""

    def test_user_name_with_tag_escaped(self):
        from bot.utils import esc
        # User o'z ismini "<b>x" qilib qo'yishi mumkin - shablon uni xom almashtiradi
        assert esc('<b>Hacker</b>') == '&lt;b&gt;Hacker&lt;/b&gt;'

    def test_esc_and_safe_html_differ(self):
        """esc va safe_html farqi saqlanib qolishi kerak (regressiya guard)."""
        from bot.utils import esc, safe_html
        assert esc('<b>x</b>') != safe_html('<b>x</b>')


# ==================== to_plain ====================

class TestToPlain:
    """Telegram alert HTML'ni qo'llab-quvvatlamaydi va ~200 belgi bilan cheklangan."""

    def test_tags_stripped(self):
        from bot.utils import to_plain
        assert to_plain('<b>Qalin</b> matn') == 'Qalin matn'

    def test_entities_unescaped(self):
        from bot.utils import to_plain
        assert to_plain('Tom &amp; Jerry') == 'Tom & Jerry'

    def test_truncated_to_limit(self):
        from bot.utils import to_plain
        assert len(to_plain('x' * 500)) == 200

    def test_custom_limit(self):
        from bot.utils import to_plain
        assert len(to_plain('x' * 50, limit=10)) == 10

    def test_none_returns_empty(self):
        from bot.utils import to_plain
        assert to_plain(None) == ''


# ==================== html_text_of ====================

class TestHtmlTextOf:

    def test_uses_html_text(self):
        """Formatlash saqlanishi uchun message.html_text ishlatiladi."""
        from bot.utils import html_text_of
        m = SimpleNamespace(html_text='<b>Qalin</b>', text='Qalin', caption=None)
        assert html_text_of(m) == '<b>Qalin</b>'

    def test_falls_back_when_no_text(self):
        """Matn/caption bo'lmasa aiogram TypeError beradi - yiqilmasligi kerak."""
        from bot.utils import html_text_of

        class NoText:
            text = None
            caption = None

            @property
            def html_text(self):
                raise TypeError("This message doesn't have any text.")

        assert html_text_of(NoText()) == ''

    def test_falls_back_to_caption(self):
        from bot.utils import html_text_of

        class OnlyCaption:
            text = None
            caption = 'Izoh'

            @property
            def html_text(self):
                raise TypeError("nope")

        assert html_text_of(OnlyCaption()) == 'Izoh'


# ==================== premium_required shabloni ULANGANmi ====================

class TestPremiumRequiredWired:
    """Admin premium xabarini o'zgartirsa - BOT ham o'sha xabarni yuborishi shart.

    Ilgari `premium_required` hech qayerda o'qilmasdi: admin tahrirlagan, lekin
    bot hardcoded matn yuborardi.
    """

    def test_template_renders_title(self):
        from apps.core.models import MessageTemplate
        out = MessageTemplate.get_message('premium_required', title='Avatar')
        assert 'Avatar' in out

    def test_admin_edit_is_used_by_bot(self):
        """DB'dagi tahrirlangan matn get_message orqali qaytishi kerak."""
        from apps.core.models import MessageTemplate
        MessageTemplate.objects.update_or_create(
            message_type='premium_required',
            defaults={'title': 'Premium talab qilish', 'content': 'MENING YANGI MATNIM: {title}'},
        )
        out = MessageTemplate.get_message('premium_required', title='Salaar')
        assert out == 'MENING YANGI MATNIM: Salaar'
        MessageTemplate.objects.filter(message_type='premium_required').delete()

    async def test_paywall_sends_template(self, movie_model, monkeypatch):
        """get_movie_by_code premium paywall'da shablonni yuboradi (hardcoded emas)."""
        import bot.handlers.user as u
        from asgiref.sync import sync_to_async
        from apps.core.models import MessageTemplate

        await sync_to_async(MessageTemplate.objects.update_or_create)(
            message_type='premium_required',
            defaults={'title': 'Premium', 'content': 'SHABLON_MATNI {title}'},
        )
        await sync_to_async(movie_model.objects.create)(
            code='75001', title='Prem', is_active=True, is_premium=True, file_id='V',
        )

        monkeypatch.setattr(u, 'check_user_subscription', AsyncMock(return_value=[]))
        # chegirma o'chirilgan -> oddiy paywall shoxi
        monkeypatch.setattr(u, 'get_bot_settings', AsyncMock(return_value=None))
        monkeypatch.setattr(u, 'is_user_admin', AsyncMock(return_value=False))

        m = AsyncMock()
        m.from_user = MagicMock()
        m.from_user.id = 123456789
        m.text = '75001'
        m.answer = AsyncMock()

        db_user = SimpleNamespace(user_id=123456789, is_premium_active=False)
        await u.get_movie_by_code(m, db_user=db_user, bot=AsyncMock())

        m.answer.assert_awaited_once()
        sent = m.answer.call_args.args[0]
        assert 'SHABLON_MATNI' in sent
        assert 'Prem' in sent

        await sync_to_async(MessageTemplate.objects.filter(message_type='premium_required').delete)()
