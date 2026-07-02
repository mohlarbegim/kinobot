"""
User o'zgarganda bot jarayonining in-process cache'ini tozalash uchun signal.

Django admin veb-panelida (gunicorn) yoki bot handlerlarida User saqlanganda, bot
jarayoniga Redis pub/sub orqali xabar yuboriladi. Shu tarzda ban/premium o'zgarishi
botga TTL (60s) kutmasdan yetadi.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.cache_bus import publish_invalidation
from .models import User

# Bot cache'i uchun ahamiyatli (xavfsizlik/kirish) maydonlar
_RELEVANT_FIELDS = {'is_banned', 'ban_reason', 'is_premium', 'premium_expires'}


@receiver(post_save, sender=User)
def _user_post_save(sender, instance, created, update_fields=None, **kwargs):
    if created:
        return  # yangi user - hech qaysi cache'da yo'q
    # Faqat ahamiyatli maydon o'zgarganda publish qilamiz. Bu /start dagi
    # last_active/username yangilanishlarida ortiqcha xabar yuborilmasligini ta'minlaydi.
    if update_fields is None or (_RELEVANT_FIELDS & set(update_fields)):
        publish_invalidation('user', id=instance.user_id)
