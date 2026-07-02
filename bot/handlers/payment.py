import logging
from datetime import timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.conf import settings

from apps.users.models import User
from apps.payments.models import Tariff, Payment, PendingPaymentSession
from apps.core.models import BotSettings
from bot.keyboards import tariffs_kb, main_menu_inline_kb, payment_confirm_kb, back_kb
from bot.filters import CanManagePayments
from bot.utils import esc
from bot.middlewares.database import clear_user_cache

logger = logging.getLogger(__name__)

from bot.constants import PENDING_PAYMENT_TIMEOUT

router = Router()


# ==================== TARIF TANLASH ====================

@router.callback_query(F.data.startswith("tariff:"))
async def tariff_select_callback(callback: CallbackQuery, db_user: User = None, bot_settings: BotSettings = None):
    """Tarif tanlash"""
    parts = callback.data.split(":")
    tariff_id = int(parts[1])
    with_discount = parts[2] == "1"

    tariff = await get_tariff(tariff_id)

    if not tariff:
        await callback.answer("❌ Tarif topilmadi.", show_alert=True)
        return

    # Narxni hisoblash: chegirma faqat u haqiqatan ham asosiy narxdan KICHIK bo'lsa.
    # (is not None -> 0 so'm giveaway ham to'g'ri ishlaydi; >= price -> chegirma emas)
    if with_discount and tariff.discounted_price is not None and tariff.discounted_price < tariff.price:
        price = tariff.discounted_price
        discount_text = f"\n🎁 Chegirma: -{tariff.discount_percent}%"
    else:
        price = tariff.price
        discount_text = ""

    text = (
        f"💳 <b>To'lov ma'lumotlari:</b>\n\n"
        f"📦 Tarif: <b>{esc(tariff.name)}</b>\n"
        f"📅 Muddat: <b>{tariff.days} kun</b>\n"
        f"💰 Narx: <b>{price:,} so'm</b>{discount_text}\n\n"
        f"💳 Karta: <code>{esc(bot_settings.card_number)}</code>\n"
        f"👤 Egasi: <b>{esc(bot_settings.card_holder)}</b>\n\n"
        f"📸 <b>To'lovni amalga oshiring va screenshot yuboring.</b>\n\n"
        f"⚠️ Izoh: Chekda <code>{callback.from_user.id}</code> ni ko'rsating."
    )

    # State ga tarif saqlash
    await callback.message.edit_text(text, reply_markup=back_kb())

    # Tarif ma'lumotlarini saqlash (keyingi xabar uchun)
    await save_pending_payment(
        callback.from_user.id,
        tariff_id,
        price,
        with_discount
    )

    await callback.answer()


# ==================== SCREENSHOT YUBORISH ====================

@router.message(F.photo)
async def screenshot_handler(message: Message, db_user: User = None, bot: Bot = None):
    """Screenshot qabul qilish"""
    # Pending payment'ni ATOMIK "claim" qilamiz: o'qiladi va shu zahoti o'chiriladi.
    # Media-group (albom) yuborilganda har bir rasm alohida update bo'lib keladi va
    # parallel ishlaydi; faqat bitta handler sessiyani o'chira oladi, qolganlari None
    # oladi -> bitta to'lovga bitta Payment (takror to'lovlarning oldi olinadi).
    pending = await claim_pending_payment(message.from_user.id)

    if not pending:
        # Oddiy rasm yoki allaqachon claim qilingan - e'tibor bermaslik
        return

    tariff = await get_tariff(pending['tariff_id'])

    if not tariff:
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        return

    # Payment yaratish
    photo = message.photo[-1]

    payment = await create_payment(
        user_id=db_user.user_id,
        tariff_id=tariff.id,
        amount=pending['amount'],
        is_discounted=pending['with_discount'],
        screenshot_file_id=photo.file_id
    )

    # User ga xabar
    await message.answer(
        "✅ <b>Chek qabul qilindi!</b>\n\n"
        "⏳ Admin tekshirib, tasdiqlagandan keyin Premium aktivlashadi.\n"
        "Odatda bu 5-30 daqiqa vaqt oladi.",
        reply_markup=back_kb()
    )

    # Adminga xabar
    admin_text = (
        f"💳 <b>Yangi to'lov!</b>\n\n"
        f"👤 Foydalanuvchi: {esc(db_user.full_name)}\n"
        f"🆔 ID: <code>{db_user.user_id}</code>\n"
        f"📦 Tarif: {esc(tariff.name)} ({tariff.days} kun)\n"
        f"💰 Summa: {pending['amount']:,} so'm\n"
        f"🎁 Chegirma: {'Ha' if pending['with_discount'] else 'Yoq'}\n"
    )

    # Admin xabarlarini saqlash (keyinchalik o'chirish uchun)
    admin_messages = {}

    for admin_id in settings.ADMINS:
        try:
            msg = await bot.send_photo(
                chat_id=admin_id,
                photo=photo.file_id,
                caption=admin_text,
                reply_markup=payment_confirm_kb(payment.id)
            )
            admin_messages[str(admin_id)] = msg.message_id
        except TelegramBadRequest as e:
            logger.warning(f"Admin {admin_id} ga to'lov xabari yuborilmadi: {e}")
        except Exception as e:
            logger.error(f"Admin {admin_id} ga xabar yuborishda kutilmagan xatolik: {e}")

    # Admin xabar ID larni saqlash
    if admin_messages:
        await save_admin_messages(payment.id, admin_messages)


