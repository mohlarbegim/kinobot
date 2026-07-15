"""
Ko'p janr (M2M) testlari.

Bitta kinoda 2-3 janr bo'lishi mumkin (romantik + melodrama + jangari).
Eski `category` FK ATAYLAB saqlanmoqda (web panel/API o'qiydi) - shuning uchun
bot yozganda ikkalasi ham yangilanishini tekshiramiz.
"""
import pytest
from asgiref.sync import sync_to_async
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.django_db


def _cat(category_model, name, slug):
    return category_model.objects.create(name=name, slug=slug, is_active=True)


# ==================== Model ====================

class TestMovieGenreProperties:

    def test_genres_display_joins_multiple(self, movie_model, category_model):
        m = movie_model.objects.create(code='60001', title='Ko`p janr', is_active=True)
        c1 = _cat(category_model, 'Romantik', 'romantik-1')
        c2 = _cat(category_model, 'Jangari', 'jangari-1')
        m.categories.set([c1.id, c2.id])

        assert set(m.genre_list) == {'Romantik', 'Jangari'}
        assert ' | ' in m.genres_display

    def test_falls_back_to_old_fk(self, movie_model, category_model):
        """M2M bo'sh, eski FK bor -> janr baribir ko'rinadi (migratsiyagacha qo'shilgan kino)."""
        c = _cat(category_model, 'Drama', 'drama-1')
        m = movie_model.objects.create(code='60002', title='Eski', is_active=True, category=c)

        assert m.genre_list == ['Drama']
        assert m.genres_display == 'Drama'

    def test_no_genre_returns_empty(self, movie_model):
        m = movie_model.objects.create(code='60003', title='Janrsiz', is_active=True)
        assert m.genre_list == []
        assert m.genres_display == ''

    def test_m2m_wins_over_fk(self, movie_model, category_model):
        """M2M to'la bo'lsa - FK emas, M2M ko'rsatiladi."""
        old = _cat(category_model, 'Eski', 'eski-1')
        new1 = _cat(category_model, 'Yangi1', 'yangi1-1')
        new2 = _cat(category_model, 'Yangi2', 'yangi2-1')
        m = movie_model.objects.create(code='60004', title='X', is_active=True, category=old)
        m.categories.set([new1.id, new2.id])

        assert set(m.genre_list) == {'Yangi1', 'Yangi2'}
        assert 'Eski' not in m.genres_display


# ==================== create_movie ====================

class TestCreateMovieMultiGenre:

    def test_creates_with_multiple_genres(self, movie_model, category_model):
        from bot.handlers.admin import create_movie
        c1 = _cat(category_model, 'Romantik', 'romantik-2')
        c2 = _cat(category_model, 'Melodrama', 'melodrama-2')
        c3 = _cat(category_model, 'Jangari', 'jangari-2')

        movie = create_movie.func(
            code='60010', title='Uch janr', file_id='V',
            category_ids=[c1.id, c2.id, c3.id],
            year=2024, country='usa', quality='720p', language='uzbek',
            description='', is_premium=False, added_by_id=None,
        )

        assert movie.categories.count() == 3
        assert set(movie.genre_list) == {'Romantik', 'Melodrama', 'Jangari'}

    def test_first_genre_also_written_to_old_fk(self, movie_model, category_model):
        """Web panel/API hozircha FK o'qiydi - u bo'sh qolmasligi kerak."""
        from bot.handlers.admin import create_movie
        c1 = _cat(category_model, 'Birinchi', 'birinchi-2')
        c2 = _cat(category_model, 'Ikkinchi', 'ikkinchi-2')

        movie = create_movie.func(
            code='60011', title='FK sinov', file_id='V',
            category_ids=[c1.id, c2.id],
            year=None, country='usa', quality='720p', language='uzbek',
            description='', is_premium=False, added_by_id=None,
        )

        assert movie.category_id == c1.id  # birinchi tanlangan

    def test_no_genres_leaves_fk_null(self, movie_model):
        from bot.handlers.admin import create_movie
        movie = create_movie.func(
            code='60012', title='Janrsiz', file_id='V', category_ids=[],
            year=None, country='usa', quality='720p', language='uzbek',
            description='', is_premium=False, added_by_id=None,
        )
        assert movie.category_id is None
        assert movie.categories.count() == 0


# ==================== set_movie_categories (tahrirlash) ====================

