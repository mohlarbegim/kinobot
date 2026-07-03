from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register('users', views.UserViewSet)
router.register('admins', views.AdminViewSet)
router.register('categories', views.CategoryViewSet)
router.register('movies', views.MovieViewSet)
router.register('channels', views.ChannelViewSet)
router.register('tariffs', views.TariffViewSet)
router.register('payments', views.PaymentViewSet)
router.register('message-templates', views.MessageTemplateViewSet)
router.register('broadcasts', views.BroadcastViewSet)

urlpatterns = [
    # Auth
    path('auth/login/', views.StaffTokenObtainPairView.as_view(), name='api_login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='api_refresh'),
    path('auth/me/', views.me, name='api_me'),

    # Singleton + stats
    path('settings/', views.BotSettingsView.as_view(), name='api_settings'),
    path('stats/', views.StatsView.as_view(), name='api_stats'),

    # Broadcast media yuklash (Telegram file_id oladi)
    path('upload-media/', views.upload_media, name='api_upload_media'),

    # Router (CRUD + custom actions)
    path('', include(router.urls)),
]
