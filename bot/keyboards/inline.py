from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_inline_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Asosiy menyu - inline"""
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="🔍 Kino qidirish", callback_data="search"))
    builder.row(
        InlineKeyboardButton(text="❤️ Saqlanganlar", callback_data="saved_movies"),
        InlineKeyboardButton(text="💎 Premium", callback_data="premium")
    )
    builder.row(
        InlineKeyboardButton(text="🙋 Kino so'rash", callback_data="request_movie"),
        InlineKeyboardButton(text="👤 Profil", callback_data="profile")
    )

    # Admin tugmasi
    if is_admin:
        builder.row(InlineKeyboardButton(text="👨‍💼 Admin Panel", callback_data="admin:panel"))

    return builder.as_markup()


def _channel_emoji(channel) -> str:
    """Kanal turiga qarab emoji.

    Instagram/tashqi kanallar ham 📢 bilan ko'rsatiladi - Telegram kanallardan
    farq qilmasligi (Instagram ekani bilinmasligi) uchun. Foydalanuvchi havolani
    bosganda o'zi ochilgan sahifani ko'radi.
    """
    return "📢"


def channels_kb(channels: list, check: bool = True) -> InlineKeyboardMarkup:
    """Majburiy kanallar - faqat havola tugmalari + «Tekshirish».

    Har kanal uchun bitta havola tugmasi (tartib raqami bilan). Alohida "obuna
    bo'ldim" tugmasi YO'Q:
    - Telegram kanal/guruh: obuna avtomatik (get_chat_member) tekshiriladi.
    - Instagram / bot / tashqi: bot tekshira olmaydi. "Ikki marta Tekshirish"
      mantig'i - foydalanuvchi Instagram'ga ikki marta tashrif buyurishga
      majbur bo'ladi (check_sub_callback'ga qarang).
    """
    builder = InlineKeyboardBuilder()

    # Kanallar tartib raqami bilan (1, 2, 3...). Instagram/tashqi (non-checkable)
    # check_subscription'da doim oxirida keladi -> eng oxirgi raqam bo'ladi.
    for i, channel in enumerate(channels, start=1):
        builder.row(InlineKeyboardButton(
            text=f"{i}. {_channel_emoji(channel)} {channel.title}",
            url=channel.invite_link
        ))

    if check:
        builder.row(InlineKeyboardButton(
            text="🔄 Tekshirish",
            callback_data="check_subscription"
        ))

    return builder.as_markup()


def subscription_prompt_text(channels: list, confirming: bool = False) -> str:
    """Obuna so'rovi matni. Barcha kanallar birga ko'rsatiladi (Telegram + Instagram).

    confirming=True: Telegram bajarilib, faqat Instagram qolganida BIRINCHI
    «Tekshirish»dan keyingi matn - foydalanuvchini Instagram'ga ikkinchi marta
    o'tib obuna bo'lishga undaydi.
    """
    if confirming:
        return (
            "📢 <b>Sahifamizga obuna bo'ling</b>\n\n"
            "Yuqoridagi <b>havolaga</b> o'ting, obuna bo'ling va shu yerga qayting.\n\n"
            "So'ng yana <b>«🔄 Tekshirish»</b> tugmasini bosing."
        )

    text = (
        "📢 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
        "Ro'yxatdagi barcha kanal va sahifalarga obuna bo'lib, "
        "<b>🔄 Tekshirish</b> tugmasini bosing."
    )
    return text


def categories_kb(categories: list) -> InlineKeyboardMarkup:
    """Kategoriyalar - chiroyli grid"""
    builder = InlineKeyboardBuilder()

    for category in categories:
        emoji = category.emoji if category.emoji else "📁"
        builder.button(text=f"{emoji} {category.name}", callback_data=f"category:{category.id}")

    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_menu"))

    return builder.as_markup()


def admin_categories_kb(categories: list) -> InlineKeyboardMarkup:
    """Admin uchun kategoriyalar"""
    builder = InlineKeyboardBuilder()

    for category in categories:
        emoji = category.emoji if category.emoji else "📁"
        builder.button(text=f"{emoji} {category.name}", callback_data=f"admin_category:{category.id}")

    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="admin_category:skip"))
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"))

    return builder.as_markup()


def movies_kb(movies: list, page: int = 1, total_pages: int = 1, category_id: int = None) -> InlineKeyboardMarkup:
    """Kinolar ro'yxati - chiroyli pagination"""
    builder = InlineKeyboardBuilder()

    for movie in movies:
        if movie.is_premium:
            prefix = "💎 "
        else:
            prefix = "🎬 "
        builder.row(InlineKeyboardButton(
            text=f"{prefix}{movie.display_title} [{movie.code}]",
            callback_data=f"movie:{movie.code}"
        ))

    # Pagination
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(
                text="◀️ Oldingi",
                callback_data=f"movies_page:{category_id}:{page - 1}"
            ))

        nav_buttons.append(InlineKeyboardButton(
            text=f"📄 {page}/{total_pages}",
            callback_data="noop"
        ))

        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(
                text="Keyingi ▶️",
                callback_data=f"movies_page:{category_id}:{page + 1}"
            ))

        builder.row(*nav_buttons)

    # Orqaga tugmasi
    if category_id:
        builder.row(InlineKeyboardButton(
            text="📂 Kategoriyalar",
            callback_data="categories"
        ))

    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_menu"))

    return builder.as_markup()


