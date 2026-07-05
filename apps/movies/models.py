from django.db import models


class Category(models.Model):
    """Kino kategoriyasi (janr)"""

    name = models.CharField(max_length=100, verbose_name='Nomi')
    emoji = models.CharField(max_length=10, blank=True, default='', verbose_name='Emoji')
    slug = models.SlugField(unique=True, verbose_name='Slug')
    order = models.PositiveIntegerField(default=0, verbose_name='Tartib')
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')

    class Meta:
        verbose_name = 'Kategoriya'
        verbose_name_plural = 'Kategoriyalar'
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.emoji} {self.name}" if self.emoji else self.name


class Movie(models.Model):
    """Kino modeli"""

    QUALITY_CHOICES = [
        ('360p', '360p'),
        ('480p', '480p'),
        ('720p', '720p HD'),
        ('1080p', '1080p Full HD'),
        ('4k', '4K Ultra HD'),
    ]

    LANGUAGE_CHOICES = [
        ('uzbek', "O'zbek tilida"),
        ('rus', 'Rus tilida'),
        ('eng', 'Ingliz tilida'),
        ('turk', 'Turk tilida'),
        ('korea', 'Koreys tilida'),
        ('other', 'Boshqa'),
    ]

    COUNTRY_CHOICES = [
        ('usa', '🇺🇸 AQSH'),
        ('korea', '🇰🇷 Janubiy Koreya'),
        ('india', '🇮🇳 Hindiston'),
        ('turkey', '🇹🇷 Turkiya'),
        ('russia', '🇷🇺 Rossiya'),
        ('uzbekistan', '🇺🇿 O\'zbekiston'),
        ('uk', '🇬🇧 Buyuk Britaniya'),
        ('france', '🇫🇷 Fransiya'),
        ('japan', '🇯🇵 Yaponiya'),
        ('china', '🇨🇳 Xitoy'),
        ('other', '🌍 Boshqa'),
    ]

    code = models.CharField(max_length=20, unique=True, verbose_name='Kino kodi')
    title = models.CharField(max_length=255, verbose_name='Nomi (original)')
    title_uz = models.CharField(max_length=255, blank=True, default='', verbose_name="Nomi (o'zbekcha)")

    # Telegram - ixtiyoriy: kino video'siz ham qo'shilishi mumkin (keyin yuklanadi)
    file_id = models.CharField(max_length=255, blank=True, default='', verbose_name='Telegram File ID')
    thumbnail_file_id = models.CharField(max_length=255, blank=True, default='', verbose_name='Thumbnail File ID')

    # Kategoriya
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='movies',
        verbose_name='Kategoriya'
    )

    # Ma'lumotlar
    year = models.PositiveIntegerField(blank=True, null=True, verbose_name='Yili')
    duration = models.PositiveIntegerField(blank=True, null=True, verbose_name='Davomiyligi (daqiqa)')
    quality = models.CharField(max_length=10, choices=QUALITY_CHOICES, default='720p', verbose_name='Sifati')
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='uzbek', verbose_name='Tili')
    country = models.CharField(max_length=20, choices=COUNTRY_CHOICES, default='usa', verbose_name='Davlati')
    description = models.TextField(blank=True, default='', verbose_name='Tavsif')

    # Premium
    is_premium = models.BooleanField(default=False, verbose_name='Premium kino')

    # Statistika
    views = models.PositiveIntegerField(default=0, verbose_name="Ko'rishlar soni")
    likes = models.PositiveIntegerField(default=0, verbose_name="Yoqtirishlar soni")

    # Holat
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')

    # Vaqtlar
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Qo'shilgan vaqt")
    added_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='added_movies',
        verbose_name="Kim qo'shgan"
    )

    class Meta:
        verbose_name = 'Kino'
        verbose_name_plural = 'Kinolar'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.code}] {self.title}"

    @property
    def display_title(self):
        """Ko'rsatiladigan nom"""
        return self.title_uz if self.title_uz else self.title

    def increment_views(self):
        """Ko'rishlar sonini oshirish"""
        self.views += 1
        self.save(update_fields=['views'])


class MovieLike(models.Model):
    """Kino yoqtirishlari (like) — har user bir kinoni bir marta yoqtiradi (toggle)."""

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='movie_likes',
        verbose_name='Foydalanuvchi'
    )
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='liked_by',
        verbose_name='Kino'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Yoqtirilgan vaqt')

    class Meta:
        verbose_name = 'Yoqtirish'
        verbose_name_plural = 'Yoqtirishlar'
        unique_together = ['user', 'movie']

    def __str__(self):
        return f"{self.user_id} ❤️ {self.movie_id}"


class WatchHistory(models.Model):
    """Ko'rish tarixi — foydalanuvchi ko'rgan kinolar (qayta ko'rilса vaqt yangilanadi)."""

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='watch_history',
        verbose_name='Foydalanuvchi'
    )
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='watched_by',
        verbose_name='Kino'
    )
    watched_at = models.DateTimeField(auto_now=True, verbose_name="Ko'rilgan vaqt")

    class Meta:
        verbose_name = 'Ko\'rish tarixi'
        verbose_name_plural = 'Ko\'rish tarixi'
        unique_together = ['user', 'movie']
        ordering = ['-watched_at']

    def __str__(self):
        return f"{self.user_id} 👁 {self.movie_id}"


class MovieRequest(models.Model):
    """Kino so'rovi — foydalanuvchi botда yo'q kinoni nomini so'raydi."""

    STATUS_CHOICES = [
        ('pending', 'Kutilmoqda'),
        ('done', 'Qo\'shildi'),
        ('rejected', 'Rad etildi'),
    ]

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='movie_requests',
        verbose_name='Foydalanuvchi'
    )
    title = models.CharField(max_length=255, verbose_name="So'ralgan kino")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='Holat')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="So'ralgan vaqt")

    class Meta:
        verbose_name = 'Kino so\'rovi'
        verbose_name_plural = 'Kino so\'rovlari'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


class SavedMovie(models.Model):
    """Saqlangan (sevimli) kinolar"""

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='saved_movies',
        verbose_name='Foydalanuvchi'
    )
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='saved_by',
        verbose_name='Kino'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Saqlangan vaqt')

    class Meta:
        verbose_name = 'Saqlangan kino'
        verbose_name_plural = 'Saqlangan kinolar'
        unique_together = ['user', 'movie']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.full_name} - {self.movie.title}"
