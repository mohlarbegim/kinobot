from django.db import models
from django.core.cache import cache


class BotSettings(models.Model):
    """Bot sozlamalari - Singleton"""

    # Asosiy
    is_active = models.BooleanField(default=True, verbose_name='Bot aktiv')
    maintenance_message = models.TextField(
        blank=True,
        default='Bot texnik ishlar sababli vaqtincha to\'xtatilgan. Iltimos keyinroq urinib ko\'ring.',
        verbose_name='Texnik ishlar xabari'
    )

    # To'lov
    card_number = models.CharField(max_length=50, verbose_name='Karta raqami')
    card_holder = models.CharField(max_length=100, verbose_name='Karta egasi')

    # Chegirma
    discount_active = models.BooleanField(default=True, verbose_name='Chegirma aktiv')
    discount_percent = models.PositiveIntegerField(default=50, verbose_name='Chegirma foizi')
    discount_duration = models.PositiveIntegerField(default=180, verbose_name='Chegirma muddati (sekund)')

    # Trial
    free_trial_days = models.PositiveIntegerField(default=7, verbose_name='Bepul kunlar soni')

    # Referal
    referral_active = models.BooleanField(default=True, verbose_name='Referal aktiv')
    referral_bonus = models.PositiveIntegerField(default=1, verbose_name='Referal bonus (kun)')

    # Admin
    admin_contact = models.CharField(max_length=100, blank=True, default='', verbose_name='Admin kontakt')

    # Kanal link (Kino qidirish sahifasida ko'rinadi)
    channel_link = models.URLField(max_length=200, blank=True, default='', verbose_name='Kanal linki')
    channel_name = models.CharField(max_length=100, blank=True, default='Bizning kanal', verbose_name='Kanal nomi')

    class Meta:
        verbose_name = 'Bot sozlamalari'
        verbose_name_plural = 'Bot sozlamalari'

    def __str__(self):
        return 'Bot sozlamalari'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete('bot_settings')
        # Bot jarayonining in-process settings cache'ini ham tozalatamiz (Redis pub/sub)
        from apps.core.cache_bus import publish_invalidation
        publish_invalidation('settings')

    @classmethod
    def get_settings(cls):
        """Singleton instance olish"""
        settings = cache.get('bot_settings')
        if not settings:
            settings, _ = cls.objects.get_or_create(
                pk=1,
                defaults={
                    'card_number': '8600 0000 0000 0000',
                    'card_holder': 'CARD HOLDER',
                }
            )
            cache.set('bot_settings', settings, 300)
        return settings