# ==================== TO'LOVNI TASDIQLASH ====================

@router.callback_query(F.data.startswith("approve_payment:"), CanManagePayments())
async def approve_payment_callback(callback: CallbackQuery, bot: Bot):
    """To'lovni tasdiqlash"""
    payment_id = int(callback.data.split(":")[1])

    # Admin xabarlarini olish (o'chirish uchun) - tasdiqlashdan oldin
    admin_messages = await get_admin_messages(payment_id)

    # Tasdiqlash (atomik: status transaksiya ichida qayta tekshiriladi -> ikki
    # marta tasdiqlash / double-credit poygasi oldi olinadi)
    result = await approve_payment(payment_id, callback.from_user.id)

    if result['result'] == 'not_found':
        await callback.answer("❌ To'lov topilmadi.", show_alert=True)
        return
    if result['result'] == 'already':
        await callback.answer("⚠️ Bu to'lov allaqachon ko'rib chiqilgan.", show_alert=True)
        return
    if result['result'] == 'no_tariff':
        await callback.answer(
            "❌ Tarif topilmadi (o'chirilgan). To'lov tasdiqlanmadi.", show_alert=True
        )
        return

    await callback.answer("✅ To'lov tasdiqlandi!")

    # Joriy admin xabarini yangilash
    try:
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n✅ <b>TASDIQLANDI</b>",
            reply_markup=None
        )
    except TelegramBadRequest as e:
        logger.debug(f"Admin xabarini yangilashda xatolik: {e}")

    # Boshqa adminlardan xabarni o'chirish
    current_admin_id = str(callback.from_user.id)
    if admin_messages:
        for admin_id, message_id in admin_messages.items():
            if admin_id != current_admin_id:
                try:
                    await bot.delete_message(chat_id=int(admin_id), message_id=message_id)
                except TelegramBadRequest as e:
                    logger.debug(f"Admin xabarini o'chirishda xatolik: {e}")

    # User ga xabar (approve_payment natijasidan - qo'shimcha so'rovsiz)
    try:
        await bot.send_message(
            chat_id=result['user_telegram_id'],
            text=(
                f"🎉 <b>Premium aktivlashtirildi!</b>\n\n"
                f"📦 Tarif: {esc(result['tariff_name'])}\n"
                f"📅 Muddat: {result['tariff_days']} kun\n\n"
                f"Botdan foydalaning! 🎬"
            )
        )
    except TelegramBadRequest as e:
        logger.warning(f"Userga premium xabari yuborilmadi (user_id={result['user_telegram_id']}): {e}")


# ==================== TO'LOVNI RAD ETISH ====================