def filter_movies_kb(movies: list, filter_type: str, filter_value, page: int = 1, total_pages: int = 1) -> InlineKeyboardMarkup:
    """Filtr (davlat/til/yil) natijalari - filtrni saqlaydigan pagination.

    Pagination tugmasi 'filter_page:{type}:{value}:{page}' yuboradi, shunda keyingi
    sahifa ham xuddi shu filtr bo'yicha chiqadi (aks holda barcha kinolar chiqib ketardi).
    """
    builder = InlineKeyboardBuilder()

    for movie in movies:
        prefix = "💎 " if movie.is_premium else "🎬 "
        builder.row(InlineKeyboardButton(
            text=f"{prefix}{movie.display_title} [{movie.code}]",
            callback_data=f"movie:{movie.code}"
        ))

    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(
                text="◀️ Oldingi",
                callback_data=f"filter_page:{filter_type}:{filter_value}:{page - 1}"
            ))
        nav_buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(
                text="Keyingi ▶️",
                callback_data=f"filter_page:{filter_type}:{filter_value}:{page + 1}"
            ))
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="search"))
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_menu"))

    return builder.as_markup()


def tariffs_kb(tariffs: list, with_discount: bool = False) -> InlineKeyboardMarkup:
    """Tariflar - chiroyli"""
    builder = InlineKeyboardBuilder()

    for tariff in tariffs:
        if with_discount and tariff.discounted_price:
            old_price = f"<s>{tariff.price:,}</s>"
            text = f"🎁 {tariff.name} • {tariff.discounted_price:,} so'm (-{tariff.discount_percent}%)"
        else:
            text = f"💎 {tariff.name} • {tariff.price:,} so'm"

        builder.row(InlineKeyboardButton(
            text=text,
            callback_data=f"tariff:{tariff.id}:{1 if with_discount else 0}"
        ))

    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_menu"))

    return builder.as_markup()


