from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'
    verbose_name = 'Foydalanuvchilar'

    def ready(self):
        from . import signals  # noqa: F401  (signal receiverlarini ro'yxatga olish)
