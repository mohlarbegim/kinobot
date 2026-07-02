"""
Kanal o'zgarganda bot jarayonining kanal/obuna cache'ini tozalash uchun signal.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.core.cache_bus import publish_invalidation
from .models import Channel


@receiver(post_save, sender=Channel)
@receiver(post_delete, sender=Channel)
def _channel_changed(sender, instance, **kwargs):
    publish_invalidation('channels')