def apply_discount(price: int, percent: int) -> int:
    """Narxga foizli chegirma qo'llash (butun so'm)."""
    if not percent or percent <= 0:
        return price
    percent = min(percent, 100)
    return price - (price * percent // 100)


def flash_sale_tariffs_kb(tariffs: list, is_discount: bool = True, discount_percent: int = 0) -> InlineKeyboardMarkup:
    """Flash sale tariflar. is_discount=True bo'lsa haqiqiy chegirmali narx ko'rsatiladi."""
    builder = InlineKeyboardBuilder()

    for tariff in tariffs:
        original_price = tariff.price

        if is_discount and discount_percent > 0:
            # Haqiqiy chegirmali narx
            new_price = apply_discount(original_price, discount_percent)
            text = f"🔥 {tariff.name} • {new_price:,} so'm (-{discount_percent}%)"
            builder.row(InlineKeyboardButton(
                text=text,
                callback_data=f"flash_tariff:{tariff.id}:1"
            ))
        else:
            # Chegirmasiz - qo'yilgan narx
            text = f"💎 {tariff.name} • {original_price:,} so'm"
            builder.row(InlineKeyboardButton(
                text=text,
                callback_data=f"flash_tariff:{tariff.id}:0"
            ))

    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_menu"))

    return builder.as_markup()


def payment_confirm_kb(payment_id: int) -> InlineKeyboardMarkup:
    """To'lovni tasdiqlash - admin"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_payment:{payment_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_payment:{payment_id}")
    )

    return builder.as_markup()


def broadcast_target_kb() -> InlineKeyboardMarkup:
    """Xabar yuborish maqsadi"""
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="👥 Hammaga", callback_data="broadcast_target:all"))
    builder.row(
        InlineKeyboardButton(text="💎 Premium", callback_data="broadcast_target:premium"),
        InlineKeyboardButton(text="👤 Oddiy", callback_data="broadcast_target:regular")
    )
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"))

    return builder.as_markup()


def broadcast_ad_kb() -> InlineKeyboardMarkup:
    """Reklama xabarmi"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Ha", callback_data="broadcast_ad:yes"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="broadcast_ad:no")
    )
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="cancel"))

    return builder.as_markup()


def confirm_broadcast_kb() -> InlineKeyboardMarkup:
    """Broadcast tasdiqlash"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Yuborish", callback_data="confirm_broadcast"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")
    )

    return builder.as_markup()


def movie_quality_kb() -> InlineKeyboardMarkup:
    """Kino sifati - chiroyli"""
    builder = InlineKeyboardBuilder()

    qualities = [
        ("📱 360p", "360p"),
        ("📺 480p", "480p"),
        ("💻 720p HD", "720p"),
        ("🖥 1080p FHD", "1080p"),
        ("📽 4K Ultra", "4k"),
    ]

    for text, data in qualities:
        builder.button(text=text, callback_data=f"quality:{data}")

    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"))

    return builder.as_markup()


def movie_language_kb() -> InlineKeyboardMarkup:
    """Kino tili - chiroyli"""
    builder = InlineKeyboardBuilder()

    languages = [
        ("🇺🇿 O'zbekcha", "uzbek"),
        ("🇷🇺 Ruscha", "rus"),
        ("🇺🇸 Inglizcha", "eng"),
        ("🇹🇷 Turkcha", "turk"),
        ("🇰🇷 Koreyscha", "korea"),
        ("🌍 Boshqa", "other"),
    ]

    for text, data in languages:
        builder.button(text=text, callback_data=f"language:{data}")

    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"))

    return builder.as_markup()


def movie_country_kb() -> InlineKeyboardMarkup:
    """Kino davlati - chiroyli"""
    builder = InlineKeyboardBuilder()

    countries = [
        ("🇺🇸 AQSH", "usa"),
        ("🇰🇷 Koreya", "korea"),
        ("🇮🇳 Hindiston", "india"),
        ("🇹🇷 Turkiya", "turkey"),
        ("🇷🇺 Rossiya", "russia"),
        ("🇺🇿 O'zbekiston", "uzbekistan"),
        ("🇬🇧 Britaniya", "uk"),
        ("🇫🇷 Fransiya", "france"),
        ("🇯🇵 Yaponiya", "japan"),
        ("🇨🇳 Xitoy", "china"),
        ("🌍 Boshqa", "other"),
    ]

    for text, data in countries:
        builder.button(text=text, callback_data=f"country:{data}")

    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"))

    return builder.as_markup()


def back_kb() -> InlineKeyboardMarkup:
    """Orqaga inline tugma"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_menu"))
    return builder.as_markup()


