"""
Mavjud kinolarning `category` (FK) qiymatini `categories` (M2M) ga ko'chirish.

XAVFSIZLIK: bu migratsiya FK'ni O'CHIRMAYDI - faqat nusxalaydi. Shu tufayli:
  - eski kod (FK o'qiydigan) ishlashda davom etadi,
  - rollback (reverse) ham to'liq ishlaydi.

Idempotent: qayta ishga tushsa dublikat yaratmaydi (M2M .add() takrorlanmaydi).
"""
from django.db import migrations


def copy_fk_to_m2m(apps, schema_editor):
    """category -> categories (oldinga)."""
    Movie = apps.get_model('movies', 'Movie')

    # Faqat janri bor kinolar. .iterator() - katta bazada xotirani yemasligi uchun.
    qs = Movie.objects.filter(category__isnull=False).only('id', 'category_id')
    for movie in qs.iterator(chunk_size=500):
        movie.categories.add(movie.category_id)


def copy_m2m_to_fk(apps, schema_editor):
    """categories -> category (orqaga / rollback).

    FK bitta qiymat oladi - birinchi janrni yozamiz. Rollback'da ko'p janrli
    kinoda qolgan janrlar yo'qoladi (FK'ning tabiiy cheklovi), lekin kino
    janrsiz qolmaydi.
    """
    Movie = apps.get_model('movies', 'Movie')

    for movie in Movie.objects.prefetch_related('categories').iterator(chunk_size=500):
        if movie.category_id:
            continue  # FK allaqachon to'la
        first = movie.categories.first()
        if first:
            movie.category_id = first.id
            movie.save(update_fields=['category'])


class Migration(migrations.Migration):

    dependencies = [
        ('movies', '0005_add_movie_categories_m2m'),
    ]

    operations = [
        migrations.RunPython(copy_fk_to_m2m, copy_m2m_to_fk),
    ]
