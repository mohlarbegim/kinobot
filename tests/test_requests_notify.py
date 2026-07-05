"""
Tests for user MOVIE REQUESTS and NEW-MOVIE NOTIFICATION helpers.

Covers:
  - bot.handlers.user.create_movie_request
  - bot.handlers.admin.get_pending_requests
  - bot.handlers.admin.mark_request_done
  - bot.handlers.admin.count_active_users
  - bot.handlers.admin.get_active_user_ids

All target functions are @sync_to_async, so the underlying sync callable is
invoked via `.func(...)` (see tests/test_payments.py for the pattern).
"""
import pytest
from datetime import timedelta
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture
def movie_request_model():
    from apps.movies.models import MovieRequest
    return MovieRequest


# ==================== create_movie_request ====================

class TestCreateMovieRequest:
    """bot.handlers.user.create_movie_request"""

    def test_creates_pending_row_for_existing_user(self, db_user, movie_request_model):
        """Mavjud user uchun 'pending' so'rov yaratiladi."""
        from bot.handlers.user import create_movie_request

        req = create_movie_request.func(db_user.user_id, 'Interstellar')

        assert req is not None
        assert req.pk is not None
        # req.user_id — bu FK ustuni (User.pk), Telegram user_id emas
        assert req.user_id == db_user.pk
        assert req.user.user_id == db_user.user_id
        assert req.title == 'Interstellar'
        assert req.status == 'pending'  # default
        # DB da haqiqatan saqlangan
        assert movie_request_model.objects.filter(pk=req.pk, status='pending').exists()

    def test_returns_none_for_nonexistent_user(self, movie_request_model):
        """Mavjud bo'lmagan user_id -> None qaytadi, hech nima saqlanmaydi."""
        from bot.handlers.user import create_movie_request

        before = movie_request_model.objects.count()
        result = create_movie_request.func(999_000_111, 'Ghost Movie')

        assert result is None
        assert movie_request_model.objects.count() == before

    def test_title_truncated_to_255(self, db_user):
        """255 dan uzun nom 255 belgigacha qisqartiriladi."""
        from bot.handlers.user import create_movie_request

        long_title = 'x' * 300
        req = create_movie_request.func(db_user.user_id, long_title)

        assert req is not None
        assert len(req.title) == 255
        assert req.title == 'x' * 255
        # DB dan qayta o'qiganda ham 255
        req.refresh_from_db()
        assert len(req.title) == 255


# ==================== get_pending_requests / mark_request_done ====================

class TestPendingRequests:
    """bot.handlers.admin.get_pending_requests + mark_request_done"""

    def test_returns_only_pending(self, db_user):
        """get_pending_requests faqat 'pending' larni qaytaradi ('done' chiqarib tashlanadi)."""
        from bot.handlers.user import create_movie_request
        from bot.handlers.admin import get_pending_requests, mark_request_done

        keep = create_movie_request.func(db_user.user_id, 'Keep Pending')
        done = create_movie_request.func(db_user.user_id, 'Mark Done')

        # birini 'done' qilamiz
        mark_request_done.func(done.pk)

        pending = get_pending_requests.func()
        pending_ids = [r.pk for r in pending]

        assert keep.pk in pending_ids
        assert done.pk not in pending_ids
        assert all(r.status == 'pending' for r in pending)

    def test_ordering_newest_first(self, db_user, movie_request_model):
        """So'rovlar eng yangisidan boshlab (-created_at) tartiblanadi."""
        from bot.handlers.user import create_movie_request
        from bot.handlers.admin import get_pending_requests

        older = create_movie_request.func(db_user.user_id, 'Older Request')
        newer = create_movie_request.func(db_user.user_id, 'Newer Request')

        # created_at auto_now_add — determinizm uchun aniq vaqt beramiz
        now = timezone.now()
        movie_request_model.objects.filter(pk=older.pk).update(
            created_at=now - timedelta(hours=2)
        )
        movie_request_model.objects.filter(pk=newer.pk).update(
            created_at=now
        )

        pending = get_pending_requests.func()
        pending_ids = [r.pk for r in pending]

        # yangisi ro'yxatda oldinroq turadi
        assert pending_ids.index(newer.pk) < pending_ids.index(older.pk)
        assert pending_ids[0] == newer.pk

    def test_mark_request_done_flips_status(self, db_user, movie_request_model):
        """mark_request_done statusni 'done' ga o'zgartiradi va pending ro'yxatidan chiqaradi."""
        from bot.handlers.user import create_movie_request
        from bot.handlers.admin import get_pending_requests, mark_request_done

        req = create_movie_request.func(db_user.user_id, 'To Be Done')
        assert req.status == 'pending'

        mark_request_done.func(req.pk)

        req.refresh_from_db()
        assert req.status == 'done'

        pending_ids = [r.pk for r in get_pending_requests.func()]
        assert req.pk not in pending_ids


# ==================== count_active_users / get_active_user_ids ====================

class TestActiveUsers:
    """bot.handlers.admin.count_active_users + get_active_user_ids"""

    def test_count_active_users_excludes_banned(self, user_model):
        """count_active_users bloklangan userlarni sanamaydi."""
        from bot.handlers.admin import count_active_users

        baseline = count_active_users.func()

        normal = user_model.objects.create(user_id=555001, full_name='Normal One')
        banned = user_model.objects.create(
            user_id=555002, full_name='Banned One', is_banned=True
        )

        after = count_active_users.func()

        # faqat bloklanmagan yangi user hisobga qo'shildi (banned emas)
        assert after == baseline + 1

        # aniqlik uchun: banned=True qilinsa sanoq kamayadi
        normal.is_banned = True
        normal.save()
        assert count_active_users.func() == baseline

    def test_get_active_user_ids_excludes_banned(self, user_model):
        """get_active_user_ids bloklangan user_id ni ro'yxatga kiritmaydi."""
        from bot.handlers.admin import get_active_user_ids

        normal = user_model.objects.create(user_id=555101, full_name='Normal Two')
        banned = user_model.objects.create(
            user_id=555102, full_name='Banned Two', is_banned=True
        )

        ids = get_active_user_ids.func()

        assert isinstance(ids, list)
        assert normal.user_id in ids
        assert banned.user_id not in ids
        # hammasi int
        assert all(isinstance(i, int) for i in ids)

    def test_db_user_is_active(self, db_user):
        """Standart (bloklanmagan) fixture user faol deb hisoblanadi."""
        from bot.handlers.admin import count_active_users, get_active_user_ids

        assert db_user.is_banned is False
        assert db_user.user_id in get_active_user_ids.func()
        assert count_active_users.func() >= 1
