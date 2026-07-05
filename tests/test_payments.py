"""
Payment Tests for KinoBot
"""
import pytest
from datetime import timedelta
from django.utils import timezone

pytestmark = pytest.mark.django_db


class TestTariffModel:
    """Test Tariff model"""

    def test_tariff_creation(self, db_tariff):
        """Test tariff is created"""
        assert db_tariff.name == 'Test Tariff'
        assert db_tariff.days == 30
        assert db_tariff.price == 10000

    def test_discounted_price(self, db_tariff):
        """Test discounted price"""
        assert db_tariff.discounted_price == 5000
        assert db_tariff.discounted_price < db_tariff.price

    def test_active_tariffs(self, tariff_model, db_tariff):
        """Test active tariffs"""
        count = tariff_model.objects.filter(is_active=True).count()
        assert count >= 1


class TestPaymentModel:
    """Test Payment model"""

    def test_payment_creation(self, payment_model, db_user, db_tariff):
        """Test payment creation"""
        payment = payment_model.objects.create(
            user=db_user,
            tariff=db_tariff,
            amount=db_tariff.price,
            status='pending',
            screenshot_file_id='test_screenshot'
        )
        assert payment.status == 'pending'
        assert payment.amount == 10000
        payment.delete()

    def test_payment_statuses(self):
        """Test payment statuses"""
        statuses = ['pending', 'approved', 'rejected', 'expired']
        assert 'pending' in statuses
        assert 'approved' in statuses

    def test_discounted_payment(self, payment_model, db_user, db_tariff):
        """Test payment with discount"""
        payment = payment_model.objects.create(
            user=db_user,
            tariff=db_tariff,
            amount=db_tariff.discounted_price,
            is_discounted=True,
            status='pending',
            screenshot_file_id='test'
        )
        assert payment.is_discounted is True
        assert payment.amount == 5000
        payment.delete()


class TestPaymentApproval:
    """Test payment approval"""

    def test_approve_payment(self, payment_model, db_user, db_tariff):
        """Test approve payment"""
        payment = payment_model.objects.create(
            user=db_user,
            tariff=db_tariff,
            amount=db_tariff.price,
            status='pending',
            screenshot_file_id='test'
        )
        payment.status = 'approved'
        payment.approved_at = timezone.now()
        payment.save()
        payment.refresh_from_db()
        assert payment.status == 'approved'
        payment.delete()

    def test_reject_payment(self, payment_model, db_user, db_tariff):
        """Test reject payment"""
        payment = payment_model.objects.create(
            user=db_user,
            tariff=db_tariff,
            amount=db_tariff.price,
            status='pending',
            screenshot_file_id='test'
        )
        payment.status = 'rejected'
        payment.save()
        payment.refresh_from_db()
        assert payment.status == 'rejected'
        payment.delete()

    def test_activate_premium(self, db_user, db_tariff):
        """Test premium activation"""
        db_user.is_premium = True
        db_user.premium_expires = timezone.now() + timedelta(days=db_tariff.days)
        db_user.save()
        db_user.refresh_from_db()
        assert db_user.is_premium_active is True
        # Cleanup
        db_user.is_premium = False
        db_user.save()


class TestFlashSale:
    """Test flash sale"""

    def test_flash_sale_trigger(self, user_model):
        """Test flash sale trigger"""
        user = user_model(user_id=111, premium_first_view=None)
        user.premium_first_view = timezone.now()
        assert user.premium_first_view is not None

    def test_flash_sale_active(self, user_model):
        """Test flash sale is active"""
        user = user_model(
            user_id=222,
            premium_first_view=timezone.now()
        )
        assert user.is_flash_sale_active is True

    def test_flash_sale_expired(self, user_model):
        """Test flash sale expired"""
        user = user_model(
            user_id=333,
            premium_first_view=timezone.now() - timedelta(minutes=10)
        )
        assert user.is_flash_sale_active is False

    def test_flash_sale_price_not_doubled(self, db_tariff):
        """Flash sale tugagach ham narx OSHMASLIGI kerak (2x olib tashlandi)"""
        from bot.keyboards import flash_sale_tariffs_kb

        # is_discount=False -> flash sale tugagan/o'chiq holat
        kb = flash_sale_tariffs_kb([db_tariff], is_discount=False)
        joined = " ".join(b.text for row in kb.inline_keyboard for b in row)

        # Narx = qo'yilgan narx (10,000), 2x (20,000) EMAS
        assert f"{db_tariff.price:,}" in joined
        assert f"{db_tariff.price * 2:,}" not in joined

    def test_flash_sale_active_price_not_doubled(self, db_tariff):
        """Flash sale aktiv holatda ham narx qo'yilgan narx"""
        from bot.keyboards import flash_sale_tariffs_kb

        kb = flash_sale_tariffs_kb([db_tariff], is_discount=True)
        joined = " ".join(b.text for row in kb.inline_keyboard for b in row)

        assert f"{db_tariff.price:,}" in joined
        assert f"{db_tariff.price * 2:,}" not in joined


class TestPaymentFlow:
    """Test complete payment flow"""

    def test_complete_flow(self, db_user, db_tariff, payment_model):
        """Test complete payment flow"""
        # Create payment
        payment = payment_model.objects.create(
            user=db_user,
            tariff=db_tariff,
            amount=db_tariff.price,
            status='pending',
            screenshot_file_id='flow_test'
        )
        assert payment.status == 'pending'

        # Approve
        payment.status = 'approved'
        payment.approved_at = timezone.now()
        payment.save()

        # Activate premium
        db_user.is_premium = True
        db_user.premium_expires = timezone.now() + timedelta(days=db_tariff.days)
        db_user.save()

        # Verify
        db_user.refresh_from_db()
        assert db_user.is_premium_active is True
        assert payment.status == 'approved'

        # Cleanup
        payment.delete()
        db_user.is_premium = False
        db_user.save()

    def test_extend_premium(self, db_premium_user, db_tariff):
        """Test extending premium"""
        initial = db_premium_user.premium_expires
        db_premium_user.premium_expires = initial + timedelta(days=db_tariff.days)
        db_premium_user.save()
        db_premium_user.refresh_from_db()
        assert db_premium_user.premium_expires > initial
