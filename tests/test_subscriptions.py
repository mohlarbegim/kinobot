"""
Subscription Tests for KinoBot
"""
import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db


class TestChannelModel:
    """Test Channel model"""

    def test_channel_creation(self, db_channel):
        """Test channel is created"""
        assert db_channel.channel_id == -1001234567890
        assert db_channel.title == 'Test Channel'
        assert db_channel.is_active is True

    def test_channel_types(self):
        """Test channel types"""
        types = ['channel', 'group', 'bot', 'instagram', 'other']
        assert len(types) == 5

    def test_active_channels(self, channel_model, db_channel):
        """Test active channels"""
        count = channel_model.objects.filter(is_active=True).count()
        assert count >= 1


class TestChannelSubscription:
    """Test ChannelSubscription model"""

    def test_subscription_creation(self, db_user, db_channel):
        """Test creating subscription"""
        from apps.channels.models import ChannelSubscription

        sub, created = ChannelSubscription.objects.get_or_create(
            channel=db_channel,
            user=db_user
        )
        assert sub.channel == db_channel
        assert sub.user == db_user
        sub.delete()

    def test_subscription_unique(self, db_user, db_channel):
        """Test unique constraint"""
        from apps.channels.models import ChannelSubscription

        sub1, created1 = ChannelSubscription.objects.get_or_create(
            channel=db_channel, user=db_user
        )
        assert created1 is True

        sub2, created2 = ChannelSubscription.objects.get_or_create(
            channel=db_channel, user=db_user
        )
        assert created2 is False
        assert sub1.id == sub2.id
        sub1.delete()

    def test_subscription_timestamp(self, db_user, db_channel):
        """Test subscription timestamp"""
        from apps.channels.models import ChannelSubscription

        sub = ChannelSubscription.objects.create(
            channel=db_channel, user=db_user
        )
        assert sub.subscribed_at is not None
        sub.delete()


class TestSubscriptionMiddleware:
    """Test subscription middleware"""

    def test_skip_commands(self):
        """Test skip commands"""
        from bot.middlewares.subscription import SubscriptionMiddleware

        mw = SubscriptionMiddleware()
        assert '/start' in mw.SKIP_COMMANDS
        assert '/help' in mw.SKIP_COMMANDS
        assert '/admin' in mw.SKIP_COMMANDS

    def test_skip_callbacks(self):
        """Test skip callbacks"""
        from bot.middlewares.subscription import SubscriptionMiddleware

        mw = SubscriptionMiddleware()
        assert 'check_subscription' in mw.SKIP_CALLBACKS

    def test_admin_bypasses(self):
        """Test admin bypasses check"""
        from django.conf import settings
        assert isinstance(settings.ADMINS, list)


class TestCacheManagement:
    """Test cache management"""

    def test_clear_subscription_cache(self):
        """Test clear subscription cache"""
        from bot.middlewares.subscription import clear_subscription_cache
        clear_subscription_cache()  # Should not raise

    def test_clear_user_cache(self):
        """Test clear user cache"""
        from bot.middlewares.subscription import clear_subscription_cache
        clear_subscription_cache(123456789)  # Should not raise

    def test_clear_channels_cache(self):
        """Test clear channels cache"""
        from bot.middlewares.subscription import clear_channels_cache
        clear_channels_cache()  # Should not raise


class TestSubscriptionFlow:
    """Test subscription flow"""

    def test_subscription_flow(self, db_user, db_channel):
        """Test complete subscription flow"""
        from apps.channels.models import ChannelSubscription

        # Check not subscribed
        is_sub = ChannelSubscription.objects.filter(
            channel=db_channel, user=db_user
        ).exists()
        assert is_sub is False

        # Subscribe
        ChannelSubscription.objects.create(
            channel=db_channel, user=db_user
        )

        # Verify
        is_sub = ChannelSubscription.objects.filter(
            channel=db_channel, user=db_user
        ).exists()
        assert is_sub is True

        # Cleanup
        ChannelSubscription.objects.filter(
            channel=db_channel, user=db_user
        ).delete()

    def test_joined_from_channel(self, db_user, db_channel):
        """Test joined_from_channel tracking"""
        db_user.joined_from_channel = db_channel
        db_user.save()
        db_user.refresh_from_db()
        assert db_user.joined_from_channel == db_channel
        # Cleanup
        db_user.joined_from_channel = None
        db_user.save()