def movie_action_kb(movie_code: str, is_saved: bool = False, likes: int = 0, is_liked: bool = False) -> InlineKeyboardMarkup:
    """Kino ko'rganda action tugmalari (like + saqlash)"""
    builder = InlineKeyboardBuilder()

    like_text = f"👍 {likes} ✓" if is_liked else f"👍 {likes}"
    builder.row(InlineKeyboardButton(text=like_text, callback_data=f"like:{movie_code}"))

    if is_saved:
        builder.row(InlineKeyboardButton(text="💔 Saqlanganlardan o'chirish", callback_data=f"unsave:{movie_code}"))
    else:
        builder.row(InlineKeyboardButton(text="❤️ Saqlash", callback_data=f"save:{movie_code}"))

    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_menu"))
    return builder.as_markup()


def saved_movies_kb(movies: list, page: int = 1, total_pages: int = 1) -> InlineKeyboardMarkup:
    """Saqlangan kinolar ro'yxati"""
    builder = InlineKeyboardBuilder()

    for movie in movies:
        premium = "💎 " if movie.is_premium else ""
        builder.row(InlineKeyboardButton(
            text=f"{premium}🎬 {movie.display_title}",
            callback_data=f"saved_movie:{movie.code}"
        ))

    # Pagination
    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(
                text="◀️ Oldingi",
                callback_data=f"saved_page:{page - 1}"
            ))

        nav_buttons.append(InlineKeyboardButton(
            text=f"📄 {page}/{total_pages}",
            callback_data="noop"
        ))

        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(
                text="Keyingi ▶️",
                callback_data=f"saved_page:{page + 1}"
            ))

        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_menu"))

    return builder.as_markup()


def profile_kb() -> InlineKeyboardMarkup:
    """Profil menyusi — ko'rish tarixi, saqlanganlar."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📜 Ko'rilgan kinolar", callback_data="watch_history"))
    builder.row(InlineKeyboardButton(text="❤️ Saqlanganlar", callback_data="saved_movies"))
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_menu"))
    return builder.as_markup()


def history_movies_kb(movies: list, page: int = 1, total_pages: int = 1) -> InlineKeyboardMarkup:
    """Ko'rilgan kinolar ro'yxati (bosilса kino qayta yuboriladi)."""
    builder = InlineKeyboardBuilder()

    for movie in movies:
        premium = "💎 " if movie.is_premium else ""
        builder.row(InlineKeyboardButton(
            text=f"{premium}🎬 {movie.display_title}",
            callback_data=f"movie_view:{movie.code}"
        ))

    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"hist_page:{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"hist_page:{page + 1}"))
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="👤 Profil", callback_data="profile"))
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_menu"))
    return builder.as_markup()


def cancel_inline_kb() -> InlineKeyboardMarkup:
    """Bekor qilish inline"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"))
    return builder.as_markup()


def search_filter_kb() -> InlineKeyboardMarkup:
    """Qidiruv filtrlari"""
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="🔤 Nom bo'yicha qidirish", switch_inline_query_current_chat=""))
    builder.row(InlineKeyboardButton(text="🎬 Barcha kinolar", callback_data="all_movies"))
    builder.row(
        InlineKeyboardButton(text="📂 Janr", callback_data="filter:category"),
        InlineKeyboardButton(text="🌍 Davlat", callback_data="filter:country")
    )
    builder.row(
        InlineKeyboardButton(text="🌐 Til", callback_data="filter:language"),
        InlineKeyboardButton(text="📅 Yil", callback_data="filter:year")
    )
    builder.row(InlineKeyboardButton(text="🎲 Tasodifiy kino", callback_data="random_movie"))
    builder.row(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_menu"))

    return builder.as_markup()


def filter_country_kb() -> InlineKeyboardMarkup:
    """Davlat filtri"""
    builder = InlineKeyboardBuilder()

    countries = [
        ("🇺🇸 AQSH", "usa"),
        ("🇰🇷 Koreya", "korea"),
        ("🇮🇳 Hindiston", "india"),
        ("🇹🇷 Turkiya", "turkey"),
        ("🇷🇺 Rossiya", "russia"),
        ("🇺🇿 O'zbekiston", "uzbekistan"),
        ("🇯🇵 Yaponiya", "japan"),
        ("🇨🇳 Xitoy", "china"),
    ]

    for text, data in countries:
        builder.button(text=text, callback_data=f"filter_country:{data}")

    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="search"))

    return builder.as_markup()


