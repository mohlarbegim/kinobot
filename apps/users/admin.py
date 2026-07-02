from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import User, Admin


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['user_id', 'full_name', 'username', 'premium_badge', 'movies_watched', 'created_at']
    list_filter = ['is_premium', 'is_banned', 'created_at']
    search_fields = ['user_id', 'username', 'full_name']
    readonly_fields = ['user_id', 'referral_code', 'movies_watched', 'created_at', 'last_active']
    ordering = ['-created_at']

    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('user_id', 'username', 'full_name')
        }),
        ('Premium', {
            'fields': ('is_premium', 'premium_expires', 'free_trial_expires')
        }),
        ('Referal', {
            'fields': ('referral_code', 'referred_by')
        }),
        ('Statistika', {
            'fields': ('movies_watched',)
        }),
        ('Holat', {
            'fields': ('is_banned', 'ban_reason')
        }),
        ('Vaqtlar', {
            'fields': ('created_at', 'last_active')
        }),
    )

    actions = ['give_premium_30_days', 'ban_users', 'unban_users']

    @admin.display(description='Premium')
    def premium_badge(self, obj):
        if obj.is_premium_active:
            return format_html('<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 3px;">Premium</span>')
        elif obj.is_trial_active:
            return format_html('<span style="background-color: #17a2b8; color: white; padding: 3px 8px; border-radius: 3px;">Trial</span>')
        return format_html('<span style="background-color: #6c757d; color: white; padding: 3px 8px; border-radius: 3px;">Oddiy</span>')

    @admin.action(description='30 kun premium berish')
    def give_premium_30_days(self, request, queryset):
        for user in queryset:
            user.is_premium = True
            if user.premium_expires and user.premium_expires > timezone.now():
                user.premium_expires += timezone.timedelta(days=30)
            else:
                user.premium_expires = timezone.now() + timezone.timedelta(days=30)
            user.save()
        self.message_user(request, f'{queryset.count()} foydalanuvchiga 30 kun premium berildi.')

    @admin.action(description='Bloklash')
    def ban_users(self, request, queryset):
        # .update() post_save signalini ishga tushirmaydi -> bot cache'ini o'zimiz tozalatamiz
        from apps.core.cache_bus import publish_invalidation
        user_ids = list(queryset.values_list('user_id', flat=True))
        queryset.update(is_banned=True)
        for uid in user_ids:
            publish_invalidation('user', id=uid)
        self.message_user(request, f'{len(user_ids)} foydalanuvchi bloklandi.')

    @admin.action(description='Blokdan chiqarish')
    def unban_users(self, request, queryset):
        from apps.core.cache_bus import publish_invalidation
        user_ids = list(queryset.values_list('user_id', flat=True))
        queryset.update(is_banned=False, ban_reason='')
        for uid in user_ids:
            publish_invalidation('user', id=uid)
        self.message_user(request, f'{len(user_ids)} foydalanuvchi blokdan chiqarildi.')


@admin.register(Admin)
class AdminAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'can_add_movies', 'can_broadcast', 'can_manage_users', 'can_manage_payments']
    list_filter = ['role']
    search_fields = ['user__full_name', 'user__username']