class TestSetMovieCategories:

    def test_sets_multiple_and_syncs_fk(self, movie_model, category_model):
        from bot.handlers.admin import set_movie_categories
        c1 = _cat(category_model, 'A', 'a-3')
        c2 = _cat(category_model, 'B', 'b-3')
        movie_model.objects.create(code='60020', title='T', is_active=True)

        movie, err = set_movie_categories.func('60020', [c1.id, c2.id])

        assert err is None
        assert movie.categories.count() == 2
        assert movie.category_id == c1.id

    def test_clearing_genres_clears_fk_too(self, movie_model, category_model):
        from bot.handlers.admin import set_movie_categories
        c = _cat(category_model, 'A', 'a-4')
        m = movie_model.objects.create(code='60021', title='T', is_active=True, category=c)
        m.categories.set([c.id])

        movie, err = set_movie_categories.func('60021', [])

        assert err is None
        assert movie.categories.count() == 0
        assert movie.category_id is None  # FK ham tozalandi

    def test_replaces_not_appends(self, movie_model, category_model):
        from bot.handlers.admin import set_movie_categories
        c1 = _cat(category_model, 'A', 'a-5')
        c2 = _cat(category_model, 'B', 'b-5')
        m = movie_model.objects.create(code='60022', title='T', is_active=True)
        m.categories.set([c1.id])

        movie, _ = set_movie_categories.func('60022', [c2.id])

        assert [c.id for c in movie.categories.all()] == [c2.id]

    def test_missing_movie_returns_error(self):
        from bot.handlers.admin import set_movie_categories
        movie, err = set_movie_categories.func('99999999', [])
        assert movie is None
        assert err == 'not_found'


# ==================== get_movie_category_ids ====================

class TestGetMovieCategoryIds:

    def test_returns_m2m_ids(self, movie_model, category_model):
        from bot.handlers.admin import get_movie_category_ids
        c1 = _cat(category_model, 'A', 'a-6')
        c2 = _cat(category_model, 'B', 'b-6')
        m = movie_model.objects.create(code='60030', title='T', is_active=True)
        m.categories.set([c1.id, c2.id])

        assert set(get_movie_category_ids.func(m.id)) == {c1.id, c2.id}

    def test_falls_back_to_fk(self, movie_model, category_model):
        """Tahrirlashда eski kino ochilsa - hozirgi janri belgilangan chiqishi kerak."""
        from bot.handlers.admin import get_movie_category_ids
        c = _cat(category_model, 'Eski', 'eski-6')
        m = movie_model.objects.create(code='60031', title='T', is_active=True, category=c)

        assert get_movie_category_ids.func(m.id) == [c.id]


# ==================== Foydalanuvchi filtri ====================

class TestCategoryFilter:

    def test_finds_by_m2m(self, movie_model, category_model):
        from bot.handlers.user import get_movies_by_category
        c = _cat(category_model, 'Jangari', 'jangari-7')
        m = movie_model.objects.create(code='60040', title='M2M kino', is_active=True)
        m.categories.set([c.id])

        movies, pages, name = get_movies_by_category.func(c.id)

        assert [x.code for x in movies] == ['60040']
        assert name == 'Jangari'

    def test_finds_by_old_fk(self, movie_model, category_model):
        """Migratsiyaga tushmagan eski kino ham filtrda chiqishi kerak."""
        from bot.handlers.user import get_movies_by_category
        c = _cat(category_model, 'Drama', 'drama-7')
        movie_model.objects.create(code='60041', title='FK kino', is_active=True, category=c)

        movies, pages, name = get_movies_by_category.func(c.id)

        assert [x.code for x in movies] == ['60041']

    def test_no_duplicates_when_both_set(self, movie_model, category_model):
        """MUHIM: FK ham M2M ham bir xil janr -> kino IKKI marta qaytmasligi kerak."""
        from bot.handlers.user import get_movies_by_category
        c = _cat(category_model, 'Triller', 'triller-7')
        m = movie_model.objects.create(code='60042', title='Ikkala', is_active=True, category=c)
        m.categories.set([c.id])

        movies, total_pages, _ = get_movies_by_category.func(c.id)

        assert len(movies) == 1  # .distinct() ishladi
        assert total_pages == 1

    def test_multi_genre_movie_found_by_each_genre(self, movie_model, category_model):
        """Ko'p janrli kino HAR BIR janri bo'yicha topilishi kerak."""
        from bot.handlers.user import get_movies_by_category
        c1 = _cat(category_model, 'Romantik', 'romantik-8')
        c2 = _cat(category_model, 'Melodrama', 'melodrama-8')
        m = movie_model.objects.create(code='60043', title='Ikki janr', is_active=True)
        m.categories.set([c1.id, c2.id])

        by_first, _, _ = get_movies_by_category.func(c1.id)
        by_second, _, _ = get_movies_by_category.func(c2.id)

        assert [x.code for x in by_first] == ['60043']
        assert [x.code for x in by_second] == ['60043']

    def test_inactive_movie_excluded(self, movie_model, category_model):
        from bot.handlers.user import get_movies_by_category
        c = _cat(category_model, 'X', 'x-9')
        m = movie_model.objects.create(code='60044', title='O`chiq', is_active=False)
        m.categories.set([c.id])

        movies, _, _ = get_movies_by_category.func(c.id)

        assert movies == []


# ==================== Klaviatura (toggle) ====================

