"""
Bot uchun doimiy qiymatlar (constants).
Barcha hardcoded qiymatlar shu yerda saqlanadi.
"""

# Cache TTL (Time To Live) - sekundlarda
CACHE_TTL_USER = 60  # User cache - 1 daqiqa
CACHE_TTL_SETTINGS = 300  # Settings cache - 5 daqiqa
CACHE_TTL_ADMIN = 300  # Admin cache - 5 daqiqa
CACHE_TTL_MOVIES = 120  # Movies cache - 2 daqiqa
CACHE_TTL_CATEGORIES = 300  # Categories cache - 5 daqiqa
CACHE_TTL_BOT_INFO = 3600  # Bot info cache - 1 soat
CACHE_TTL_SUBSCRIPTION = 600  # Subscription pending cache - 10 daqiqa

# Cache max size
CACHE_MAX_USERS = 1000
CACHE_MAX_MOVIES = 100
CACHE_MAX_ADMINS = 100
CACHE_MAX_PENDING_SUBS = 10000

# Pagination
DEFAULT_PER_PAGE = 8
PREMIUM_MOVIES_PER_PAGE = 5
TOP_MOVIES_LIMIT = 10

# Payment
PENDING_PAYMENT_TIMEOUT = 1800  # 30 daqiqa (sekundlarda)

# Yopiq kanalga qo'shilish so'rovi necha kun "obuna" deb hisoblanadi.
# So'rov bekor qilingan/rad etilgan bo'lsa Telegram signal bermaydi, shuning uchun
# yozuv abadiy qolib cheksiz kirish bermasligi uchun vaqt oynasi qo'yamiz. Undan keyin
# get_chat_member qayta tekshiradi (tasdiqlangan bo'lsa a'zo bo'ladi, aks holda qayta so'raladi).
JOIN_REQUEST_TTL_DAYS = 7

# Validation
MAX_MOVIE_CODE_LENGTH = 10

# Input validation patterns
MOVIE_CODE_PATTERN = r'^\d{1,10}$'
