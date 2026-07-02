from pathlib import Path

from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse, JsonResponse
from django.db import connection
import logging

logger = logging.getLogger(__name__)


def health_check(request):
    """Simple health check - database ga bog'liq emas"""
    return HttpResponse("ok", content_type="text/plain")


def health_check_db(request):
    """Database health check"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok", "database": "connected"})
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return JsonResponse({"status": "error", "database": str(e)}, status=503)


# React admin dashboard (Vite build) index.html'ini o'qib beruvchi view.
# Build fayllari `static/dashboard/` ga chiqadi, collectstatic ularni STATIC_ROOT ga
# ko'chiradi va whitenoise `/static/dashboard/...` da beradi. SPA marshrutlari
# (/dashboard/*) uchun har doim index.html qaytariladi.
_SPA_CANDIDATES = [
    Path(settings.STATIC_ROOT) / 'dashboard' / 'index.html',
    settings.BASE_DIR / 'static' / 'dashboard' / 'index.html',
]


def dashboard_spa(request, *args, **kwargs):
    for candidate in _SPA_CANDIDATES:
        try:
            if candidate.exists():
                return HttpResponse(candidate.read_text(encoding='utf-8'))
        except OSError:
            continue
    return HttpResponse(
        "<h1>Dashboard hali build qilinmagan</h1>"
        "<p>frontend/ papkasida <code>npm run build</code> ni ishga tushiring.</p>",
        status=503,
        content_type='text/html; charset=utf-8',
    )


urlpatterns = [
    path('health/', health_check, name='health'),
    path('health/db/', health_check_db, name='health_db'),

    # REST API (React dashboard)
    path('api/', include('apps.api.urls')),

    # Django admin (React tayyor bo'lgach o'chiriladi)
    path('admin/', admin.site.urls),

    # React SPA
    path('dashboard/', dashboard_spa, name='dashboard'),
    re_path(r'^dashboard/.*$', dashboard_spa),

    # Root -> health (Railway ichki tekshiruvi /health/ ishlatadi)
    path('', health_check, name='root_health'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
