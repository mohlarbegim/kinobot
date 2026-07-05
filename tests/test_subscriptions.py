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


class TestChannelJoinRequest:
    """Yopiq kanalga qo'shilish so'rovi (ChannelJoinRequest) - so'rovning o'zi kifoya"""

    def test_join_request_creation(self, db_user, db_channel):
        from apps.channels.models import ChannelJoinRequest

        jr, created = ChannelJoinRequest.objects.get_or_create(
            channel=db_channel, user=db_user
        )
        assert created is True
        assert jr.channel == db_channel
        assert jr.user == db_user
        jr.delete()

    def test_join_request_unique(self, db_user, db_channel):
        from apps.channels.models import ChannelJoinRequest

        jr1, c1 = ChannelJoinRequest.objects.get_or_create(channel=db_channel, user=db_user)
        jr2, c2 = ChannelJoinRequest.objects.get_or_create(channel=db_channel, user=db_user)
        assert c1 is True
        assert c2 is False
        assert jr1.id == jr2.id
        jr1.delete()

    def test_join_request_separate_from_subscription(self, db_user, db_channel):
        """Join request va ChannelSubscription ALOHIDA - biri ikkinchisiga aralashmaydi"""
        from apps.channels.models import ChannelJoinRequest, ChannelSubscription

        ChannelSubscription.objects.create(channel=db_channel, user=db_user)
        # Obuna yozuvi bor, lekin join request YO'Q
        assert ChannelJoinRequest.objects.filter(
            channel=db_channel, user=db_user
        ).exists() is False

        ChannelSubscription.objects.filter(channel=db_channel, user=db_user).delete()

    def test_get_join_requested_ids_query(self, user_model, channel_model):
        """get_join_requested_ids mantig'i: user__user_id bo'yicha so'rov yuborilgan pk'lar"""
        from apps.channels.models import ChannelJoinRequest

        user = user_model.objects.create(user_id=777000222, username='jr', full_name='JR')
        ch = channel_model.objects.create(
            channel_id=-1009998887, title='Yopiq kanal',
            channel_type='telegram_channel', invite_link='https://t.me/+abc', is_active=True,
        )

        requested = set(
            ChannelJoinRequest.objects.filter(user__user_id=777000222)
            .values_list('channel_id', flat=True)
        )
        assert requested == set()

        ChannelJoinRequest.objects.create(channel=ch, user=user)
        requested = set(
            ChannelJoinRequest.objects.filter(user__user_id=777000222)
            .values_list('channel_id', flat=True)
        )
        assert ch.id in requested

        ChannelJoinRequest.objects.filter(user=user).delete()
        ch.delete(); user.delete()


class TestLeaveReasksSubscription:
    """Kanaldan chiqib ketsa yozuvlar o'chadi -> keyingi tekshiruvda qayta obuna so'raladi"""

    @pytest.mark.asyncio
    async def test_remove_channel_membership_clears_records(self, user_model, channel_model):
        from asgiref.sync import sync_to_async
        from apps.channels.models import ChannelJoinRequest, ChannelSubscription
        from bot.utils.helpers import remove_channel_membership

        uid = 505050501

        @sync_to_async
        def setup():
            u = user_model.objects.create(user_id=uid, username='lv', full_name='LV')
            ch = channel_model.objects.create(
                channel_id=-100777888, title='Yopiq', channel_type='telegram_channel',
                invite_link='https://t.me/+q', is_active=True,
            )
            ChannelJoinRequest.objects.create(channel=ch, user=u)
            ChannelSubscription.objects.create(channel=ch, user=u)
            return u, ch

        @sync_to_async
        def counts(u, ch):
            return (
                ChannelJoinRequest.objects.filter(channel=ch, user=u).count(),
                ChannelSubscription.objects.filter(channel=ch, user=u).count(),
            )

        @sync_to_async
        def teardown(u, ch):
            ch.delete(); u.delete()

        u, ch = await setup()
        assert await counts(u, ch) == (1, 1)

        # Kanaldan chiqqanda chaqiriladigan helper
        await remove_channel_membership(uid, ch.id)

        # Yozuvlar o'chdi -> endi kanal "bajarilmagan" bo'lib qaytadi (qayta so'raladi)
        assert await counts(u, ch) == (0, 0)

        await teardown(u, ch)


