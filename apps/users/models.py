import secrets
from django.db import models
from django.utils import timezone


class User(models.Model):
    """Telegram foydalanuvchi modeli"""

    user_id = models.BigIntegerField(unique=True, verbose_name='Telegram ID')
    username = models.CharField(max_length=255, blank=True, null=True, verbose_name='Username')
    full_name = models.CharField(max_length=255, verbose_name="To'liq ism")

    # Premium
    is_premium = models.BooleanField(default=False, verbose_name='Premium')
    premium_expires = models.DateTimeField(blank=True, null=True, verbose_name='Premium tugash vaqti')
    # Tugash eslatmasi yuborilganmi (har soatlik spam bo'lmasligi uchun)
    premium_expiry_notified = models.BooleanField(default=False, verbose_name='Tugash eslatmasi yuborilgan')

    # Trial
    free_trial_expires = models.DateTimeField(blank=True, null=True, verbose_name='Bepul muddat tugashi')

    # Referal
    referral_code = models.CharField(max_length=10, unique=True, verbose_name='Referal kod')
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='referrals',
        verbose_name='Taklif qilgan'
    )

    # Qaysi kanal orqali kelgan
    joined_from_channel = models.ForeignKey(
        'channels.Channel',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='joined_users',
        verbose_name='Qaysi kanaldan kelgan'
    )

    # Statistika
    movies_watched = models.PositiveIntegerField(default=0, verbose_name="Ko'rilgan kinolar")

    # Flash sale - chegirma vaqti ichida
    premium_first_view = models.DateTimeField(blank=True, null=True, verbose_name='Premium birinchi ko\'rilgan')
    # Flash sale oynasi boshlangan vaqt (qayta o'rnatiladigan langar). Ikki trigger o'rnatadi:
    #   1) premium bo'lmagan user premium kino kodini kiritganda
    #   2) trial tugagan kuni scheduler push yuborganda
    flash_sale_started = models.DateTimeField(blank=True, null=True, verbose_name='Flash sale boshlangan')
    # Trial tugashi bo'yicha flash push yuborilganmi (takror spamning oldini oladi)
    trial_flash_sent = models.BooleanField(default=False, verbose_name='Trial flash yuborilgan')

    # Holat
    is_banned = models.BooleanField(default=False, verbose_name='Bloklangan')
    ban_reason = models.TextField(blank=True, null=True, verbose_name='Bloklash sababi')

    # Vaqtlar
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ro'yxatdan o'tgan")
    last_active = models.DateTimeField(auto_now=True, verbose_name='Oxirgi faollik')

    class Meta:
        verbose_name = 'Foydalanuvchi'
        verbose_name_plural = 'Foydalanuvchilar'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} ({self.user_id})"

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self._generate_referral_code()
        # Yangi userlarga trial berish
        if not self.free_trial_expires and not self.pk:
            from apps.core.models import BotSettings
            from datetime import timedelta
            settings = BotSettings.get_settings()
            if settings.free_trial_days > 0:
                self.free_trial_expires = timezone.now() + timedelta(days=settings.free_trial_days)
        super().save(*args, **kwargs)

    def _generate_referral_code(self):
        while True:
            code = secrets.token_hex(4).upper()
            if not User.objects.filter(referral_code=code).exists():
                return code

    @property
    def is_trial_active(self):
        """Trial hali aktivmi"""
        if self.free_trial_expires:
            return timezone.now() < self.free_trial_expires
        return False

    @property
    def is_premium_active(self):
        """Premium aktivmi"""
        if not self.is_premium:
            return False
        # is_premium=True, lekin muddat ko'rsatilmagan (admin qo'lda "Premium" ni
        # belgilagan) -> muddatsiz premium sifatida aktiv hisoblaymiz.
        if self.premium_expires is None:
            return True
        return timezone.now() < self.premium_expires

    @property
    def can_watch_movies(self):
        """Kino ko'ra oladimi"""
        return self.is_premium_active or self.is_trial_active

    @property
    def days_left(self):
        """Necha kun qoldi"""
        if self.is_premium_active:
            if self.premium_expires is None:
                return 0  # muddatsiz premium - "qolgan kun" ma'noga ega emas
            delta = self.premium_expires - timezone.now()
            return max(0, delta.days)
        elif self.is_trial_active:
            delta = self.free_trial_expires - timezone.now()
            return max(0, delta.days)
        return 0

    @property
    def referrals_count(self):
        """Taklif qilganlar soni"""
        return self.referrals.count()

    def _get_discount_duration(self):
        """Chegirma muddatini olish (sekundda)"""
        try:
            from apps.core.models import BotSettings
            settings = BotSettings.get_settings()
            return settings.discount_duration
        except Exception:
            return 30  # Default 30 soniya

    @property
    def is_flash_sale_active(self):
        """Flash sale oynasi hozir ochiqmi (langar o'rnatilgan va muddat o'tmagan)"""
        if not self.flash_sale_started:
            return False  # Trigger bo'lmagan - flash sale yo'q
        duration = self._get_discount_duration()
        time_passed = (timezone.now() - self.flash_sale_started).total_seconds()
        return time_passed <= duration

    @property
    def flash_sale_seconds_left(self):
        """Flash sale uchun qancha vaqt qoldi (sekundda)"""
        duration = self._get_discount_duration()
        if not self.flash_sale_started:
            return 0
        time_passed = (timezone.now() - self.flash_sale_started).total_seconds()
        remaining = duration - time_passed
        return max(0, int(remaining))


class Admin(models.Model):
    """Admin modeli"""

    ROLE_CHOICES = [
        ('superadmin', 'Super Admin'),
        ('admin', 'Admin'),
        ('moderator', 'Moderator'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile', verbose_name='Foydalanuvchi')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='moderator', verbose_name='Rol')

    # Ruxsatlar
    can_add_movies = models.BooleanField(default=False, verbose_name="Kino qo'sha oladi")
    can_broadcast = models.BooleanField(default=False, verbose_name='Xabar yuborishi mumkin')
    can_manage_users = models.BooleanField(default=False, verbose_name='Userlarni boshqaradi')
    can_manage_payments = models.BooleanField(default=False, verbose_name="To'lovlarni boshqaradi")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Yaratilgan')

    class Meta:
        verbose_name = 'Admin'
        verbose_name_plural = 'Adminlar'

    def __str__(self):
        return f"{self.user.full_name} - {self.get_role_display()}"

    def save(self, *args, **kwargs):
        if self.role == 'superadmin':
            self.can_add_movies = True
            self.can_broadcast = True
            self.can_manage_users = True
            self.can_manage_payments = True
        elif self.role == 'admin':
            self.can_add_movies = True
            self.can_broadcast = True
            self.can_manage_users = True
        super().save(*args, **kwargs)
