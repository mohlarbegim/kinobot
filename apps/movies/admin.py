from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Movie


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'emoji', 'slug', 'order', 'is_active', 'movies_count']
    list_filter = ['is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order', 'name']

    @admin.display(description='Kinolar soni')
    def movies_count(self, obj):
        return obj.movies.count()


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ['code', 'title', 'category', 'country', 'quality', 'views', 'premium_badge', 'is_active']
    list_filter = ['category', 'country', 'quality', 'language', 'is_premium', 'is_active']
    search_fields = ['code', 'title', 'title_uz']
    readonly_fields = ['views', 'created_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Asosiy', {
            'fields': ('code', 'title', 'title_uz', 'category')
        }),
        ('Telegram', {
            'fields': ('file_id', 'thumbnail_file_id')
        }),
        ('Ma\'lumotlar', {
            'fields': ('year', 'duration', 'quality', 'language', 'country', 'description')
        }),
        ('Holat', {
            'fields': ('is_premium', 'is_active')
        }),
        ('Statistika', {
            'fields': ('views', 'created_at', 'added_by')
        }),
    )

    @admin.display(description='Premium')
    def premium_badge(self, obj):
        if obj.is_premium:
            return format_html('<span style="background-color: #ffc107; color: black; padding: 3px 8px; border-radius: 3px;">Premium</span>')
        return format_html('<span style="background-color: #6c757d; color: white; padding: 3px 8px; border-radius: 3px;">Oddiy</span>')