class TestAdminCategoriesKb:

    def test_selected_marked_with_check(self, category_model):
        from bot.keyboards import admin_categories_kb
        c1 = _cat(category_model, 'A', 'a-10')
        c2 = _cat(category_model, 'B', 'b-10')

        kb = admin_categories_kb([c1, c2], selected=[c1.id])
        texts = [b.text for row in kb.inline_keyboard for b in row]

        assert any(t.startswith('✅') and 'A' in t for t in texts)
        assert not any(t.startswith('✅') and 'B' in t for t in texts)

    def test_done_button_only_when_selected(self, category_model):
        """Hech narsa tanlanmagan bo'lsa "Tayyor" tugmasi ko'rinmasligi kerak."""
        from bot.keyboards import admin_categories_kb
        c = _cat(category_model, 'A', 'a-11')

        empty = admin_categories_kb([c], selected=[])
        filled = admin_categories_kb([c], selected=[c.id])

        empty_datas = [b.callback_data for row in empty.inline_keyboard for b in row]
        filled_datas = [b.callback_data for row in filled.inline_keyboard for b in row]

        assert 'admin_category:done' not in empty_datas
        assert 'admin_category:done' in filled_datas

    def test_skip_always_present(self, category_model):
        from bot.keyboards import admin_categories_kb
        c = _cat(category_model, 'A', 'a-12')
        kb = admin_categories_kb([c], selected=[])
        datas = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert 'admin_category:skip' in datas

    def test_medit_kb_has_save_and_none(self, category_model):
        from bot.keyboards import medit_categories_kb
        c = _cat(category_model, 'A', 'a-13')
        kb = medit_categories_kb([c], selected=[c.id])
        datas = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert 'medit_cat:save' in datas
        assert 'medit_cat:none' in datas


# ==================== Toggle handler ====================

class TestAddMovieCategoryToggle:

    async def test_toggle_adds_then_removes(self, category_model, monkeypatch):
        """Janr tugmasi ikki marta bosilsa - tanlanadi, keyin bekor bo'ladi."""
        import bot.handlers.admin as a
        c = await sync_to_async(_cat)(category_model, 'A', 'a-14')

        monkeypatch.setattr(a, 'get_categories', AsyncMock(return_value=[c]))

        stored = {'category_ids': []}
        state = AsyncMock()
        state.get_data = AsyncMock(side_effect=lambda: dict(stored))
        state.update_data = AsyncMock(side_effect=lambda **kw: stored.update(kw))

        cb = AsyncMock()
        cb.data = f'admin_category:{c.id}'
        cb.message = AsyncMock()

        await a.add_movie_category(cb, state)
        assert stored['category_ids'] == [c.id]      # tanlandi

        await a.add_movie_category(cb, state)
        assert stored['category_ids'] == []          # bekor qilindi

    async def test_toggle_does_not_advance_state(self, category_model, monkeypatch):
        """Janr bosilganda keyingi qadamga O'TMASLIGI kerak (yana tanlash mumkin)."""
        import bot.handlers.admin as a
        c = await sync_to_async(_cat)(category_model, 'A', 'a-15')
        monkeypatch.setattr(a, 'get_categories', AsyncMock(return_value=[c]))

        stored = {'category_ids': []}
        state = AsyncMock()
        state.get_data = AsyncMock(side_effect=lambda: dict(stored))
        state.update_data = AsyncMock(side_effect=lambda **kw: stored.update(kw))

        cb = AsyncMock()
        cb.data = f'admin_category:{c.id}'
        cb.message = AsyncMock()

        await a.add_movie_category(cb, state)

        state.set_state.assert_not_awaited()  # qadam tugamadi

    async def test_done_advances_to_year(self, category_model, monkeypatch):
        import bot.handlers.admin as a
        from bot.states import AddMovieState
        c = await sync_to_async(_cat)(category_model, 'A', 'a-16')
        monkeypatch.setattr(a, 'get_categories', AsyncMock(return_value=[c]))

        stored = {'category_ids': [c.id], 'code': '1', 'title': 'T'}
        state = AsyncMock()
        state.get_data = AsyncMock(side_effect=lambda: dict(stored))
        state.update_data = AsyncMock(side_effect=lambda **kw: stored.update(kw))

        cb = AsyncMock()
        cb.data = 'admin_category:done'
        cb.message = AsyncMock()

        await a.add_movie_category(cb, state)

        state.set_state.assert_awaited_once_with(AddMovieState.year)

    async def test_skip_clears_selection(self, category_model, monkeypatch):
        import bot.handlers.admin as a
        c = await sync_to_async(_cat)(category_model, 'A', 'a-17')
        monkeypatch.setattr(a, 'get_categories', AsyncMock(return_value=[c]))

        stored = {'category_ids': [c.id], 'code': '1', 'title': 'T'}
        state = AsyncMock()
        state.get_data = AsyncMock(side_effect=lambda: dict(stored))
        state.update_data = AsyncMock(side_effect=lambda **kw: stored.update(kw))

        cb = AsyncMock()
        cb.data = 'admin_category:skip'
        cb.message = AsyncMock()

        await a.add_movie_category(cb, state)

        assert stored['category_ids'] == []