@router.callback_query(F.data.startswith("reject_payment:"), CanManagePayments())
async def reject_payment_callback(callback: CallbackQuery, bot: Bot):
    """To'lovni rad etish"""
    payment_id = int(callback.data.split(":")[1])

    # Admin xabarlarini olish (o'chirish uchun) - rad etishdan oldin
    admin_messages = await get_admin_messages(payment_id)

    # Rad etish (atomik: faqat 'pending' bo'lsa; tasdiqlangan to'lovni bosib
    # ketmaydi -> approve/reject poygasi oldi olinadi)
    result = await reject_payment(payment_id)

    if result['result'] == 'not_found':
        await callback.answer("❌ To'lov topilmadi.", show_alert=True)
        return
    if result['result'] == 'already':
        await callback.answer("⚠️ Bu to'lov allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    await callback.answer("❌ To'lov rad etildi!")

    # Joriy admin xabarini yangilash
    try:
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n❌ <b>RAD ETILDI</b>",
            reply_markup=None
        )
    except TelegramBadRequest as e:
        logger.debug(f"Admin xabarini yangilashda xatolik: {e}")

    # Boshqa adminlardan xabarni o'chirish
    current_admin_id = str(callback.from_user.id)
    if admin_messages:
        for admin_id, message_id in admin_messages.items():
            if admin_id != current_admin_id:
                try:
                    await bot.delete_message(chat_id=int(admin_id), message_id=message_id)
                except TelegramBadRequest as e:
                    logger.debug(f"Admin xabarini o'chirishda xatolik: {e}")

    # User ga xabar (reject_payment natijasidan)
    try:
        await bot.send_message(
            chat_id=result['user_telegram_id'],
            text=(
                "❌ <b>To'lov rad etildi!</b>\n\n"
                "Iltimos, to'g'ri chek yuboring yoki admin bilan bog'laning."
            )
        )
    except TelegramBadRequest as e:
        logger.warning(f"Userga rad xabari yuborilmadi (user_id={result['user_telegram_id']}): {e}")


# ==================== HELPER FUNCTIONS ====================


@sync_to_async
def get_tariff(tariff_id: int):
    try:
        return Tariff.objects.get(id=tariff_id)
    except Tariff.DoesNotExist:
        return None


@sync_to_async
def create_payment(user_id: int, tariff_id: int, amount: int, is_discounted: bool, screenshot_file_id: str):
    user = User.objects.get(user_id=user_id)
    return Payment.objects.create(
        user=user,
        tariff_id=tariff_id,
        amount=amount,
        is_discounted=is_discounted,
        screenshot_file_id=screenshot_file_id
    )


@sync_to_async
def save_admin_messages(payment_id: int, admin_messages: dict):
    """Admin xabar ID larni saqlash"""
    try:
        Payment.objects.filter(id=payment_id).update(admin_messages=admin_messages)
    except Exception:
        pass


@sync_to_async
def get_admin_messages(payment_id: int) -> dict:
    """Admin xabar ID larni olish"""
    try:
        payment = Payment.objects.get(id=payment_id)
        return payment.admin_messages or {}
    except Payment.DoesNotExist:
        return {}


@sync_to_async
def approve_payment(payment_id: int, admin_user_id: int) -> dict:
    """To'lovni ATOMIK tasdiqlash.

    Status transaksiya ichida qayta tekshiriladi, Payment/User qatorlari
    select_for_update bilan qulflanadi -> bir to'lov ikki marta tasdiqlanmaydi
    (double premium-credit poygasining oldi olinadi). Tarif o'chirilgan bo'lsa
    'no_tariff' qaytaradi va hech narsani o'zgartirmaydi (to'lov 'pending' qoladi).
    """
    from django.db import transaction

    with transaction.atomic():
        try:
            payment = (
                Payment.objects.select_for_update()
                .select_related('tariff', 'user')
                .get(id=payment_id)
            )
        except Payment.DoesNotExist:
            return {'result': 'not_found'}

        if payment.status != 'pending':
            return {'result': 'already'}

        if payment.tariff is None:
            # Tarif o'chirilgan - kunlar sonini bilib bo'lmaydi, tasdiqlamaymiz.
            return {'result': 'no_tariff'}

        days = payment.tariff.days
        tariff_name = payment.tariff.name

        payment.status = 'approved'
        payment.approved_at = timezone.now()
        try:
            payment.approved_by = User.objects.get(user_id=admin_user_id)
        except User.DoesNotExist:
            pass
        payment.save(update_fields=['status', 'approved_at', 'approved_by'])

        # Premium berish (user qatorini ham qulflaymiz)
        user = User.objects.select_for_update().get(pk=payment.user_id)
        user.is_premium = True
        # Yangi premium davri -> tugash eslatmasi bayrog'ini tozalaymiz
        user.premium_expiry_notified = False
        if user.premium_expires and user.premium_expires > timezone.now():
            user.premium_expires += timedelta(days=days)
        else:
            user.premium_expires = timezone.now() + timedelta(days=days)
        user.save(update_fields=['is_premium', 'premium_expires', 'premium_expiry_notified'])

        user_telegram_id = user.user_id

    # Cache'ni tozalaymiz, aks holda user 60s davomida premium sifatida ko'rinmaydi.
    clear_user_cache(user_telegram_id)

    return {
        'result': 'ok',
        'user_telegram_id': user_telegram_id,
        'tariff_name': tariff_name,
        'tariff_days': days,
    }