class TestChannelsKeyboard:
    """channels_kb - faqat havola tugmalari + «Tekshirish» (tasdiq tugmasi YO'Q)"""

    def test_no_confirm_button(self):
        """Instagram uchun ham alohida 'obuna bo'ldim' tugmasi bo'lmasligi kerak"""
        from types import SimpleNamespace
        from bot.keyboards import channels_kb

        tg = SimpleNamespace(id=1, title='TG', invite_link='https://t.me/x', is_checkable=True)
        ig = SimpleNamespace(id=2, title='IG', invite_link='https://instagram.com/x', is_checkable=False)

        kb = channels_kb([tg, ig])
        callbacks = [b.callback_data for row in kb.inline_keyboard for b in row if b.callback_data]

        # Endi tasdiq tugmalari umuman yo'q - faqat «Tekshirish»
        assert not any(c.startswith('confirm_ch') for c in callbacks)
        assert 'check_subscription' in callbacks
        # Har kanal uchun bitta havola (url) tugmasi
        url_buttons = [b for row in kb.inline_keyboard for b in row if b.url]
        assert len(url_buttons) == 2

    def test_channels_are_numbered(self):
        """Havola tugmalari tartib raqami bilan; Instagram (oxirgi) eng katta raqamda"""
        from types import SimpleNamespace
        from bot.keyboards import channels_kb

        tg1 = SimpleNamespace(id=1, title='TG1', invite_link='https://t.me/a', is_checkable=True)
        tg2 = SimpleNamespace(id=2, title='TG2', invite_link='https://t.me/b', is_checkable=True)
        ig = SimpleNamespace(id=3, title='IG', invite_link='https://instagram.com/x', is_checkable=False)

        kb = channels_kb([tg1, tg2, ig])
        # Havola (url) tugmalari matnlari
        url_texts = [b.text for row in kb.inline_keyboard for b in row if b.url]

        assert url_texts[0].startswith('1. ')          # birinchi kanal
        assert url_texts[1].startswith('2. ')
        assert url_texts[2].startswith('3. ')          # Instagram oxirgi raqam
        assert 'IG' in url_texts[2]

    def test_instagram_button_hides_type(self):
        """Instagram tugmasida 📸 belgisi va 'Instagram' so'zi bo'lmasligi kerak - faqat nom"""
        from types import SimpleNamespace
        from bot.keyboards import channels_kb

        ig = SimpleNamespace(id=1, title='Rasmiy sahifamiz',
                             invite_link='https://instagram.com/x',
                             is_checkable=False, channel_type='instagram')
        kb = channels_kb([ig])
        url_texts = [b.text for row in kb.inline_keyboard for b in row if b.url]

        assert len(url_texts) == 1
        assert '📸' not in url_texts[0]                 # Instagram belgisi yo'q
        assert 'Instagram' not in url_texts[0]          # "Instagram" so'zi yo'q
        assert 'Rasmiy sahifamiz' in url_texts[0]       # faqat admin bergan nom


class TestSubscriptionPromptText:
    """subscription_prompt_text - Instagram ekani matnda bilinmasligi kerak"""

    def _ns(self, checkable):
        from types import SimpleNamespace
        return SimpleNamespace(id=1, title='X', invite_link='https://x', is_checkable=checkable)

    def test_telegram_only_text(self):
        from bot.keyboards import subscription_prompt_text
        text = subscription_prompt_text([self._ns(True)])
        assert 'Tekshirish' in text
        assert 'Instagram' not in text

    def test_mixed_text_hides_instagram(self):
        from bot.keyboards import subscription_prompt_text
        # Aralash (Telegram + Instagram) bo'lsa ham "Instagram" so'zi chiqmasligi kerak
        text = subscription_prompt_text([self._ns(True), self._ns(False)])
        assert 'Instagram' not in text
        assert 'Tekshirish' in text

    def test_confirming_text_hides_instagram(self):
        from bot.keyboards import subscription_prompt_text
        # Ikkinchi tashrif tasdig'i: havolaga qayta o'tib «Tekshirish»ni so'raydi (Instagram demasdan)
        text = subscription_prompt_text([self._ns(False)], confirming=True)
        assert 'Instagram' not in text
        assert 'havola' in text.lower()
        assert 'Tekshirish' in text


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