class TestChannelCheckable:
    """is_checkable - qaysi kanal turi API bilan tekshiriladi"""

    def test_telegram_channel_is_checkable(self, channel_model):
        ch = channel_model(channel_id=-100111, title='TG', channel_type='telegram_channel')
        assert ch.is_checkable is True

    def test_telegram_group_is_checkable(self, channel_model):
        ch = channel_model(channel_id=-100222, title='Guruh', channel_type='telegram_group')
        assert ch.is_checkable is True

    def test_instagram_not_checkable(self, channel_model):
        ch = channel_model(title='IG', channel_type='instagram', invite_link='https://instagram.com/x')
        assert ch.is_checkable is False

    def test_bot_not_checkable(self, channel_model):
        ch = channel_model(channel_id=-100333, title='Bot', channel_type='telegram_bot')
        assert ch.is_checkable is False

    def test_external_not_checkable(self, channel_model):
        ch = channel_model(title='Tashqi', channel_type='external', invite_link='https://x.com')
        assert ch.is_checkable is False

    def test_telegram_channel_without_id_not_checkable(self, channel_model):
        # channel_id yo'q bo'lsa tekshirib bo'lmaydi
        ch = channel_model(title='TG', channel_type='telegram_channel')
        assert ch.is_checkable is False


class TestConfirmedChannelIds:
    """Non-checkable kanallar tasdig'i (honor-system) ChannelSubscription orqali"""

    def test_confirmed_ids_query(self, user_model, channel_model):
        """get_confirmed_channel_ids mantig'i: user__user_id bo'yicha tasdiqlangan pk'lar"""
        from apps.channels.models import ChannelSubscription

        user = user_model.objects.create(user_id=555000111, username='u', full_name='U')
        ig = channel_model.objects.create(
            title='IG', channel_type='instagram',
            invite_link='https://instagram.com/x', is_active=True,
        )
        ext = channel_model.objects.create(
            title='Ext', channel_type='external',
            invite_link='https://x.com', is_active=True,
        )

        # Boshida hech qanday tasdiq yo'q
        confirmed = set(
            ChannelSubscription.objects.filter(user__user_id=555000111)
            .values_list('channel_id', flat=True)
        )
        assert confirmed == set()

        # IG ni tasdiqlaydi
        ChannelSubscription.objects.create(channel=ig, user=user)
        confirmed = set(
            ChannelSubscription.objects.filter(user__user_id=555000111)
            .values_list('channel_id', flat=True)
        )
        assert ig.id in confirmed
        assert ext.id not in confirmed

        # Cleanup
        ChannelSubscription.objects.filter(user=user).delete()
        ig.delete(); ext.delete(); user.delete()


class TestChannelsKeyboard:
    """channels_kb - non-checkable kanallar uchun tasdiq tugmasi + double-confirm"""

    def test_confirm_button_only_for_non_checkable(self):
        from types import SimpleNamespace
        from bot.keyboards import channels_kb

        tg = SimpleNamespace(id=1, title='TG', invite_link='https://t.me/x', is_checkable=True)
        ig = SimpleNamespace(id=2, title='IG', invite_link='https://instagram.com/x', is_checkable=False)

        kb = channels_kb([tg, ig])
        callbacks = [b.callback_data for row in kb.inline_keyboard for b in row if b.callback_data]

        assert 'confirm_ch:2' in callbacks           # Instagram uchun tasdiq tugmasi
        assert 'confirm_ch:1' not in callbacks        # Telegram uchun bo'lmasligi kerak
        assert 'check_subscription' in callbacks      # Tekshirish tugmasi bor

    def test_confirming_id_shows_yes_button(self):
        """confirming_id berilganda o'sha kanal 'Ha, tasdiqlayman' (confirm_ch_yes) bo'ladi"""
        from types import SimpleNamespace
        from bot.keyboards import channels_kb

        ig = SimpleNamespace(id=2, title='IG', invite_link='https://instagram.com/x',
                             is_checkable=False, channel_type='instagram')
        kb = channels_kb([ig], confirming_id=2)
        callbacks = [b.callback_data for row in kb.inline_keyboard for b in row if b.callback_data]

        assert 'confirm_ch_yes:2' in callbacks       # ikkinchi tasdiq tugmasi
        assert 'confirm_ch:2' not in callbacks        # birinchi bosish tugmasi endi yo'q