@sync_to_async
def reject_payment(payment_id: int) -> dict:
    """To'lovni ATOMIK rad etish - faqat 'pending' bo'lsa.

    Tasdiqlangan to'lovni bosib ketmaydi (approve/reject poygasining oldi olinadi).
    """
    from django.db import transaction

    with transaction.atomic():
        try:
            payment = (
                Payment.objects.select_for_update()
                .select_related('user')
                .get(id=payment_id)
            )
        except Payment.DoesNotExist:
            return {'result': 'not_found'}

        if payment.status != 'pending':
            return {'result': 'already'}

        payment.status = 'rejected'
        payment.save(update_fields=['status'])
        user_telegram_id = payment.user.user_id

    return {'result': 'ok', 'user_telegram_id': user_telegram_id}


@sync_to_async
def save_pending_payment(user_id: int, tariff_id: int, amount: int, with_discount: bool):
    """Pending to'lovni database ga saqlash"""
    # Eski sessiyalarni tozalash
    PendingPaymentSession.cleanup_expired()

    # Eski sessiyani o'chirish (agar mavjud bo'lsa)
    try:
        user = User.objects.get(user_id=user_id)
        PendingPaymentSession.objects.filter(user=user).delete()

        # Yangi sessiya yaratish
        expires_at = timezone.now() + timedelta(seconds=PENDING_PAYMENT_TIMEOUT)
        PendingPaymentSession.objects.create(
            user=user,
            tariff_id=tariff_id,
            amount=amount,
            is_discounted=with_discount,
            message_id=0,  # Keyinchalik yangilanadi
            expires_at=expires_at
        )
    except User.DoesNotExist:
        logger.warning(f"Pending payment saqlashda user topilmadi: {user_id}")


@sync_to_async
def claim_pending_payment(user_id: int):
    """Pending to'lovni ATOMIK olish: o'qib, shu zahoti o'chiradi.

    Bir foydalanuvchidan bir vaqtda bir nechta rasm (media-group / albom) kelganda
    faqat BITTA handler sessiyani muvaffaqiyatli o'chira oladi -> bittasi ma'lumot
    oladi, qolganlari None. Bu takroriy Payment yozuvlarining oldini oladi.
    """
    PendingPaymentSession.cleanup_expired()

    try:
        user = User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return None

    session = PendingPaymentSession.objects.filter(user=user).order_by('-created_at').first()
    if not session:
        return None

    data = {
        'tariff_id': session.tariff_id,
        'amount': session.amount,
        'with_discount': session.is_discounted,
        'timestamp': session.created_at,
    }
    expired = session.is_expired

    # Atomik claim: qatorni pk bo'yicha o'chiramiz. delete() o'chirilgan qatorlar
    # sonini qaytaradi; parallel handlerlardan faqat bittasi 1 oladi, qolganlari 0.
    deleted, _ = PendingPaymentSession.objects.filter(pk=session.pk).delete()
    if not deleted:
        return None  # boshqa parallel handler allaqachon oldi

    if expired:
        return None

    return data
