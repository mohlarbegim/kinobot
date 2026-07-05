"""
Like (yoqtirish) va Ko'rish tarixi (WatchHistory) testlari — KinoBot

Yangi qo'shilgan ikki funksionallikni tekshiradi:
  1) Kino LIKE (toggle) — MovieLike + Movie.likes hisoblagichi
  2) Ko'rish TARIXI — WatchHistory upsert, tartib, pagination

DB helperlari `bot.handlers.user` ichida @sync_to_async bilan o'ralgan,
shuning uchun testlarda sync asl funksiya `.func(...)` orqali chaqiriladi
(test_payments.py dagi approve_payment.func(...) uslubi kabi).
"""
import time
import pytest
from datetime import timedelta
from django.utils import timezone

pytestmark = pytest.mark.django_db

from bot.handlers.user import (
    toggle_movie_like,
    check_movie_liked,
    get_movie_action_state,
    record_watch,
    get_watch_history,
    get_top_movies,
)
from bot.keyboards import movie_action_kb


# ==================== LIKE (toggle) ====================

class TestMovieLike:
    """toggle_movie_like / check_movie_liked xatti-harakati."""

    def test_like_then_unlike_counter_and_flag(self, db_user, db_movie):
        """0 -> 1 -> 0: hisoblagich va liked bayrog'i almashadi."""
        assert db_movie.likes == 0

        # Birinchi bosish -> yoqtirdi
        liked, likes = toggle_movie_like.func(db_user.user_id, db_movie.code)
        assert liked is True
        assert likes == 1

        db_movie.refresh_from_db()
        assert db_movie.likes == 1

        # Ikkinchi bosish -> yoqtirishни bekor qildi
        liked, likes = toggle_movie_like.func(db_user.user_id, db_movie.code)
        assert liked is False
        assert likes == 0

        db_movie.refresh_from_db()
        assert db_movie.likes == 0

    def test_toggle_idempotency_returns_to_start(self, db_user, db_movie):
        """Ikki marta bosish boshlang'ich holatga qaytaradi (MovieLike qolmaydi)."""
        from apps.movies.models import MovieLike

        toggle_movie_like.func(db_user.user_id, db_movie.code)
        toggle_movie_like.func(db_user.user_id, db_movie.code)

        db_movie.refresh_from_db()
        assert db_movie.likes == 0
        assert MovieLike.objects.filter(user=db_user, movie=db_movie).count() == 0

    def test_like_creates_single_row(self, db_user, db_movie):
        """Bir marta yoqtirish -> aynan bitta MovieLike yozuvi."""
        from apps.movies.models import MovieLike

        toggle_movie_like.func(db_user.user_id, db_movie.code)
        assert MovieLike.objects.filter(user=db_user, movie=db_movie).count() == 1

    def test_toggle_missing_movie_returns_none_zero(self, db_user):
        """Mavjud bo'lmagan kino -> (None, 0)."""
        liked, likes = toggle_movie_like.func(db_user.user_id, "0000000")
        assert liked is None
        assert likes == 0

    def test_toggle_missing_user_returns_none_zero(self, db_movie):
        """Mavjud bo'lmagan user -> (None, 0)."""
        liked, likes = toggle_movie_like.func(999000111, db_movie.code)
        assert liked is None
        assert likes == 0

    def test_check_movie_liked_reflects_state(self, db_user, db_movie):
        """check_movie_liked joriy holatni to'g'ri qaytaradi."""
        assert check_movie_liked.func(db_user.user_id, db_movie.code) is False

        toggle_movie_like.func(db_user.user_id, db_movie.code)
        assert check_movie_liked.func(db_user.user_id, db_movie.code) is True

        toggle_movie_like.func(db_user.user_id, db_movie.code)
        assert check_movie_liked.func(db_user.user_id, db_movie.code) is False

    def test_likes_never_goes_negative(self, user_model, movie_model):
        """likes=0 bo'lganda yoqtirishni bekor qilish 0 dan pastga tushirmaydi."""
        from apps.movies.models import MovieLike

        user = user_model.objects.create(user_id=700000201, full_name='Neg User')
        # likes=0 bo'lgan kino, lekin allaqachon MovieLike mavjud
        movie = movie_model.objects.create(code=70020, title='Neg Movie', likes=0)
        MovieLike.objects.create(user=user, movie=movie)

        # Toggle mavjud like'ni o'chiradi va kamaytirishga urinadi, lekin 0 da qoladi
        liked, likes = toggle_movie_like.func(user.user_id, movie.code)
        assert liked is False
        assert likes == 0

        movie.refresh_from_db()
        assert movie.likes == 0
        assert movie.likes >= 0