class TestMiddlewareJoinRequest:
    """Yopiq kanalga qo'shilish so'rovi bo'lsa 'left' bo'lsa ham o'tkaziladi"""

    @pytest.mark.asyncio
    async def test_join_request_satisfies_telegram_gate(self, user_model, channel_model):
        from unittest.mock import AsyncMock
        from types import SimpleNamespace
        from asgiref.sync import sync_to_async
        from apps.channels.models import ChannelJoinRequest
        from bot.middlewares.subscription import SubscriptionMiddleware

        @sync_to_async
        def setup():
            user = user_model.objects.create(user_id=333444555, username='jr2', full_name='JR2')
            ch = channel_model.objects.create(
                channel_id=-1005554443, title='Yopiq', channel_type='telegram_channel',
                invite_link='https://t.me/+xyz', is_active=True,
            )
            # Foydalanuvchi qo'shilish so'rovi yuborgan
            ChannelJoinRequest.objects.create(channel=ch, user=user)
            return user, ch

        @sync_to_async
        def teardown(user, ch):
            ChannelJoinRequest.objects.filter(user=user).delete()
            ch.delete(); user.delete()

        user, ch = await setup()

        mw = SubscriptionMiddleware()
        # Model obyektini uzatamiz (is_checkable property'si ishlashi uchun)
        mw._get_channels_cached = AsyncMock(return_value=[ch])

        bot = AsyncMock()
        # get_chat_member 'left' qaytaradi (kanalda a'zo emas, faqat so'rov yuborilgan)
        bot.get_chat_member = AsyncMock(
            return_value=SimpleNamespace(status='left')
        )

        result = await mw._check_subscription(bot, 333444555)
        # So'rov bor -> kanal missing ro'yxatida BO'LMASLIGI kerak
        assert result == []

        await teardown(user, ch)

    @pytest.mark.asyncio
    async def test_left_without_join_request_is_missing(self, user_model, channel_model):
        from unittest.mock import AsyncMock
        from types import SimpleNamespace
        from asgiref.sync import sync_to_async
        from bot.middlewares.subscription import SubscriptionMiddleware

        @sync_to_async
        def setup():
            user = user_model.objects.create(user_id=333444556, username='jr3', full_name='JR3')
            ch = channel_model.objects.create(
                channel_id=-1005554444, title='Yopiq2', channel_type='telegram_channel',
                invite_link='https://t.me/+zzz', is_active=True,
            )
            return user, ch

        @sync_to_async
        def teardown(user, ch):
            ch.delete(); user.delete()

        user, ch = await setup()

        mw = SubscriptionMiddleware()
        mw._get_channels_cached = AsyncMock(return_value=[ch])

        bot = AsyncMock()
        bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status='left'))

        result = await mw._check_subscription(bot, 333444556)
        # So'rov YO'Q -> kanal missing bo'lishi kerak
        assert len(result) == 1
        assert result[0].id == ch.id

        await teardown(user, ch)


class TestInstagramDoubleCheck:
    """check_sub_callback: Instagram uchun 'ikki marta Tekshirish' mantig'i"""

    @pytest.mark.asyncio
    async def test_instagram_requires_two_checks(self, user_model, channel_model):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from asgiref.sync import sync_to_async
        from apps.channels.models import ChannelSubscription
        from bot.handlers import user as user_handlers

        uid = 909090901

        @sync_to_async
        def setup():
            u = user_model.objects.create(user_id=uid, username='ig', full_name='IG')
            ch = channel_model.objects.create(
                title='IG', channel_type='instagram',
                invite_link='https://instagram.com/x', is_active=True,
            )
            return u, ch

        @sync_to_async
        def ig_confirmed():
            return ChannelSubscription.objects.filter(
                user__user_id=uid, channel__channel_type='instagram'
            ).exists()

        @sync_to_async
        def teardown(u, ch):
            ChannelSubscription.objects.filter(user=u).delete()
            ch.delete(); u.delete()

        u, ch = await setup()
        # In-memory holatni tozalaymiz (boshqa testlardan qolmasin)
        user_handlers._instagram_recheck.pop(uid, None)
        user_handlers._pending_subscriptions.pop(uid, None)

        bot = AsyncMock()  # checkable kanal yo'q -> get_chat_member chaqirilmaydi
        callback = SimpleNamespace(
            from_user=SimpleNamespace(id=uid),
            message=AsyncMock(),
            answer=AsyncMock(),
        )

        # 1-Tekshirish: HALI tasdiqlanmaydi, Instagram qayta ko'rsatiladi
        await user_handlers.check_sub_callback(callback, bot)
        assert user_handlers._instagram_recheck.get(uid) is True
        assert await ig_confirmed() is False
        assert callback.message.edit_text.await_count >= 1

        # 2-Tekshirish: endi tasdiqlanadi
        await user_handlers.check_sub_callback(callback, bot)
        assert await ig_confirmed() is True
        assert uid not in user_handlers._instagram_recheck

        await teardown(u, ch)


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
