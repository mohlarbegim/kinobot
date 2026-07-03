"""
React admin dashboard uchun DRF view'lar.

Xavfsizlik: barcha endpointlar default holatda IsAdminUser (is_staff) talab qiladi
(settings.REST_FRAMEWORK). Faqat login (StaffTokenObtainPairView) AllowAny.

Cache: premium/ban/premium_expires o'zgarganda bot jarayoniga Redis pub/sub orqali
xabar boradi. apps.users.User.post_save signali update_fields None yoki
{is_banned,ban_reason,is_premium,premium_expires} bilan kesishganda publish_invalidation('user')
chiqaradi. Shuning uchun quyidagi yozuvlar shu maydonlarni update_fields ga kiritadi.
"""
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django_filters.rest_framework import DjangoFilterBackend

from apps.users.models import User, Admin
from apps.movies.models import Category, Movie
from apps.channels.models import Channel
from apps.payments.models import Tariff, Payment
from apps.core.models import BotSettings, MessageTemplate, Broadcast
from apps.core.cache_bus import publish_invalidation

from .serializers import (
    StaffTokenObtainPairSerializer,
    UserSerializer, AdminSerializer,
    CategorySerializer, MovieSerializer,
    ChannelSerializer,
    TariffSerializer, PaymentSerializer,
    BotSettingsSerializer, MessageTemplateSerializer, BroadcastSerializer,
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class StaffTokenObtainPairView(TokenObtainPairView):
    """POST /api/auth/login/ -> {access, refresh, user}. Faqat is_staff."""
    permission_classes = [AllowAny]
    serializer_class = StaffTokenObtainPairSerializer


@api_view(['GET'])
@permission_classes([IsAdminUser])
def me(request):
    u = request.user
    return Response({
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'is_superuser': u.is_superuser,
        'is_staff': u.is_staff,
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def upload_media(request):
    """Media faylni Telegram'ga yuklab, broadcast uchun file_id qaytaradi.

    Fayl birinchi adminга (ADMINS[0]) yuboriladi (file_id olish uchun) va darhol
    o'chiriladi. web env'da BOT_TOKEN va ADMINS bo'lishi shart.
    """
    import requests
    from django.conf import settings

    f = request.FILES.get('file')
    if not f:
        return Response({'detail': 'Fayl yuborilmadi'}, status=status.HTTP_400_BAD_REQUEST)

    token = settings.BOT_TOKEN
    admins = settings.ADMINS
    if not token or not admins:
        return Response(
            {'detail': "Media yuklash uchun BOT_TOKEN va ADMINS sozlanishi kerak (web xizmatida)."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if f.size > 45 * 1024 * 1024:
        return Response({'detail': "Fayl juda katta (45MB dan kichik bo'lsin)"},
                        status=status.HTTP_400_BAD_REQUEST)

    ctype = (f.content_type or '').lower()
    if ctype.startswith('image/'):
        method, field, kind = 'sendPhoto', 'photo', 'photo'
    elif ctype.startswith('video/'):
        method, field, kind = 'sendVideo', 'video', 'video'
    else:
        method, field, kind = 'sendDocument', 'document', 'document'

    chat_id = admins[0]
    try:
        resp = requests.post(
            f'https://api.telegram.org/bot{token}/{method}',
            data={'chat_id': chat_id, 'disable_notification': 'true'},
            files={field: (f.name, f.read(), ctype or 'application/octet-stream')},
            timeout=90,
        )
        data = resp.json()
    except Exception as e:
        return Response({'detail': f"Telegram bilan bog'lanishda xato: {e}"},
                        status=status.HTTP_502_BAD_GATEWAY)

    if not data.get('ok'):
        return Response({'detail': f"Telegram xatosi: {data.get('description')}"},
                        status=status.HTTP_502_BAD_GATEWAY)

    result = data['result']
    if kind == 'photo':
        file_id = result['photo'][-1]['file_id']  # eng katta o'lcham
    elif kind == 'video':
        file_id = result['video']['file_id']
    else:
        file_id = result['document']['file_id']

    # file_id olindi -> vaqtinchalik xabarni o'chiramiz (best-effort)
    try:
        requests.post(
            f'https://api.telegram.org/bot{token}/deleteMessage',
            data={'chat_id': chat_id, 'message_id': result['message_id']},
            timeout=15,
        )
    except Exception:
        pass

    return Response({'file_id': file_id, 'content_type': kind, 'name': f.name})


# ---------------------------------------------------------------------------
# Users (Telegram foydalanuvchilari)
# ---------------------------------------------------------------------------
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().select_related('referred_by')
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_premium', 'is_banned']
    search_fields = ['user_id', 'username', 'full_name']
    ordering_fields = ['created_at', 'last_active', 'movies_watched']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        preset = self.request.query_params.get('preset')
        now = timezone.now()
        if preset == 'premium':
            qs = qs.filter(is_premium=True, premium_expires__gt=now)
        elif preset == 'trial':
            qs = qs.filter(free_trial_expires__gt=now, is_premium=False)
        elif preset == 'regular':
            qs = qs.filter(is_premium=False).filter(
                Q(free_trial_expires__isnull=True) | Q(free_trial_expires__lte=now)
            )
        elif preset == 'today':
            qs = qs.filter(created_at__date=now.date())
        elif preset == 'banned':
            qs = qs.filter(is_banned=True)
        return qs

    @action(detail=True, methods=['post'])
    def ban(self, request, pk=None):
        user = self.get_object()
        reason = request.data.get('reason', '') or ''
        user.is_banned = True
        user.ban_reason = reason
        user.save(update_fields=['is_banned', 'ban_reason'])
        publish_invalidation('user', id=user.user_id)
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=['post'])
    def unban(self, request, pk=None):
        user = self.get_object()
        user.is_banned = False
        user.ban_reason = None
        user.save(update_fields=['is_banned', 'ban_reason'])
        publish_invalidation('user', id=user.user_id)
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=['post'], url_path='give-premium')
    def give_premium(self, request, pk=None):
        """{days: int} - premiumni uzaytiradi yoki yangi beradi."""
        try:
            days = int(request.data.get('days'))
        except (TypeError, ValueError):
            return Response({'detail': "days butun son bo'lishi kerak"},
                            status=status.HTTP_400_BAD_REQUEST)
        if days <= 0:
            return Response({'detail': 'days musbat bo\'lishi kerak'},
                            status=status.HTTP_400_BAD_REQUEST)
        user = self.get_object()
        now = timezone.now()
        base = user.premium_expires if (user.premium_expires and user.premium_expires > now) else now
        user.is_premium = True
        user.premium_expires = base + timedelta(days=days)
        user.premium_expiry_notified = False
        user.save(update_fields=['is_premium', 'premium_expires', 'premium_expiry_notified'])
        publish_invalidation('user', id=user.user_id)
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=['post'], url_path='remove-premium')
    def remove_premium(self, request, pk=None):
        user = self.get_object()
        user.is_premium = False
        user.premium_expires = None
        user.save(update_fields=['is_premium', 'premium_expires'])
        publish_invalidation('user', id=user.user_id)
        return Response(self.get_serializer(user).data)


class AdminViewSet(viewsets.ModelViewSet):
    """Bot adminlarini (Admin modeli) boshqarish. o'zgarganда 'admin' invalidatsiya."""
    queryset = Admin.objects.all().select_related('user')
    serializer_class = AdminSerializer
    search_fields = ['user__full_name', 'user__username']
    ordering_fields = ['created_at', 'role']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        obj = serializer.save()
        publish_invalidation('admin', id=obj.user.user_id)

    def perform_update(self, serializer):
        obj = serializer.save()
        publish_invalidation('admin', id=obj.user.user_id)

    def perform_destroy(self, instance):
        uid = instance.user.user_id
        instance.delete()
        publish_invalidation('admin', id=uid)


# ---------------------------------------------------------------------------
# Movies
# ---------------------------------------------------------------------------
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filterset_fields = ['is_active']
    search_fields = ['name', 'slug']
    ordering_fields = ['order', 'name']
    ordering = ['order', 'name']

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        obj = self.get_object()
        obj.is_active = not obj.is_active
        obj.save(update_fields=['is_active'])
        return Response(self.get_serializer(obj).data)


class MovieViewSet(viewsets.ModelViewSet):
    queryset = Movie.objects.all().select_related('category')
    serializer_class = MovieSerializer
    filterset_fields = ['category', 'country', 'quality', 'language', 'is_premium', 'is_active']
    search_fields = ['code', 'title', 'title_uz']
    ordering_fields = ['created_at', 'views', 'year']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        obj = self.get_object()
        obj.is_active = not obj.is_active
        obj.save(update_fields=['is_active'])
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'], url_path='toggle-premium')
    def toggle_premium(self, request, pk=None):
        obj = self.get_object()
        obj.is_premium = not obj.is_premium
        obj.save(update_fields=['is_premium'])
        return Response(self.get_serializer(obj).data)


# ---------------------------------------------------------------------------
# Channels (post_save/post_delete signali 'channels' invalidatsiyani chiqaradi)
# ---------------------------------------------------------------------------
class ChannelViewSet(viewsets.ModelViewSet):
    queryset = Channel.objects.all()
    serializer_class = ChannelSerializer
    filterset_fields = ['channel_type', 'is_active']
    search_fields = ['title', 'username']
    ordering_fields = ['order', 'title']
    ordering = ['order', 'title']

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        obj = self.get_object()
        obj.is_active = not obj.is_active
        obj.save(update_fields=['is_active'])  # save() -> post_save signal -> 'channels'
        return Response(self.get_serializer(obj).data)


# ---------------------------------------------------------------------------
# Tariffs
# ---------------------------------------------------------------------------
class TariffViewSet(viewsets.ModelViewSet):
    queryset = Tariff.objects.all()
    serializer_class = TariffSerializer
    filterset_fields = ['is_active']
    ordering_fields = ['order', 'days', 'price']
    ordering = ['order', 'days']

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        obj = self.get_object()
        obj.is_active = not obj.is_active
        obj.save(update_fields=['is_active'])
        return Response(self.get_serializer(obj).data)


# ---------------------------------------------------------------------------
# Payments - atomik approve/reject (bot/handlers/payment.py mantig'i)
# ---------------------------------------------------------------------------
class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all().select_related('user', 'tariff', 'approved_by')
    serializer_class = PaymentSerializer
    http_method_names = ['get', 'head', 'options', 'post', 'patch']  # delete/put yo'q
    filterset_fields = ['status', 'is_discounted']
    search_fields = ['user__full_name', 'user__username', 'user__user_id']
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """To'lovni atomik tasdiqlash: status re-check + select_for_update + premium uzaytirish."""
        note = f"Dashboard: {request.user.username}"
        with transaction.atomic():
            try:
                payment = (Payment.objects.select_for_update()
                           .select_related('tariff', 'user').get(pk=pk))
            except Payment.DoesNotExist:
                return Response({'result': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

            if payment.status != 'pending':
                return Response({'result': 'already', 'status': payment.status},
                                status=status.HTTP_409_CONFLICT)
            if payment.tariff is None:
                return Response({'result': 'no_tariff'}, status=status.HTTP_400_BAD_REQUEST)

            days = payment.tariff.days
            payment.status = 'approved'
            payment.approved_at = timezone.now()
            payment.admin_note = note
            payment.save(update_fields=['status', 'approved_at', 'admin_note'])

            user = User.objects.select_for_update().get(pk=payment.user_id)
            now = timezone.now()
            base = user.premium_expires if (user.premium_expires and user.premium_expires > now) else now
            user.is_premium = True
            user.premium_expires = base + timedelta(days=days)
            user.premium_expiry_notified = False
            user.save(update_fields=['is_premium', 'premium_expires', 'premium_expiry_notified'])
            user_telegram_id = user.user_id

        # commit'dan keyin - bot jarayoniga xabar (in-process signal ham 'user' chiqaradi)
        publish_invalidation('user', id=user_telegram_id)
        payment.refresh_from_db()
        return Response(self.get_serializer(payment).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        with transaction.atomic():
            try:
                payment = Payment.objects.select_for_update().select_related('user').get(pk=pk)
            except Payment.DoesNotExist:
                return Response({'result': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
            if payment.status != 'pending':
                return Response({'result': 'already', 'status': payment.status},
                                status=status.HTTP_409_CONFLICT)
            payment.status = 'rejected'
            payment.admin_note = f"Dashboard: {request.user.username}"
            payment.save(update_fields=['status', 'admin_note'])
        payment.refresh_from_db()
        return Response(self.get_serializer(payment).data)


# ---------------------------------------------------------------------------
# Bot settings (singleton, pk=1)
# ---------------------------------------------------------------------------
class BotSettingsView(RetrieveUpdateAPIView):
    """GET/PATCH /api/settings/ - yagona BotSettings. save() 'settings' invalidatsiya chiqaradi."""
    serializer_class = BotSettingsSerializer

    def get_object(self):
        return BotSettings.get_settings()


# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------
class MessageTemplateViewSet(viewsets.ModelViewSet):
    queryset = MessageTemplate.objects.all()
    serializer_class = MessageTemplateSerializer
    http_method_names = ['get', 'head', 'options', 'patch']  # faqat tahrirlash
    ordering = ['message_type']

    def list(self, request, *args, **kwargs):
        if not MessageTemplate.objects.exists():
            MessageTemplate.init_defaults()
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['post'])
    def seed(self, request):
        MessageTemplate.init_defaults()
        return Response({'detail': 'Standart shablonlar yaratildi.'})

    @action(detail=False, methods=['post'], url_path='reset-all')
    def reset_all(self, request):
        MessageTemplate.objects.all().delete()
        MessageTemplate.init_defaults()
        return Response({'detail': 'Barcha shablonlar standartga qaytarildi.'})


# ---------------------------------------------------------------------------
# Broadcasts - tarix + yuborish. Yaratilganda Redis orqali bot jarayoniga signal
# beriladi (bot/utils/cache_listener.py -> broadcast_sender.send_broadcast).
# ---------------------------------------------------------------------------
class BroadcastViewSet(viewsets.ModelViewSet):
    queryset = Broadcast.objects.all().select_related('sent_by')
    serializer_class = BroadcastSerializer
    http_method_names = ['get', 'head', 'options', 'post']  # list/retrieve/create
    filterset_fields = ['target', 'content_type', 'is_completed']
    ordering = ['-started_at']

    def create(self, request, *args, **kwargs):
        from apps.core.cache_bus import redis_enabled
        if not redis_enabled():
            return Response(
                {'detail': "Xabar yuborish uchun Redis va ishlab turgan bot jarayoni "
                           "kerak (USE_REDIS=True). Hozir mavjud emas."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        obj = serializer.save()
        # bot jarayoniga "shu broadcast'ni yubor" signalini beramiz
        publish_invalidation('broadcast', id=obj.id)


# ---------------------------------------------------------------------------
# Statistika
# ---------------------------------------------------------------------------
class StatsView(APIView):
    def get(self, request):
        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        users = User.objects.all()
        approved = Payment.objects.filter(status='approved')

        # Daromad: haqiqiy to'langan summa (amount). Tariff price emas.
        revenue_total = approved.aggregate(s=Sum('amount'))['s'] or 0
        revenue_30d = approved.filter(approved_at__gte=month_ago).aggregate(s=Sum('amount'))['s'] or 0

        # So'nggi 14 kunlik yangi userlar (grafik uchun)
        daily = []
        for i in range(13, -1, -1):
            day = today - timedelta(days=i)
            count = users.filter(created_at__date=day).count()
            daily.append({'date': day.isoformat(), 'count': count})

        data = {
            'users': {
                'total': users.count(),
                'today': users.filter(created_at__date=today).count(),
                'week': users.filter(created_at__gte=week_ago).count(),
                'month': users.filter(created_at__gte=month_ago).count(),
                'active_24h': users.filter(last_active__gte=now - timedelta(hours=24)).count(),
                'premium': users.filter(is_premium=True, premium_expires__gt=now).count(),
                'trial': users.filter(free_trial_expires__gt=now, is_premium=False).count(),
                'banned': users.filter(is_banned=True).count(),
            },
            'movies': {
                'total': Movie.objects.count(),
                'active': Movie.objects.filter(is_active=True).count(),
                'premium': Movie.objects.filter(is_premium=True).count(),
                'total_views': Movie.objects.aggregate(s=Sum('views'))['s'] or 0,
            },
            'payments': {
                'pending': Payment.objects.filter(status='pending').count(),
                'approved': approved.count(),
                'rejected': Payment.objects.filter(status='rejected').count(),
                'revenue_total': revenue_total,
                'revenue_30d': revenue_30d,
            },
            'channels': {
                'total': Channel.objects.count(),
                'active': Channel.objects.filter(is_active=True).count(),
            },
            'daily_new_users': daily,
        }
        return Response(data)
