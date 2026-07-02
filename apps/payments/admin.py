from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import Tariff, Payment


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ['name', 'days', 'price', 'discounted_price', 'discount_percent', 'order', 'is_active']
    list_filter = ['is_active']
    ordering = ['order', 'days']

    @admin.display(description='Chegirma %')
    def discount_percent(self, obj):
        percent = obj.discount_percent
        if percent > 0:
            return format_html('<span style="color: green;">-{}%</span>', percent)
        return '-'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'tariff', 'amount', 'status_badge', 'created_at']
    list_filter = ['status', 'created_at', 'is_discounted']
    search_fields = ['user__full_name', 'user__username', 'user__user_id']
    readonly_fields = ['user', 'tariff', 'amount', 'is_discounted', 'screenshot_file_id', 'created_at']
    ordering = ['-created_at']

    fieldsets = (
        ('To\'lov ma\'lumotlari', {
            'fields': ('user', 'tariff', 'amount', 'is_discounted', 'screenshot_file_id')
        }),
        ('Holat', {
            'fields': ('status', 'admin_note')
        }),
        ('Tasdiqlash', {
            'fields': ('approved_by', 'approved_at')
        }),
        ('Vaqt', {
            'fields': ('created_at',)
        }),
    )

    actions = ['approve_payments', 'reject_payments']

    @admin.display(description='Holat')
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'approved': '#28a745',
            'rejected': '#dc3545',
            'expired': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        text_color = 'black' if obj.status == 'pending' else 'white'
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, text_color, obj.get_status_display()
        )

    @admin.action(description='Tasdiqlash')
    def approve_payments(self, request, queryset):
        from apps.users.models import User
        from django.db import transaction
        admin_user = User.objects.filter(user_id=request.user.id).first()

        approved = 0
        skipped = 0
        for payment in queryset.filter(status='pending').select_related('tariff', 'user'):
            # Tarif o'chirilgan bo'lsa (SET_NULL) kunlar sonini bilib bo'lmaydi -> o'tkazamiz
            if payment.tariff is None:
                skipped += 1
                continue

            # Har bir to'lovni alohida atomik tranzaksiyada - biri xato bersa
            # boshqalari ta'sirlanmaydi (qisman/yarim tasdiqlash bo'lmaydi).
            with transaction.atomic():
                payment.status = 'approved'
                payment.approved_by = admin_user
                payment.approved_at = timezone.now()
                payment.save(update_fields=['status', 'approved_by', 'approved_at'])

                user = payment.user
                user.is_premium = True
                user.premium_expiry_notified = False
                if user.premium_expires and user.premium_expires > timezone.now():
                    user.premium_expires += timezone.timedelta(days=payment.tariff.days)
                else:
                    user.premium_expires = timezone.now() + timezone.timedelta(days=payment.tariff.days)
                user.save(update_fields=['is_premium', 'premium_expires', 'premium_expiry_notified'])
            approved += 1

        msg = f'{approved} ta to\'lov tasdiqlandi.'
        if skipped:
            msg += f' {skipped} ta o\'tkazib yuborildi (tarif o\'chirilgan).'
        self.message_user(request, msg)

    @admin.action(description='Rad etish')
    def reject_payments(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='rejected')
        self.message_user(request, f'{updated} ta to\'lov rad etildi.')