class MessageTemplate(models.Model):
    """Bot xabarlari shablonlari"""

    MESSAGE_TYPES = [
        ('welcome', 'Salom xabari'),
        ('subscription_required', 'Obuna talab qilish'),
        ('subscription_success', 'Obuna muvaffaqiyatli'),
        ('premium_required', 'Premium talab qilish'),
        ('premium_info', 'Premium ma\'lumot'),
        ('premium_success', 'Premium muvaffaqiyatli'),
        ('payment_instructions', 'To\'lov ko\'rsatmalari'),
        ('payment_pending', 'To\'lov kutilmoqda'),
        ('payment_approved', 'To\'lov tasdiqlandi'),
        ('payment_rejected', 'To\'lov rad etildi'),
        ('movie_not_found', 'Kino topilmadi'),
        ('search_prompt', 'Qidiruv so\'rovi'),
        ('profile_info', 'Profil ma\'lumoti'),
        ('referral_info', 'Referal ma\'lumoti'),
        ('ban_message', 'Ban xabari'),
        ('maintenance', 'Texnik ishlar'),
    ]

    message_type = models.CharField(max_length=50, choices=MESSAGE_TYPES, unique=True, verbose_name='Xabar turi')
    title = models.CharField(max_length=100, verbose_name='Sarlavha')
    content = models.TextField(verbose_name='Xabar matni')

    # Placeholders haqida ma'lumot
    placeholders_help = models.TextField(blank=True, default='', verbose_name='Placeholder yordam')

    updated_at = models.DateTimeField(auto_now=True, verbose_name='Yangilangan')

    class Meta:
        verbose_name = 'Xabar shabloni'
        verbose_name_plural = 'Xabar shablonlari'
        ordering = ['message_type']

    def __str__(self):
        return f"{self.get_message_type_display()}"

    @classmethod
    def get_message(cls, message_type: str, **kwargs) -> str:
        """Xabarni olish va formatlash"""
        try:
            template = cls.objects.get(message_type=message_type)
            content = template.content
            for key, value in kwargs.items():
                content = content.replace(f'{{{key}}}', str(value))
            return content
        except cls.DoesNotExist:
            return cls._get_default_message(message_type, **kwargs)

    @classmethod
    def _get_default_message(cls, message_type: str, **kwargs) -> str:
        """Default xabarlar"""
        defaults = {
            'welcome': '👋 Salom, <b>{full_name}</b>!\n\n{status}🎬 Kino kodini yuboring yoki menyu tugmalaridan foydalaning:',
            'subscription_required': '📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo\'ling:',
            'subscription_success': '✅ Obuna tasdiqlandi!\n\n🎬 Kino kodini yuboring:',
            'premium_required': '💎 Bu kino faqat Premium foydalanuvchilar uchun.',
            'premium_info': '💎 Premium afzalliklari:\n\n✅ Barcha kinolarni ko\'rish\n✅ Reklama yo\'q\n✅ Tezkor yuklash',
            'premium_success': '🎉 Tabriklaymiz! Premium muvaffaqiyatli aktivlashtirildi.\n\n⏰ Amal qilish muddati: {days} kun',
            'payment_instructions': '💳 <b>To\'lov ma\'lumotlari:</b>\n\n📦 Tarif: <b>{tariff_name}</b>\n📅 Muddat: <b>{days} kun</b>\n💰 Narx: <b>{price}</b>\n\n💳 Karta: <code>{card_number}</code>\n👤 Egasi: <b>{card_holder}</b>\n\n📸 <b>To\'lovni amalga oshiring va screenshot yuboring.</b>\n\n⚠️ Izoh: Chekda <code>{user_id}</code> ni ko\'rsating.',
            'payment_pending': '⏳ To\'lovingiz tekshirilmoqda. Iltimos kuting...',
            'payment_approved': '🎉 <b>Premium aktivlashtirildi!</b>\n\n📦 Tarif: {tariff_name}\n📅 Muddat: {days} kun\n\nBotdan foydalaning! 🎬',
            'payment_rejected': '❌ <b>To\'lov rad etildi!</b>\n\nIltimos, to\'g\'ri chek yuboring yoki admin bilan bog\'laning.',
            'movie_not_found': '❌ <code>{code}</code> kodli kino topilmadi.\n\n🔍 Kodni tekshirib qaytadan yuboring.',
            'search_prompt': '🔍 <b>Kino qidirish</b>\n\nKino kodini yuboring yoki filter tanlang:\nMasalan: <code>123</code>',
            'profile_info': '👤 <b>Profil</b>\n\n🆔 ID: <code>{user_id}</code>\n👤 Ism: {full_name}\n📊 Status: {status}\n🎬 Ko\'rilgan: {movies_watched}\n\n🔗 <b>Referal:</b>\nKod: <code>{referral_code}</code>\nTaklif qilganlar: {referrals_count} ta\n\n📎 Havolangiz:\nhttps://t.me/{bot_username}?start={referral_code}',
            'referral_info': '👥 Sizning referal havolangiz:\n\n{referral_link}\n\n✅ Taklif qilganlar: {referrals_count} ta',
            'ban_message': '🚫 Siz bloklangansiz.\n\nSabab: {reason}',
            'maintenance': '🔧 Bot texnik ishlar sababli vaqtincha to\'xtatilgan.',
        }
        content = defaults.get(message_type, 'Xabar topilmadi')
        for key, value in kwargs.items():
            content = content.replace(f'{{{key}}}', str(value))
        return content

    @classmethod
    def init_defaults(cls):
        """Barcha default xabarlarni yaratish"""
        defaults = {
            'welcome': ('Salom xabari', '👋 Salom, <b>{full_name}</b>!\n\n{status}🎬 Kino kodini yuboring yoki menyu tugmalaridan foydalaning:', '{full_name} - foydalanuvchi ismi; {status} - Premium/Trial belgisi'),
            'subscription_required': ('Obuna talab qilish', '📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo\'ling:', ''),
            'subscription_success': ('Obuna muvaffaqiyatli', '✅ Obuna tasdiqlandi!\n\n🎬 Kino kodini yuboring:', ''),
            'premium_required': ('Premium talab qilish', '💎 Bu kino faqat Premium foydalanuvchilar uchun.\n\nPremium olish uchun /premium buyrug\'ini yuboring.', ''),
            'premium_info': ('Premium ma\'lumot', '💎 <b>Premium afzalliklari:</b>\n\n✅ Barcha kinolarni ko\'rish\n✅ Reklama yo\'q\n✅ Tezkor yuklash\n✅ Eksklyuziv kontentlar', ''),
            'premium_success': ('Premium muvaffaqiyatli', '🎉 Tabriklaymiz!\n\n💎 Premium muvaffaqiyatli aktivlashtirildi.\n⏰ Amal qilish muddati: {days} kun', '{days} - kunlar soni'),
            'payment_instructions': ('To\'lov ko\'rsatmalari', '💳 <b>To\'lov ma\'lumotlari:</b>\n\n📦 Tarif: <b>{tariff_name}</b>\n📅 Muddat: <b>{days} kun</b>\n💰 Narx: <b>{price}</b>\n\n💳 Karta: <code>{card_number}</code>\n👤 Egasi: <b>{card_holder}</b>\n\n📸 <b>To\'lovni amalga oshiring va screenshot yuboring.</b>\n\n⚠️ Izoh: Chekda <code>{user_id}</code> ni ko\'rsating.', '{tariff_name}, {days}, {price}, {card_number}, {card_holder}, {user_id}'),
            'payment_pending': ('To\'lov kutilmoqda', '⏳ To\'lovingiz tekshirilmoqda.\n\nAdmin tez orada tasdiqlaydi. Iltimos kuting...', ''),
            'payment_approved': ('To\'lov tasdiqlandi', '🎉 <b>Premium aktivlashtirildi!</b>\n\n📦 Tarif: {tariff_name}\n📅 Muddat: {days} kun\n\nBotdan foydalaning! 🎬', '{tariff_name} - tarif nomi; {days} - kunlar soni'),
            'payment_rejected': ('To\'lov rad etildi', '❌ <b>To\'lov rad etildi!</b>\n\nIltimos, to\'g\'ri chek yuboring yoki admin bilan bog\'laning.', ''),
            'movie_not_found': ('Kino topilmadi', '❌ <code>{code}</code> kodli kino topilmadi.\n\n🔍 Kodni tekshirib qaytadan yuboring.', '{code} - kiritilgan kod'),
            'search_prompt': ('Qidiruv so\'rovi', '🔍 <b>Kino qidirish</b>\n\nKino kodini yuboring yoki filter tanlang:\nMasalan: <code>123</code>', ''),
            'profile_info': ('Profil ma\'lumoti', '👤 <b>Profil</b>\n\n🆔 ID: <code>{user_id}</code>\n👤 Ism: {full_name}\n📊 Status: {status}\n🎬 Ko\'rilgan: {movies_watched}\n\n🔗 <b>Referal:</b>\nKod: <code>{referral_code}</code>\nTaklif qilganlar: {referrals_count} ta\n\n📎 Havolangiz:\nhttps://t.me/{bot_username}?start={referral_code}', '{full_name}, {user_id}, {status}, {movies_watched}, {referral_code}, {referrals_count}, {bot_username}'),
            'referral_info': ('Referal ma\'lumoti', '👥 <b>Referal dasturi</b>\n\n🔗 Sizning havolangiz:\n{referral_link}\n\n✅ Taklif qilganlar: {referrals_count} ta\n🎁 Bonus: Har bir do\'st uchun +{bonus_days} kun', '{referral_link}, {referrals_count}, {bonus_days}'),
            'ban_message': ('Ban xabari', '🚫 <b>Siz bloklangansiz!</b>\n\nSabab: {reason}\n\nAgar xatolik bo\'lsa, admin bilan bog\'laning.', '{reason} - bloklash sababi'),
            'maintenance': ('Texnik ishlar', '🔧 <b>Texnik ishlar</b>\n\nBot vaqtincha to\'xtatilgan.\nIltimos keyinroq urinib ko\'ring.', ''),
        }

        for msg_type, (title, content, placeholders) in defaults.items():
            cls.objects.get_or_create(
                message_type=msg_type,
                defaults={
                    'title': title,
                    'content': content,
                    'placeholders_help': placeholders
                }
            )


