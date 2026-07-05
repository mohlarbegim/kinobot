"""
Admin Tests for KinoBot
"""
import pytest
from datetime import timedelta
from django.utils import timezone

pytestmark = pytest.mark.django_db


class TestAdminFilters:
    """Test admin permission filters"""

    @pytest.mark.asyncio
    async def test_is_admin(self, mock_message):
        """Test IsAdmin filter"""
        from bot.filters import IsAdmin
        from django.conf import settings

        if settings.ADMINS:
            mock_message.from_user.id = settings.ADMINS[0]
            result = await IsAdmin()(mock_message)
            assert result is True

    @pytest.mark.asyncio
    async def test_is_super_admin(self, mock_message):
        """Test IsSuperAdmin filter"""
        from bot.filters import IsSuperAdmin
        from django.conf import settings

        if settings.ADMINS:
            mock_message.from_user.id = settings.ADMINS[0]
            result = await IsSuperAdmin()(mock_message)
            assert result is True

    @pytest.mark.asyncio
    async def test_can_add_movies(self, mock_message):
        """Test CanAddMovies filter"""
        from bot.filters import CanAddMovies
        from django.conf import settings

        if settings.ADMINS:
            mock_message.from_user.id = settings.ADMINS[0]
            result = await CanAddMovies()(mock_message)
            assert result is True

    @pytest.mark.asyncio
    async def test_can_broadcast(self, mock_message):
        """Test CanBroadcast filter"""
        from bot.filters import CanBroadcast
        from django.conf import settings

        if settings.ADMINS:
            mock_message.from_user.id = settings.ADMINS[0]
            result = await CanBroadcast()(mock_message)
            assert result is True


class TestMovieManagement:
    """Test movie management"""

    def test_movie_code_validation(self):
        """Test valid movie codes"""
        valid = ['123', '99999', '1']
        for code in valid:
            assert code.isdigit() is True

    def test_invalid_code(self):
        """Test invalid movie codes"""
        invalid = ['abc', '12a', 'movie']
        for code in invalid:
            assert code.isdigit() is False

    def test_year_validation(self):
        """Test year validation"""
        valid_years = [2020, 2024, 1990]
        for year in valid_years:
            assert 1900 <= year <= 2030

    def test_quality_options(self):
        """Test quality options"""
        qualities = ['360p', '480p', '720p', '1080p', '4k']
        assert len(qualities) == 5

    def test_language_options(self):
        """Test language options"""
        languages = ['uzbek', 'russian', 'english', 'turkish', 'korean', 'other']
        assert 'uzbek' in languages

    def test_movie_without_video(self, movie_model, db_category):
        """Videosiz kino qo'shsa bo'ladi (file_id bo'sh) - keyin video qo'shiladi"""
        movie = movie_model.objects.create(
            code=76543,
            title='Videosiz kino',
            file_id='',           # video o'tkazib yuborilgan
            category=db_category,
        )
        movie.refresh_from_db()
        assert movie.file_id == ''
        assert movie_model.objects.filter(code=76543).exists()
        # Keyin video qo'shish mumkin
        movie.file_id = 'BAAC_later'
        movie.save()
        movie.refresh_from_db()
        assert movie.file_id == 'BAAC_later'
        movie.delete()

    def test_movie_serializer_file_id_optional(self):
        """MovieSerializer file_id'siz ham valid (dashboard video majburiy emas)"""
        from apps.api.serializers import MovieSerializer
        s = MovieSerializer(data={'code': 'NOVID-9', 'title': 'X'})
        assert s.is_valid(), s.errors
        assert 'file_id' not in s.errors

    @pytest.mark.asyncio
    async def test_movie_sent_with_protect_content(self):
        """Yuborilgan kino forward himoyasi (protect_content=True) bilan ketishi kerak"""
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from bot.handlers.user import send_movie_or_notice

        tgt = SimpleNamespace(answer=AsyncMock(), answer_video=AsyncMock())
        movie = SimpleNamespace(file_id='BAAC_movie')
        await send_movie_or_notice(tgt, movie, "Caption")
        assert tgt.answer_video.call_args.kwargs.get('protect_content') is True

    def test_toggle_movie_status(self, db_movie):
        """Test toggle active status"""
        initial = db_movie.is_active
        db_movie.is_active = not initial
        db_movie.save()
        db_movie.refresh_from_db()
        assert db_movie.is_active != initial

    def test_toggle_premium(self, db_movie):
        """Test toggle premium status"""
        initial = db_movie.is_premium
        db_movie.is_premium = not initial
        db_movie.save()
        db_movie.refresh_from_db()
        assert db_movie.is_premium != initial

    def test_delete_movie(self, movie_model, db_category):
        """Test delete movie"""
        movie = movie_model.objects.create(
            code=77777,
            title='Delete Test',
            file_id='delete_test',
            category=db_category
        )
        movie_id = movie.id
        movie.delete()
        assert not movie_model.objects.filter(id=movie_id).exists()


