from django.db import models
from django.utils import timezone


class Tariff(models.Model):
    """Premium tarif"""

    name = models.CharField(max_length=100, verbose_name='Nomi')
    days = models.PositiveIntegerField(verbose_name='Kunlar soni')
    price = models.PositiveIntegerField(verbose_name="Narxi (so'm)")
    discounted_price = models.PositiveIntegerField(blank=True, null=True, verbose_name="Chegirmali narx (so'm)")

    order = models.PositiveIntegerField(default=0, verbose_name='Tartib')
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')

    class Meta:
        verbose_name = 'Tarif'
        verbose_name_plural = 'Tariflar'
        ordering = ['order', 'days']

    def __str__(self):
        return f"{self.name} - {self.days} kun"

    @property
    def discount_percent(self):
        """Chegirma foizi"""
        # is not None -> discounted_price=0 (100% chegirma) ham to'g'ri hisoblanadi.
        if self.discounted_price is not None and self.price and self.discounted_price < self.price:
            return int((1 - self.discounted_price / self.price) * 100)
        return 0


class Payment(models.Model):
    """To'lov"""

    STATUS_CHOICES = [
        ('pending', 'Kutilmoqda'),
        ('approved', 'Tasdiqlangan'),
        ('rejected', 'Rad etilgan'),
        ('expired', 'Muddati tugagan'),
    ]

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Foydalanuvchi'
    )
    tariff = models.ForeignKey(
        Tariff,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='payments',
        verbose_name='Tarif'
    )

    amount = models.PositiveIntegerField(verbose_name="To'langan summa")
    is_discounted = models.BooleanField(default=False, verbose_name='Chegirma qo\'llandi')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='Holat')

    screenshot_file_id = models.CharField(max_length=255, verbose_name='Screenshot File ID')

    # Admin xabarlarini saqlash (xabarni o'chirish uchun)
    admin_messages = models.JSONField(blank=True, null=True, verbose_name='Admin xabarlari')

    admin_note = models.TextField(blank=True, default='', verbose_name='Admin izohi')
    approved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='approved_payments',
        verbose_name='Kim tasdiqladi'
    )
    approved_at = models.DateTimeField(blank=True, null=True, verbose_name='Tasdiqlangan vaqt')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Yaratilgan')

    class Meta:
        verbose_name = "To'lov"
        verbose_name_plural = "To'lovlar"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.full_name} - {self.amount} so'm - {self.get_status_display()}"


class PendingPaymentSession(models.Model):
    """To'lov sessiyasi - foydalanuvchi to'lov jarayonida"""

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='pending_sessions',
        verbose_name='Foydalanuvchi'
    )
    tariff = models.ForeignKey(
        Tariff,
        on_delete=models.CASCADE,
        related_name='pending_sessions',
        verbose_name='Tarif'
    )
    amount = models.PositiveIntegerField(verbose_name="To'lov summasi")
    is_discounted = models.BooleanField(default=False, verbose_name='Chegirma')
    message_id = models.BigIntegerField(verbose_name='Xabar ID')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Boshlangan vaqt')
    expires_at = models.DateTimeField(verbose_name='Tugash vaqti')

    class Meta:
        verbose_name = "To'lov sessiyasi"
        verbose_name_plural = "To'lov sessiyalari"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.full_name} - {self.tariff.name}"

    @property
    def is_expired(self):
        """Sessiya muddati tugaganmi"""
        return timezone.now() > self.expires_at

    @classmethod
    def cleanup_expired(cls):
        """Muddati tugagan sessiyalarni o'chirish"""
        cls.objects.filter(expires_at__lt=timezone.now()).delete()
