"""
Trial-tugash flash push scheduler testlari
"""
import pytest
from datetime import timedelta
from django.utils import timezone

pytestmark = pytest.mark.django_db


class TestTrialFlashScheduler:
    """bot.utils.scheduler trial flash helperlari"""

    def _make_user(self, user_model, uid, **kwargs):
        # save() yangi userga avtomatik trial beradi; biz uni aniq qiymat bilan
        # ustidan yozamiz.
        user = user_model.objects.create(user_id=uid, full_name=f'U{uid}')
        for k, v in kwargs.items():
            setattr(user, k, v)
        user.save()
        return user

    def test_recently_expired_trial_is_selected(self, user_model):
        from bot.utils.scheduler import get_trial_expiring_users
        self._make_user(
            user_model, 80001,
            free_trial_expires=timezone.now() - timedelta(hours=2),
            is_premium=False, trial_flash_sent=False,
        )
        ids = [u.user_id for u in get_trial_expiring_users.func()]
        assert 80001 in ids

    def test_old_expired_trial_not_selected(self, user_model):
        """24 soatdan oldin tugagan trial ommaviy push OLMAYDI"""
        from bot.utils.scheduler import get_trial_expiring_users
        self._make_user(
            user_model, 80002,
            free_trial_expires=timezone.now() - timedelta(days=3),
            is_premium=False, trial_flash_sent=False,
        )
        ids = [u.user_id for u in get_trial_expiring_users.func()]
        assert 80002 not in ids

    def test_already_notified_not_selected(self, user_model):
        from bot.utils.scheduler import get_trial_expiring_users
        self._make_user(
            user_model, 80003,
            free_trial_expires=timezone.now() - timedelta(hours=1),
            is_premium=False, trial_flash_sent=True,
        )
        ids = [u.user_id for u in get_trial_expiring_users.func()]
        assert 80003 not in ids

    def test_premium_user_not_selected(self, user_model):
        from bot.utils.scheduler import get_trial_expiring_users
        self._make_user(
            user_model, 80004,
            free_trial_expires=timezone.now() - timedelta(hours=1),
            is_premium=True,
            premium_expires=timezone.now() + timedelta(days=10),
            trial_flash_sent=False,
        )
        ids = [u.user_id for u in get_trial_expiring_users.func()]
        assert 80004 not in ids

    def test_active_trial_not_selected(self, user_model):
        """Hali tugamagan trial push OLMAYDI"""
        from bot.utils.scheduler import get_trial_expiring_users
        self._make_user(
            user_model, 80005,
            free_trial_expires=timezone.now() + timedelta(days=2),
            is_premium=False, trial_flash_sent=False,
        )
        ids = [u.user_id for u in get_trial_expiring_users.func()]
        assert 80005 not in ids

    def test_start_trial_flash_sale_sets_window_and_flag(self, user_model):
        from bot.utils.scheduler import start_trial_flash_sale
        self._make_user(
            user_model, 80006,
            free_trial_expires=timezone.now() - timedelta(hours=1),
            is_premium=False, trial_flash_sent=False,
            flash_sale_started=None,
        )
        start_trial_flash_sale.func(80006)

        user = user_model.objects.get(user_id=80006)
        assert user.trial_flash_sent is True
        assert user.flash_sale_started is not None
        assert user.is_flash_sale_active is True
