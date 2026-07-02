from django.apps import AppConfig


class ChannelsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.channels'
    verbose_name = 'Kanallar'

    def ready(self):
        from . import signals  # noqa: F401  (signal receiverlarini ro'yxatga olish)