def filter_language_kb() -> InlineKeyboardMarkup:
    """Til filtri"""
    builder = InlineKeyboardBuilder()

    languages = [
        ("🇺🇿 O'zbekcha", "uzbek"),
        ("🇷🇺 Ruscha", "rus"),
        ("🇺🇸 Inglizcha", "eng"),
        ("🇹🇷 Turkcha", "turk"),
        ("🇰🇷 Koreyscha", "korea"),
    ]

    for text, data in languages:
        builder.button(text=text, callback_data=f"filter_language:{data}")

    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="search"))

    return builder.as_markup()


def filter_year_kb() -> InlineKeyboardMarkup:
    """Yil filtri"""
    builder = InlineKeyboardBuilder()

    years = ["2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017"]

    for year in years:
        builder.button(text=year, callback_data=f"filter_year:{year}")

    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="search"))

    return builder.as_markup()


def skip_inline_kb() -> InlineKeyboardMarkup:
    """O'tkazib yuborish inline"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="skip"))
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel"))
    return builder.as_markup()


def admin_main_kb() -> InlineKeyboardMarkup:
    """Admin asosiy menyu inline"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Statistika", callback_data="admin:stats"))
    builder.row(
        InlineKeyboardButton(text="🎬 Kinolar", callback_data="admin:movies"),
        InlineKeyboardButton(text="➕ Qo'shish", callback_data="admin:add_movie")
    )
    builder.row(
        InlineKeyboardButton(text="🎭 Janrlar", callback_data="admin:categories"),
        InlineKeyboardButton(text="📢 Kanallar", callback_data="admin:channels")
    )
    builder.row(
        InlineKeyboardButton(text="👥 Userlar", callback_data="admin:users"),
        InlineKeyboardButton(text="💳 To'lovlar", callback_data="admin:payments")
    )
    builder.row(
        InlineKeyboardButton(text="💎 Tariflar", callback_data="admin:tariffs"),
        InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin:settings")
    )
    builder.row(
        InlineKeyboardButton(text="📨 Xabar yuborish", callback_data="admin:broadcast"),
        InlineKeyboardButton(text="🙋 So'rovlar", callback_data="admin:requests")
    )
    builder.row(InlineKeyboardButton(text="✏️ Xabarlar", callback_data="admin:messages"))
    builder.row(InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_menu"))
    return builder.as_markup()


def admin_messages_kb(messages: list) -> InlineKeyboardMarkup:
    """Xabar shablonlari ro'yxati"""
    builder = InlineKeyboardBuilder()

    for msg in messages:
        builder.row(InlineKeyboardButton(
            text=f"✏️ {msg.title}",
            callback_data=f"edit_msg:{msg.message_type}"
        ))

    builder.row(InlineKeyboardButton(text="🔄 Barcha xabarlarni tiklash", callback_data="reset_messages"))
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel"))

    return builder.as_markup()


def admin_stats_kb() -> InlineKeyboardMarkup:
    """Statistika menyusi"""
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="📈 Bugungi statistika", callback_data="stats:today"))
    builder.row(InlineKeyboardButton(text="📊 Haftalik statistika", callback_data="stats:week"))
    builder.row(InlineKeyboardButton(text="📉 Oylik statistika", callback_data="stats:month"))
    builder.row(InlineKeyboardButton(text="💎 Premium statistika", callback_data="stats:premium"))
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin:panel"))

    return builder.as_markup()


