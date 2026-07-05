"""
Admin: userga premium berish / olib qo'yish testlari
"""
import pytest
from datetime import timedelta
from django.utils import timezone

pytestmark = pytest.mark.django_db


class TestGiveUserPremium:
    """bot.handlers.admin.give_user_premium"""

    def test_give_days(self, user_model):
        from bot.handlers.admin import give_user_premium
        user_model.objects.create(user_id=90001, full_name='U1')

        assert give_user_premium.func(90001, 30) is True
        u = user_model.objects.get(user_id=90001)
        assert u.is_premium is True
        assert u.premium_expires is not None
        assert u.is_premium_active is True
        # ~30 kun
        assert 28 <= (u.premium_expires - timezone.now()).days <= 30

    def test_give_indefinite(self, user_model):
        """days=0 -> muddatsiz premium (premium_expires=None, lekin aktiv)"""
        from bot.handlers.admin import give_user_premium
        user_model.objects.create(user_id=90002, full_name='U2')

        assert give_user_premium.func(90002, 0) is True
        u = user_model.objects.get(user_id=90002)
        assert u.is_premium is True
        assert u.premium_expires is None
        assert u.is_premium_active is True

    def test_give_extends_existing(self, user_model):
        from bot.handlers.admin import give_user_premium
        user_model.objects.create(
            user_id=90003, full_name='U3',
            is_premium=True, premium_expires=timezone.now() + timedelta(days=10),
        )
        give_user_premium.func(90003, 30)
        u = user_model.objects.get(user_id=90003)
        # 10 + 30 ~ 40 kun
        assert 38 <= (u.premium_expires - timezone.now()).days <= 40

    def test_give_missing_user(self, user_model):
        from bot.handlers.admin import give_user_premium
        assert give_user_premium.func(90999, 30) is False


class TestRemoveUserPremium:
    """bot.handlers.admin.remove_user_premium"""

    def test_remove(self, user_model):
        from bot.handlers.admin import remove_user_premium
        user_model.objects.create(
            user_id=90010, full_name='P',
            is_premium=True, premium_expires=timezone.now() + timedelta(days=30),
        )
        assert remove_user_premium.func(90010) is True
        u = user_model.objects.get(user_id=90010)
        assert u.is_premium is False
        assert u.premium_expires is None
        assert u.is_premium_active is False

    def test_remove_indefinite(self, user_model):
        """Muddatsiz premiumни ham olib qo'yish"""
        from bot.handlers.admin import remove_user_premium
        user_model.objects.create(
            user_id=90011, full_name='P2',
            is_premium=True, premium_expires=None,
        )
        assert remove_user_premium.func(90011) is True
        u = user_model.objects.get(user_id=90011)
        assert u.is_premium_active is False

    def test_remove_missing_user(self, user_model):
        from bot.handlers.admin import remove_user_premium
        assert remove_user_premium.func(90999) is False