# ==================== get_movie_action_state ====================

class TestMovieActionState:
    """get_movie_action_state -> (likes, is_liked, is_saved) uchligi."""

    def test_state_default_triple(self, db_user, db_movie):
        """Hech narsa qilinmagan: (0, False, False)."""
        likes, is_liked, is_saved = get_movie_action_state.func(db_user.user_id, db_movie.code)
        assert likes == 0
        assert is_liked is False
        assert is_saved is False

    def test_state_after_like(self, db_user, db_movie):
        """Yoqtirgandan keyin: likes=1, is_liked=True, is_saved=False."""
        toggle_movie_like.func(db_user.user_id, db_movie.code)

        likes, is_liked, is_saved = get_movie_action_state.func(db_user.user_id, db_movie.code)
        assert likes == 1
        assert is_liked is True
        assert is_saved is False

    def test_state_reflects_saved(self, db_user, db_movie):
        """SavedMovie mavjud bo'lsa is_saved=True qaytadi."""
        from apps.movies.models import SavedMovie

        SavedMovie.objects.create(user=db_user, movie=db_movie)
        likes, is_liked, is_saved = get_movie_action_state.func(db_user.user_id, db_movie.code)
        assert is_saved is True
        assert is_liked is False

    def test_state_missing_movie(self, db_user):
        """Mavjud bo'lmagan kino: (0, False, False)."""
        likes, is_liked, is_saved = get_movie_action_state.func(db_user.user_id, "0000000")
        assert (likes, is_liked, is_saved) == (0, False, False)


# ==================== WATCH HISTORY ====================

class TestWatchHistory:
    """record_watch / get_watch_history."""

    def test_record_watch_creates_single_row(self, db_user, db_movie):
        """record_watch bitta WatchHistory yozuvi yaratadi."""
        from apps.movies.models import WatchHistory

        record_watch.func(db_user.user_id, db_movie.id)
        assert WatchHistory.objects.filter(user=db_user, movie=db_movie).count() == 1

    def test_rewatch_updates_timestamp_without_duplicate(self, db_user, db_movie):
        """Qayta ko'rish watched_at ni yangilaydi, dublikat qatordan yaratmaydi."""
        from apps.movies.models import WatchHistory

        record_watch.func(db_user.user_id, db_movie.id)
        first = WatchHistory.objects.get(user=db_user, movie=db_movie)
        first_ts = first.watched_at

        # auto_now aniq farqlanishi uchun kichik kutish
        time.sleep(0.05)

        record_watch.func(db_user.user_id, db_movie.id)

        # Dublikat yo'q — hisob 1 da qoladi
        assert WatchHistory.objects.filter(user=db_user, movie=db_movie).count() == 1

        second = WatchHistory.objects.get(user=db_user, movie=db_movie)
        assert second.watched_at > first_ts

    def test_record_watch_missing_user_noop(self, db_movie):
        """Mavjud bo'lmagan user -> hech qanday yozuv yaratilmaydi."""
        from apps.movies.models import WatchHistory

        record_watch.func(888000111, db_movie.id)
        assert WatchHistory.objects.filter(movie=db_movie).count() == 0

    def test_history_ordering_newest_first(self, user_model, movie_model):
        """get_watch_history eng oxirgi ko'rilganni birinchi qaytaradi."""
        from apps.movies.models import WatchHistory

        user = user_model.objects.create(user_id=700000301, full_name='Hist User')
        m_old = movie_model.objects.create(code=70031, title='Old')
        m_new = movie_model.objects.create(code=70032, title='New')

        record_watch.func(user.user_id, m_old.id)
        record_watch.func(user.user_id, m_new.id)

        base = timezone.now()
        # Aniq (deterministik) tartib uchun watched_at ni to'g'ridan-to'g'ri o'rnatamiz
        # (.update() auto_now ni chetlab o'tadi)
        WatchHistory.objects.filter(user=user, movie=m_old).update(watched_at=base - timedelta(minutes=5))
        WatchHistory.objects.filter(user=user, movie=m_new).update(watched_at=base)

        movies, total_pages = get_watch_history.func(user.user_id, page=1)
        assert total_pages == 1
        # code — CharField, DB dan string qaytadi -> str bilan solishtiramiz
        assert [str(m.code) for m in movies] == [str(m_new.code), str(m_old.code)]

    def test_history_pagination(self, user_model, movie_model):
        """8 dan ortiq ko'rish -> total_pages=2, sahifalar to'g'ri bo'linadi."""
        from apps.movies.models import WatchHistory

        user = user_model.objects.create(user_id=700000401, full_name='Page User')

        movies = []
        base = timezone.now()
        for i in range(9):  # 9 ta -> ceil(9/8) = 2 sahifa
            mv = movie_model.objects.create(code=70050 + i, title=f'M{i}')
            movies.append(mv)
            record_watch.func(user.user_id, mv.id)
            # i qancha katta bo'lsa, shuncha yangi (movies[8] eng yangi)
            WatchHistory.objects.filter(user=user, movie=mv).update(
                watched_at=base + timedelta(seconds=i)
            )

        page1, total_pages = get_watch_history.func(user.user_id, page=1)
        assert total_pages == 2
        assert len(page1) == 8
        # Eng yangi (movies[8]) birinchi, keyin kamayib boradi
        expected_page1 = [str(movies[i].code) for i in range(8, 0, -1)]
        assert [str(m.code) for m in page1] == expected_page1

        page2, total_pages2 = get_watch_history.func(user.user_id, page=2)
        assert total_pages2 == 2
        assert len(page2) == 1
        assert str(page2[0].code) == str(movies[0].code)


