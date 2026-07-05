"""
Nom bo'yicha (inline) qidirish testlari
"""
import pytest

pytestmark = pytest.mark.django_db


class TestInlineSearch:
    """bot.handlers.inline.search_movies_inline"""

    def _mk(self, movie_model, code, title='', title_uz='', is_active=True, file_id='V'):
        return movie_model.objects.create(
            code=code, title=title, title_uz=title_uz,
            is_active=is_active, file_id=file_id,
        )

    def test_match_by_title(self, movie_model):
        from bot.handlers.inline import search_movies_inline
        self._mk(movie_model, '81001', title='Avatar 2')
        codes = [m.code for m in search_movies_inline.func('avatar')]
        assert '81001' in codes

    def test_match_by_title_uz(self, movie_model):
        from bot.handlers.inline import search_movies_inline
        self._mk(movie_model, '81002', title='The Lion King', title_uz='Sher Qirol')
        codes = [m.code for m in search_movies_inline.func('sher')]
        assert '81002' in codes

    def test_case_insensitive_partial(self, movie_model):
        from bot.handlers.inline import search_movies_inline
        self._mk(movie_model, '81003', title='Interstellar')
        codes = [m.code for m in search_movies_inline.func('STELLA')]
        assert '81003' in codes

    def test_inactive_excluded(self, movie_model):
        from bot.handlers.inline import search_movies_inline
        self._mk(movie_model, '81004', title='Hidden Film', is_active=False)
        codes = [m.code for m in search_movies_inline.func('hidden')]
        assert '81004' not in codes

    def test_no_match(self, movie_model):
        from bot.handlers.inline import search_movies_inline
        results = search_movies_inline.func('zzz-nonexistent-qwerty')
        assert results == []

    def test_videoless_movie_still_found(self, movie_model):
        """Videosiz (poster) kino ham qidiruvда topiladi (natija turi handlerда hal bo'ladi)."""
        from bot.handlers.inline import search_movies_inline
        self._mk(movie_model, '81005', title='Poster Only', file_id='')
        codes = [m.code for m in search_movies_inline.func('poster only')]
        assert '81005' in codes
