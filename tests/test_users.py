"""
User Tests for KinoBot
"""
import pytest
from datetime import timedelta
from django.utils import timezone

pytestmark = pytest.mark.django_db


class TestUserModel:
    """Test User model"""

    def test_user_creation(self, db_user):
        """Test user is created"""
        assert db_user.user_id == 123456789
        assert db_user.username == 'test_user'

    def test_referral_code_generated(self, db_user):
        """Test referral code is auto-generated"""
        assert db_user.referral_code is not None
        assert len(db_user.referral_code) == 8

    def test_is_premium_active_false(self, db_user):
        """Test non-premium user"""
        assert db_user.is_premium_active is False

    def test_is_premium_active_true(self, db_premium_user):
        """Test premium user"""
        assert db_premium_user.is_premium_active is True

    def test_premium_expired(self, user_model):
        """Test expired premium"""
        user = user_model(
            user_id=111,
            is_premium=True,
            premium_expires=timezone.now() - timedelta(days=1)
        )
        assert user.is_premium_active is False

    def test_trial_active(self, user_model):
        """Test active trial"""
        user = user_model(
            user_id=222,
            free_trial_expires=timezone.now() + timedelta(days=3)
        )
        assert user.is_trial_active is True

    def test_trial_expired(self, user_model):
        """Test expired trial"""
        user = user_model(
            user_id=333,
            free_trial_expires=timezone.now() - timedelta(days=1)
        )
        assert user.is_trial_active is False

    def test_can_watch_movies_premium(self, db_premium_user):
        """Test premium can watch"""
        assert db_premium_user.can_watch_movies is True

    def test_days_left(self, user_model):
        """Test days left calculation"""
        user = user_model(
            user_id=444,
            is_premium=True,
            premium_expires=timezone.now() + timedelta(days=15)
        )
        assert 14 <= user.days_left <= 15

    def test_flash_sale_active(self, user_model):
        """Flash sale oynasi ochiq (langar hozir o'rnatilgan)"""
        user = user_model(
            user_id=555,
            flash_sale_started=timezone.now()
        )
        assert user.is_flash_sale_active is True

    def test_flash_sale_expired(self, user_model):
        """Flash sale oynasi yopiq (langar 10 daqiqa oldin, muddat 30s)"""
        user = user_model(
            user_id=666,
            flash_sale_started=timezone.now() - timedelta(minutes=10)
        )
        assert user.is_flash_sale_active is False

    def test_flash_sale_inactive_without_trigger(self, user_model):
        """Trigger bo'lmagan (flash_sale_started=None) -> flash sale YO'Q"""
        user = user_model(user_id=557, flash_sale_started=None)
        assert user.is_flash_sale_active is False
        assert user.flash_sale_seconds_left == 0


class TestMovieModel:
    """Test Movie model"""

    def test_movie_creation(self, db_movie):
        """Test movie is created"""
        assert db_movie.code == 99999
        assert db_movie.title == 'Test Movie'
        assert db_movie.is_active is True

    def test_premium_movie(self, db_premium_movie):
        """Test premium movie"""
        assert db_premium_movie.is_premium is True

    def test_movie_views(self, db_movie):
        """Test views increment"""
        initial = db_movie.views
        db_movie.views += 1
        db_movie.save()
        db_movie.refresh_from_db()
        assert db_movie.views == initial + 1


class TestCategoryModel:
    """Test Category model"""

    def test_category_creation(self, db_category):
        """Test category is created"""
        assert db_category.name == 'Test Category'
        assert db_category.emoji == '🎬'
        assert db_category.is_active is True


class TestAdminFilter:
    """Test admin filters"""

    def test_admins_configured(self):
        """Test ADMINS is configured"""
        from django.conf import settings
        assert isinstance(settings.ADMINS, list)

    @pytest.mark.asyncio
    async def test_is_admin_true(self, mock_message):
        """Test admin filter returns True for admin"""
        from bot.filters import IsAdmin
        from django.conf import settings

        if settings.ADMINS:
            mock_message.from_user.id = settings.ADMINS[0]
            result = await IsAdmin()(mock_message)
            assert result is True

    @pytest.mark.asyncio
    async def test_is_admin_false(self, mock_message):
        """Test admin filter returns False for non-admin"""
        from bot.filters import IsAdmin

        mock_message.from_user.id = 999999999
        result = await IsAdmin()(mock_message)
        assert result is False


class TestKeyboards:
    """Test keyboards"""

    def test_main_menu_kb(self):
        """Test main menu keyboard"""
        from bot.keyboards import main_menu_inline_kb
        kb = main_menu_inline_kb()
        assert kb is not None
        assert hasattr(kb, 'inline_keyboard')

    def test_admin_main_kb(self):
        """Test admin keyboard"""
        from bot.keyboards import admin_main_kb
        kb = admin_main_kb()
        assert kb is not None


class TestUtilities:
    """Test utility functions"""

    def test_format_number(self):
        """Test number formatting"""
        from bot.utils import format_number
        assert format_number(1000) == '1 000'
        assert format_number(0) == '0'

    def test_format_number_large(self):
        """Test large number formatting"""
        from bot.utils import format_number
        result = format_number(1000000)
        assert '000' in result


class TestSavedMovies:
    """Test saved movies"""

    def test_save_movie(self, db_user, db_movie):
        """Test saving a movie"""
        from apps.movies.models import SavedMovie

        saved, created = SavedMovie.objects.get_or_create(
            user=db_user,
            movie=db_movie
        )
        assert created is True
        SavedMovie.objects.filter(user=db_user, movie=db_movie).delete()

    def test_unsave_movie(self, db_user, db_movie):
        """Test removing saved movie"""
        from apps.movies.models import SavedMovie

        SavedMovie.objects.get_or_create(user=db_user, movie=db_movie)
        count, _ = SavedMovie.objects.filter(user=db_user, movie=db_movie).delete()
        assert count >= 1


class TestMovieAccess:
    """Test movie access control"""

    def test_regular_user_regular_movie(self, db_user, db_movie):
        """Test user can access regular movie"""
        assert db_movie.is_premium is False

    def test_premium_movie_needs_premium(self, db_user, db_premium_movie):
        """Test premium movie requires premium"""
        assert db_premium_movie.is_premium is True
        assert db_user.is_premium is False

    def test_premium_user_access(self, db_premium_user, db_premium_movie):
        """Test premium user can access premium movie"""
        assert db_premium_user.is_premium_active is True
        assert db_premium_movie.is_premium is True