# ==================== TOP MOVIES ====================

class TestTopMovies:
    """get_top_movies -> avval -likes, keyin -views bo'yicha tartib."""

    def test_top_ordered_by_likes_then_views(self, movie_model):
        """likes teng bo'lsa views bo'yicha, aks holda likes bo'yicha kamayish tartibi."""
        a = movie_model.objects.create(code=70101, title='A', likes=5, views=1)
        b = movie_model.objects.create(code=70102, title='B', likes=5, views=10)
        c = movie_model.objects.create(code=70103, title='C', likes=10, views=0)

        top = get_top_movies.func(limit=50)
        codes = [str(m.code) for m in top]

        # Faqat shu testda yaratilgan kinolar tartibini tekshiramiz
        mine = {str(a.code), str(b.code), str(c.code)}
        my = [code for code in codes if code in mine]
        # C (likes=10) birinchi; keyin B (likes=5, views=10); keyin A (likes=5, views=1)
        assert my == [str(c.code), str(b.code), str(a.code)]

    def test_top_limit_respected(self, movie_model):
        """limit parametri qaytadigan ro'yxat uzunligini cheklaydi."""
        for i in range(5):
            movie_model.objects.create(code=70110 + i, title=f'T{i}', likes=i)

        top = get_top_movies.func(limit=3)
        assert len(top) == 3


# ==================== KEYBOARD ====================

class TestMovieActionKb:
    """movie_action_kb like tugmasi matni va callback_data."""

    def test_like_button_unliked_text(self):
        """is_liked=False -> '👍 {likes}' (belgisiz)."""
        kb = movie_action_kb("12345", is_saved=False, likes=7, is_liked=False)
        like_btn = kb.inline_keyboard[0][0]
        assert like_btn.text == "👍 7"
        assert like_btn.callback_data == "like:12345"

    def test_like_button_liked_text(self):
        """is_liked=True -> '👍 {likes} ✓' (belgi bilan)."""
        kb = movie_action_kb("12345", is_saved=False, likes=7, is_liked=True)
        like_btn = kb.inline_keyboard[0][0]
        assert like_btn.text == "👍 7 ✓"
        assert like_btn.callback_data == "like:12345"

    def test_like_button_zero_likes(self):
        """likes=0 standart holat matni."""
        kb = movie_action_kb("99999", likes=0, is_liked=False)
        like_btn = kb.inline_keyboard[0][0]
        assert like_btn.text == "👍 0"
