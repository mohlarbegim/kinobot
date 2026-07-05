from aiogram.fsm.state import State, StatesGroup


class AddMovieState(StatesGroup):
    """Kino qo'shish holatlari"""
    code = State()
    title = State()
    video = State()
    category = State()
    year = State()
    country = State()
    quality = State()
    language = State()
    description = State()
    is_premium = State()
    confirm = State()  # Tasdiqlash


class EditMovieState(StatesGroup):
    """Kino tahrirlash holatlari (qaysi maydon FSM data'da: edit_code, edit_field)"""
    value = State()


class BroadcastState(StatesGroup):
    """Xabar yuborish holatlari"""
    target = State()
    is_ad = State()
    content = State()
    confirm = State()


class AddChannelState(StatesGroup):
    """Kanal qo'shish holatlari"""
    channel_input = State()
    title = State()
    name = State()  # Instagram/tashqi sahifa uchun ko'rinadigan nom (Instagram ekani bilinmasin)


class EditSettingsState(StatesGroup):
    """Sozlamalarni tahrirlash"""
    card_number = State()
    card_holder = State()
    trial_days = State()
    referral_bonus = State()
    discount_percent = State()
    discount_duration = State()


class EditMessageState(StatesGroup):
    """Xabar shablonini tahrirlash"""
    message_type = State()
    content = State()


class UserSearchState(StatesGroup):
    """User qidirish holatlari"""
    query = State()


class MovieSearchState(StatesGroup):
    """Kino qidirish holatlari"""
    query = State()


class AddCategoryState(StatesGroup):
    """Janr qo'shish holatlari"""
    name = State()
    emoji = State()


class EditCategoryState(StatesGroup):
    """Janrni tahrirlash holatlari"""
    name = State()
    emoji = State()


class AddTariffState(StatesGroup):
    """Tarif qo'shish holatlari"""
    name = State()
    days = State()
    price = State()


class EditTariffState(StatesGroup):
    """Tarifni tahrirlash holatlari"""
    name = State()
    days = State()
    price = State()