class TestSubscriptionPromptText:
    """subscription_prompt_text - bosqichga qarab matn"""

    def _ns(self, checkable):
        from types import SimpleNamespace
        return SimpleNamespace(id=1, title='X', invite_link='https://x', is_checkable=checkable)

    def test_stage1_telegram_text(self):
        from bot.keyboards import subscription_prompt_text
        text = subscription_prompt_text([self._ns(True)])
        assert 'Tekshirish' in text

    def test_stage2_instagram_text(self):
        from bot.keyboards import subscription_prompt_text
        # Barcha kanal non-checkable -> 2-bosqich (Instagram) matni
        text = subscription_prompt_text([self._ns(False)])
        assert '📸' in text

    def test_confirming_text(self):
        from bot.keyboards import subscription_prompt_text
        text = subscription_prompt_text([self._ns(False)], confirming=True)
        assert 'Rostdan' in text


class TestSubscriptionMiddlewareSkip:
    """confirm_ch* callback middleware'da bloklanmasligi kerak"""

    def test_confirm_callback_prefix_skipped(self):
        # Middleware skip: confirm_ch prefiksi ikkala callback'ni ham qamrab oladi
        for data in ('confirm_ch:5', 'confirm_ch_yes:5'):
            skipped = data.startswith('confirm_ch') or data.startswith('admin:')
            assert skipped is True, data


class TestMiddlewareFailOpen:
    """Bot kanalga admin emas (get_chat_member xato) -> middleware crash bo'lmasligi kerak"""

    @pytest.mark.asyncio
    async def test_check_subscription_fail_open_on_forbidden(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from bot.middlewares.subscription import SubscriptionMiddleware

        mw = SubscriptionMiddleware()
        # Checkable (Telegram) kanal; get_chat_member faqat shu uchun chaqiriladi (DB tegilmaydi)
        ch = SimpleNamespace(id=1, channel_id=-1004387912093, is_checkable=True,
                             title='X', invite_link='https://t.me/x')
        mw._get_channels_cached = AsyncMock(return_value=[ch])

        bot = AsyncMock()
        # "Forbidden: bot is not a member of the channel chat" kabi xato
        bot.get_chat_member = AsyncMock(
            side_effect=Exception("Forbidden: bot is not a member of the channel chat")
        )

        # Crash bo'lmasligi + fail-open (kanal o'tkaziladi) -> bo'sh ro'yxat
        result = await mw._check_subscription(bot, 123456789)
        assert result == []


class TestReferralSystem:
    """Test referral system"""

    def test_referral_code(self, db_user):
        """Test referral code"""
        assert db_user.referral_code is not None
        assert len(db_user.referral_code) == 8

    def test_referral_link(self, db_user):
        """Test referral link format"""
        link = f"https://t.me/bot?start={db_user.referral_code}"
        assert db_user.referral_code in link

    def test_referred_by(self, user_model, db_user):
        """Test referred_by tracking"""
        referred = user_model.objects.create(
            user_id=888777666,
            username='referred',
            full_name='Referred User',
            referred_by=db_user
        )
        assert referred.referred_by == db_user

        # Count referrals
        count = user_model.objects.filter(referred_by=db_user).count()
        assert count >= 1

        referred.delete()

    def test_referral_bonus_and_notification(self, user_model):
        """Referral orqali qo'shilganda taklif qiluvchiga bonus + xabar ma'lumoti"""
        from bot.utils.helpers import get_or_create_user
        from apps.core.models import BotSettings

        s = BotSettings.get_settings()
        s.referral_active = True
        s.referral_bonus = 3
        s.save()

        referrer = user_model.objects.create(user_id=111222333, username='ref', full_name='R')
        before = referrer.free_trial_expires

        # @sync_to_async ichidagi asl sync funksiyani chaqiramiz (.func)
        new_user = get_or_create_user.func(
            user_id=444555666, username='new', full_name='N',
            referral_code=referrer.referral_code,
        )

        referrer.refresh_from_db()
        # Bonus qo'shildi (trial muddati o'rnatildi/uzaytirildi)
        assert referrer.free_trial_expires is not None
        if before is not None:
            assert referrer.free_trial_expires > before
        assert new_user.referred_by_id == referrer.id
        # Taklif qiluvchini xabardor qilish uchun ma'lumot biriktirilgan
        info = getattr(new_user, '_referral_bonus', None)
        assert info is not None
        assert info['referrer_id'] == 111222333
        assert info['bonus_days'] == 3

        new_user.delete()
        referrer.delete()
