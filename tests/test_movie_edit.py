"""
Kino tahrirlash (edit_movie_field) testlari
"""
import pytest

pytestmark = pytest.mark.django_db


class TestEditMovieField:
    """bot.handlers.admin.edit_movie_field DB helper"""

    def _make_movie(self, movie_model, code, **kwargs):
        return movie_model.objects.create(
            code=code,
            title=kwargs.pop('title', 'Film'),
            **kwargs
        )

    def test_edit_title(self, movie_model):
        from bot.handlers.admin import edit_movie_field
        self._make_movie(movie_model, '70001', title='Eski nom')

        movie, err = edit_movie_field.func('70001', 'title', 'Yangi nom')

        assert err is None
        assert movie is not None
        assert movie.title == 'Yangi nom'
        movie_model.objects.get(code='70001').title == 'Yangi nom'

    def test_edit_year(self, movie_model):
        from bot.handlers.admin import edit_movie_field
        self._make_movie(movie_model, '70002')

        movie, err = edit_movie_field.func('70002', 'year', 2021)

        assert err is None
        assert movie.year == 2021

    def test_edit_code_success(self, movie_model):
        from bot.handlers.admin import edit_movie_field
        self._make_movie(movie_model, '70003')

        movie, err = edit_movie_field.func('70003', 'code', '70099')

        assert err is None
        assert movie.code == '70099'
        assert movie_model.objects.filter(code='70099').exists()
        assert not movie_model.objects.filter(code='70003').exists()

    def test_edit_code_duplicate_rejected(self, movie_model):
        from bot.handlers.admin import edit_movie_field
        self._make_movie(movie_model, '70004')
        self._make_movie(movie_model, '70005')

        movie, err = edit_movie_field.func('70004', 'code', '70005')

        assert err == 'duplicate'
        assert movie is None
        # Kod o'zgarmagan bo'lishi kerak
        assert movie_model.objects.filter(code='70004').exists()

    def test_edit_category_set_and_clear(self, movie_model, category_model):
        from bot.handlers.admin import edit_movie_field
        self._make_movie(movie_model, '70006')
        cat = category_model.objects.create(name='Aksiya', slug='aksiya-70006')

        movie, err = edit_movie_field.func('70006', 'category_id', cat.id)
        assert err is None
        assert movie.category_id == cat.id

        movie, err = edit_movie_field.func('70006', 'category_id', None)
        assert err is None
        assert movie.category_id is None

    def test_edit_file_id(self, movie_model):
        from bot.handlers.admin import edit_movie_field
        self._make_movie(movie_model, '70007', file_id='')

        movie, err = edit_movie_field.func('70007', 'file_id', 'NEW_FILE_ID')
        assert err is None
        assert movie.file_id == 'NEW_FILE_ID'

    def test_edit_poster_thumbnail(self, movie_model):
        from bot.handlers.admin import edit_movie_field
        self._make_movie(movie_model, '70010', file_id='')

        movie, err = edit_movie_field.func('70010', 'thumbnail_file_id', 'POSTER_ID')
        assert err is None
        assert movie.thumbnail_file_id == 'POSTER_ID'
        assert movie_model.objects.get(code='70010').thumbnail_file_id == 'POSTER_ID'

    def test_edit_not_found(self, movie_model):
        from bot.handlers.admin import edit_movie_field
        movie, err = edit_movie_field.func('70999', 'title', 'X')
        assert err == 'not_found'
        assert movie is None

    def test_edit_disallowed_field(self, movie_model):
        from bot.handlers.admin import edit_movie_field
        self._make_movie(movie_model, '70008')
        # views kabi ruxsat berilmagan maydon yangilanmasligi kerak
        movie, err = edit_movie_field.func('70008', 'views', 999)
        assert err == 'not_found'
        assert movie is None


class TestCreateMoviePoster:
    """create_movie posterни (thumbnail_file_id) saqlashi"""

    def test_create_with_poster_no_video(self, movie_model, category_model):
        from bot.handlers.admin import create_movie
        movie = create_movie.func(
            code='70020', title='Poster kino', file_id='',
            thumbnail_file_id='POSTER_ABC', category_ids=[],
            year=None, country='usa', quality='720p', language='uzbek',
            description='', is_premium=False, added_by_id=None,
        )
        assert movie.file_id == ''
        assert movie.thumbnail_file_id == 'POSTER_ABC'
        # DB'da ham saqlangan
        assert movie_model.objects.get(code='70020').thumbnail_file_id == 'POSTER_ABC'

    def test_create_default_no_poster(self, movie_model):
        from bot.handlers.admin import create_movie
        movie = create_movie.func(
            code='70021', title='Video kino', file_id='VIDEO_XYZ',
            category_ids=[], year=None, country='usa', quality='720p',
            language='uzbek', description='', is_premium=False, added_by_id=None,
        )
        # thumbnail_file_id default bo'sh (ixtiyoriy argument)
        assert movie.thumbnail_file_id == ''
        assert movie.file_id == 'VIDEO_XYZ'