class Broadcast(models.Model):
    """Xabar yuborish"""

    TARGET_CHOICES = [
        ('all', 'Hammaga'),
        ('premium', 'Premium foydalanuvchilar'),
        ('regular', 'Oddiy foydalanuvchilar'),
    ]

    CONTENT_TYPE_CHOICES = [
        ('text', 'Matn'),
        ('photo', 'Rasm'),
        ('video', 'Video'),
        ('document', 'Fayl'),
    ]

    target = models.CharField(max_length=20, choices=TARGET_CHOICES, default='all', verbose_name='Kimga')
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES, default='text', verbose_name='Kontent turi')

    text = models.TextField(blank=True, default='', verbose_name='Xabar matni')
    file_id = models.CharField(max_length=255, blank=True, default='', verbose_name='File ID')

    is_advertisement = models.BooleanField(default=False, verbose_name='Reklama (premium ga bormaydi)')

    buttons = models.JSONField(blank=True, null=True, verbose_name='Inline tugmalar')

    # Statistika
    total_users = models.PositiveIntegerField(default=0, verbose_name='Jami foydalanuvchilar')
    sent_count = models.PositiveIntegerField(default=0, verbose_name='Yuborildi')
    failed_count = models.PositiveIntegerField(default=0, verbose_name='Xato')

    is_completed = models.BooleanField(default=False, verbose_name='Tugallandi')

    sent_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='broadcasts',
        verbose_name='Kim yubordi'
    )

    started_at = models.DateTimeField(auto_now_add=True, verbose_name='Boshlangan')
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name='Tugallangan')

    class Meta:
        verbose_name = 'Xabar yuborish'
        verbose_name_plural = 'Xabar yuborishlar'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.get_target_display()} - {self.started_at.strftime('%d.%m.%Y %H:%M')}"
