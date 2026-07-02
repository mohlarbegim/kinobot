"""
React admin dashboard uchun DRF serializerlar.

Eslatma: bu yerdagi "User" - apps.users.User (Telegram foydalanuvchisi), auth.User EMAS.
Admin login uchun auth.User (superuser) ishlatiladi (auth.py ga qarang).
"""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.users.models import User, Admin
from apps.movies.models import Category, Movie, SavedMovie
from apps.channels.models import Channel, ChannelSubscription
from apps.payments.models import Tariff, Payment, PendingPaymentSession
from apps.core.models import BotSettings, MessageTemplate, Broadcast


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class StaffTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Faqat is_staff (admin) foydalanuvchilar dashboard'ga kira oladi."""

    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.is_staff:
            raise serializers.ValidationError(
                "Bu hisobda admin panelga kirish huquqi yo'q."
            )
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'is_superuser': self.user.is_superuser,
        }
        return data


# ---------------------------------------------------------------------------
# Users (Telegram foydalanuvchilari)
# ---------------------------------------------------------------------------
class UserSerializer(serializers.ModelSerializer):
    is_premium_active = serializers.BooleanField(read_only=True)
    is_trial_active = serializers.BooleanField(read_only=True)
    can_watch_movies = serializers.BooleanField(read_only=True)
    days_left = serializers.IntegerField(read_only=True)
    referrals_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'user_id', 'username', 'full_name',
            'is_premium', 'premium_expires', 'free_trial_expires',
            'referral_code', 'referred_by', 'joined_from_channel',
            'movies_watched', 'is_banned', 'ban_reason',
            'created_at', 'last_active',
            'is_premium_active', 'is_trial_active', 'can_watch_movies',
            'days_left', 'referrals_count',
        ]
        read_only_fields = [
            'id', 'user_id', 'referral_code', 'referred_by', 'joined_from_channel',
            'movies_watched', 'created_at', 'last_active',
        ]


class AdminSerializer(serializers.ModelSerializer):
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    user_telegram_id = serializers.IntegerField(source='user.user_id', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = Admin
        fields = [
            'id', 'user', 'user_full_name', 'user_telegram_id',
            'role', 'role_display',
            'can_add_movies', 'can_broadcast', 'can_manage_users', 'can_manage_payments',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ---------------------------------------------------------------------------
# Movies
# ---------------------------------------------------------------------------
class CategorySerializer(serializers.ModelSerializer):
    movies_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'emoji', 'slug', 'order', 'is_active', 'movies_count']
        read_only_fields = ['id', 'slug', 'movies_count']

    def get_movies_count(self, obj):
        return obj.movies.count()


class MovieSerializer(serializers.ModelSerializer):
    display_title = serializers.CharField(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    quality_display = serializers.CharField(source='get_quality_display', read_only=True)
    country_display = serializers.CharField(source='get_country_display', read_only=True)
    language_display = serializers.CharField(source='get_language_display', read_only=True)

    class Meta:
        model = Movie
        fields = [
            'id', 'code', 'title', 'title_uz', 'display_title',
            'file_id', 'thumbnail_file_id',
            'category', 'category_name',
            'year', 'duration',
            'quality', 'quality_display',
            'language', 'language_display',
            'country', 'country_display',
            'description', 'is_premium', 'views', 'is_active',
            'created_at', 'added_by',
        ]
        read_only_fields = ['id', 'views', 'created_at', 'added_by']


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------
class ChannelSerializer(serializers.ModelSerializer):
    is_checkable = serializers.BooleanField(read_only=True)
    subscribers_count = serializers.IntegerField(read_only=True)
    channel_type_display = serializers.CharField(source='get_channel_type_display', read_only=True)

    class Meta:
        model = Channel
        fields = [
            'id', 'channel_id', 'username', 'title', 'invite_link',
            'channel_type', 'channel_type_display',
            'order', 'is_active', 'created_at',
            'is_checkable', 'subscribers_count',
        ]
        read_only_fields = ['id', 'created_at', 'is_checkable', 'subscribers_count']


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
class TariffSerializer(serializers.ModelSerializer):
    discount_percent = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tariff
        fields = [
            'id', 'name', 'days', 'price', 'discounted_price',
            'discount_percent', 'order', 'is_active',
        ]
        read_only_fields = ['id', 'discount_percent']


class PaymentSerializer(serializers.ModelSerializer):
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    user_telegram_id = serializers.IntegerField(source='user.user_id', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True, default=None)
    tariff_name = serializers.CharField(source='tariff.name', read_only=True, default=None)
    tariff_days = serializers.IntegerField(source='tariff.days', read_only=True, default=None)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.full_name', read_only=True, default=None)

    class Meta:
        model = Payment
        fields = [
            'id', 'user', 'user_full_name', 'user_telegram_id', 'user_username',
            'tariff', 'tariff_name', 'tariff_days',
            'amount', 'is_discounted',
            'status', 'status_display',
            'screenshot_file_id', 'admin_note',
            'approved_by', 'approved_by_name', 'approved_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'user', 'tariff', 'amount', 'is_discounted',
            'screenshot_file_id', 'approved_by', 'approved_at', 'created_at',
        ]


# ---------------------------------------------------------------------------
# Core: settings, templates, broadcasts
# ---------------------------------------------------------------------------
class BotSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotSettings
        fields = [
            'id', 'is_active', 'maintenance_message',
            'card_number', 'card_holder',
            'discount_active', 'discount_percent', 'discount_duration',
            'free_trial_days', 'referral_active', 'referral_bonus',
            'admin_contact', 'channel_link', 'channel_name',
        ]
        read_only_fields = ['id']


class MessageTemplateSerializer(serializers.ModelSerializer):
    message_type_display = serializers.CharField(source='get_message_type_display', read_only=True)

    class Meta:
        model = MessageTemplate
        fields = [
            'id', 'message_type', 'message_type_display',
            'title', 'content', 'placeholders_help', 'updated_at',
        ]
        read_only_fields = ['id', 'message_type', 'updated_at']


class BroadcastSerializer(serializers.ModelSerializer):
    target_display = serializers.CharField(source='get_target_display', read_only=True)
    sent_by_name = serializers.CharField(source='sent_by.full_name', read_only=True, default=None)

    class Meta:
        model = Broadcast
        fields = [
            'id', 'target', 'target_display', 'content_type',
            'text', 'file_id', 'is_advertisement', 'buttons',
            'total_users', 'sent_count', 'failed_count',
            'is_completed', 'sent_by', 'sent_by_name',
            'started_at', 'completed_at',
        ]
        read_only_fields = [
            'id', 'total_users', 'sent_count', 'failed_count',
            'is_completed', 'sent_by', 'started_at', 'completed_at',
        ]