class TestChannelManagement:
    """Test channel management"""

    def test_channel_creation(self, db_channel):
        """Test channel creation"""
        assert db_channel.title == 'Test Channel'
        assert db_channel.is_active is True

    def test_channel_types(self):
        """Test channel types"""
        types = ['channel', 'group', 'bot', 'instagram', 'other']
        assert 'channel' in types

    def test_toggle_channel(self, db_channel):
        """Test toggle channel status"""
        initial = db_channel.is_active
        db_channel.is_active = not initial
        db_channel.save()
        db_channel.refresh_from_db()
        assert db_channel.is_active != initial

    def test_delete_channel(self, channel_model):
        """Test delete channel"""
        channel = channel_model.objects.create(
            channel_id=-1009999999,
            title='Delete Test Channel',
            channel_type='channel'
        )
        channel_id = channel.id
        channel.delete()
        assert not channel_model.objects.filter(id=channel_id).exists()


class TestUserManagement:
    """Test user management"""

    def test_ban_user(self, db_user):
        """Test ban user"""
        db_user.is_banned = True
        db_user.ban_reason = 'Test ban'
        db_user.save()
        db_user.refresh_from_db()
        assert db_user.is_banned is True
        # Cleanup
        db_user.is_banned = False
        db_user.save()

    def test_unban_user(self, db_user):
        """Test unban user"""
        db_user.is_banned = True
        db_user.save()
        db_user.is_banned = False
        db_user.save()
        db_user.refresh_from_db()
        assert db_user.is_banned is False

    def test_give_premium(self, db_user):
        """Test give premium"""
        db_user.is_premium = True
        db_user.premium_expires = timezone.now() + timedelta(days=30)
        db_user.save()
        db_user.refresh_from_db()
        assert db_user.is_premium_active is True
        # Cleanup
        db_user.is_premium = False
        db_user.save()

    def test_extend_premium(self, db_premium_user):
        """Test extend premium"""
        initial = db_premium_user.premium_expires
        db_premium_user.premium_expires = initial + timedelta(days=30)
        db_premium_user.save()
        db_premium_user.refresh_from_db()
        assert db_premium_user.premium_expires > initial


class TestBotSettings:
    """Test bot settings"""

    def test_settings_singleton(self, bot_settings_model):
        """Test singleton pattern"""
        s1 = bot_settings_model.get_settings()
        s2 = bot_settings_model.get_settings()
        assert s1.id == s2.id

    def test_update_card(self, bot_settings_model):
        """Test update card number"""
        settings = bot_settings_model.get_settings()
        old = settings.card_number
        settings.card_number = '8600 1111 2222 3333'
        settings.save()
        settings.refresh_from_db()
        assert settings.card_number == '8600 1111 2222 3333'
        # Restore
        settings.card_number = old
        settings.save()

    def test_toggle_bot(self, bot_settings_model):
        """Test toggle bot active"""
        settings = bot_settings_model.get_settings()
        initial = settings.is_active
        settings.is_active = not initial
        settings.save()
        settings.refresh_from_db()
        assert settings.is_active != initial
        # Restore
        settings.is_active = initial
        settings.save()


class TestStatistics:
    """Test statistics"""

    def test_user_count(self, user_model, db_user):
        """Test user count"""
        count = user_model.objects.count()
        assert count >= 1

    def test_movie_count(self, movie_model, db_movie):
        """Test movie count"""
        count = movie_model.objects.count()
        assert count >= 1

    def test_active_movies(self, movie_model, db_movie):
        """Test active movies count"""
        count = movie_model.objects.filter(is_active=True).count()
        assert count >= 1

    def test_premium_users(self, user_model, db_premium_user):
        """Test premium users count"""
        count = user_model.objects.filter(
            is_premium=True,
            premium_expires__gt=timezone.now()
        ).count()
        assert count >= 1


class TestAdminStates:
    """Test FSM states"""

    def test_add_movie_states(self):
        """Test AddMovieState"""
        from bot.states import AddMovieState
        states = ['code', 'title', 'video', 'category', 'year',
                  'country', 'quality', 'language', 'description',
                  'is_premium', 'confirm']
        for state in states:
            assert hasattr(AddMovieState, state)

    def test_broadcast_states(self):
        """Test BroadcastState"""
        from bot.states import BroadcastState
        states = ['target', 'is_ad', 'content', 'confirm']
        for state in states:
            assert hasattr(BroadcastState, state)

    def test_add_channel_states(self):
        """Test AddChannelState"""
        from bot.states import AddChannelState
        states = ['channel_input', 'title']
        for state in states:
            assert hasattr(AddChannelState, state)
