import asyncio
import logging
import os
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MANDATORY_CHANNEL = os.getenv("MANDATORY_CHANNEL")
PRIVATE_MOVIE_CHANNEL = os.getenv("PRIVATE_MOVIE_CHANNEL")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

if not BOT_TOKEN or not MANDATORY_CHANNEL or not PRIVATE_MOVIE_CHANNEL:
    raise RuntimeError(
        "BOT_TOKEN, MANDATORY_CHANNEL and PRIVATE_MOVIE_CHANNEL must be set in .env"
    )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_FILE = "movies.db"

TRANSLATIONS = {
    "start": {
        "uz": "Tilni tanlang:",
        "ru": "Выберите язык:",
        "en": "Choose language:",
    },
    "need_channel": {
        "uz": "🔐 Botdan foydalanish uchun bizning kanalga a'zo bo'lishingiz kerak!\n\nKanalga azo bo'lganingizdan so'ng \"✅ Tekshirish\" tugmasini bosing.",
        "ru": "🔐 Для использования бота вам необходимо подписаться на наш канал!\n\nПосле подписки нажмите кнопку \"✅ Проверить\".",
        "en": "🔐 To use the bot, you need to subscribe to our channel!\n\nAfter subscribing, click the \"✅ Check\" button.",
    },
    "need_join": {
        "uz": "Siz majburiy kanalga a'zo bo'lishingiz kerak:\n{}",
        "ru": "Вы должны подписаться на канал:\n{}",
        "en": "You must subscribe to the channel:\n{}",
    },
    "ask_code": {
        "uz": "Kino kodini yuboring:",
        "ru": "Отправьте код фильма:",
        "en": "Send movie code:",
    },
    "not_found": {
        "uz": "Kod topilmadi",
        "ru": "Код не найден",
        "en": "Code not found",
    },
    "need_subscription": {
        "uz": "❌ Kechirasiz, sizning obuna muddati tugagan yoki hali faol emas.\n\nBot foydalanish uchun faol obuna zarur!",
        "ru": "❌ Извините, ваша подписка истекла или еще не активна.\n\nДля использования бота требуется активная подписка!",
        "en": "❌ Sorry, your subscription has expired or is not active yet.\n\nActive subscription required to use the bot!",
    },
    "already_member": {
        "uz": "✅ Siz allaqachon kanalga a'zo! Tilni tanlang:",
        "ru": "✅ Вы уже подписаны на канал! Выберите язык:",
        "en": "✅ You are already subscribed! Choose language:",
    },
}

LANG_BUTTONS = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
    ]
])


def get_channel_url(channel: str) -> str:
    """Convert channel identifier to proper Telegram link"""
    if not channel:
        return ""
    
    # If it starts with @, it's a username
    if channel.startswith("@"):
        return f"https://t.me/{channel.lstrip('@')}"
    
    # If it's a numeric ID starting with -100, convert to proper link
    if channel.startswith("-100"):
        channel_id = channel[4:]  # Remove -100 prefix
        return f"https://t.me/c/{channel_id}/"
    
    # If it starts with -, it's an old format, try to convert
    if channel.startswith("-"):
        channel_id = channel[1:]
        return f"https://t.me/c/{channel_id}/"
    
    # If it's just a number, assume it's a channel ID
    if channel.isdigit():
        return f"https://t.me/c/{channel}/"
    
    # Otherwise assume it's a username
    return f"https://t.me/{channel}"


def get_subscription_buttons(lang: str, channel_url: str) -> InlineKeyboardMarkup:
    """Create subscription verification buttons"""
    sub_text = {
        "uz": {"subscribe": "📺 Kanalga a'zo bo'lish", "check": "✅ Tekshirish"},
        "ru": {"subscribe": "📺 Подписаться", "check": "✅ Проверить"},
        "en": {"subscribe": "📺 Subscribe", "check": "✅ Check"},
    }
    texts = sub_text.get(lang, sub_text["en"])
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts["subscribe"], url=channel_url)],
        [InlineKeyboardButton(text=texts["check"], callback_data=f"check_sub_{lang}")],
    ])


class MovieDatabase:
    def __init__(self, filename: str):
        self.connection = sqlite3.connect(filename, check_same_thread=False)
        self.init_table()

    def init_table(self):
        with self.connection:
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, file_id TEXT, caption TEXT, file_type TEXT)"
            )
            self.connection.execute(
                """CREATE TABLE IF NOT EXISTS subscriptions (
                   user_id INTEGER PRIMARY KEY, 
                   is_active INTEGER DEFAULT 1,
                   created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                   expires_at DATETIME
                )"""
            )

    def save_movie(self, code: str, file_id: str, caption: str, file_type: str):
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO movies (code, file_id, caption, file_type) VALUES (?, ?, ?, ?)",
                (code, file_id, caption, file_type),
            )

    def get_movie(self, code: str):
        cursor = self.connection.cursor()
        cursor.execute("SELECT file_id, caption, file_type FROM movies WHERE code = ?", (code.strip(),))
        return cursor.fetchone()

    def add_subscription(self, user_id: int, expires_at: str = None):
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO subscriptions (user_id, is_active, expires_at) VALUES (?, 1, ?)",
                (user_id, expires_at),
            )

    def remove_subscription(self, user_id: int):
        with self.connection:
            self.connection.execute(
                "UPDATE subscriptions SET is_active = 0 WHERE user_id = ?",
                (user_id,),
            )

    def has_active_subscription(self, user_id: int) -> bool:
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT 1 FROM subscriptions 
               WHERE user_id = ? AND is_active = 1 
               AND (expires_at IS NULL OR expires_at > datetime('now'))""",
            (user_id,),
        )
        return cursor.fetchone() is not None

    def get_all_subscribers(self):
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT user_id, is_active, created_at, expires_at FROM subscriptions 
               WHERE is_active = 1 ORDER BY created_at"""
        )
        return cursor.fetchall()

    def get_subscriber_count(self):
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT COUNT(*) FROM subscriptions WHERE is_active = 1 
               AND (expires_at IS NULL OR expires_at > datetime('now'))"""
        )
        return cursor.fetchone()[0]


db = MovieDatabase(DB_FILE)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
user_languages: dict[int, str] = {}


async def check_mandatory_channel(user_id: int) -> bool:
    try:
        status = await bot.get_chat_member(MANDATORY_CHANNEL, user_id)
        return status.status in ("member", "creator", "administrator")
    except Exception as error:
        logger.warning("Failed to verify membership for %s: %s", user_id, error)
        return False


def check_subscription(user_id: int) -> bool:
    """Check if user has active subscription"""
    return db.has_active_subscription(user_id)


def translate(key: str, lang: str) -> str:
    return TRANSLATIONS.get(key, {}).get(lang, TRANSLATIONS.get(key, {}).get("en", ""))


@dp.message(Command(commands=["start"]))
async def cmd_start(message: Message):
    await message.answer(TRANSLATIONS["start"]["en"], reply_markup=LANG_BUTTONS)


@dp.message(Command(commands=["list"]))
async def cmd_list(message: Message):
    if message.from_user.id != ADMIN_USER_ID:
        return
    cursor = db.connection.cursor()
    cursor.execute("SELECT code, file_type FROM movies ORDER BY code")
    movies = cursor.fetchall()
    if movies:
        text = f"📽️ Saqlangan filmlar ({len(movies)} ta):\n"
        for code, ftype in movies:
            text += f"• {code} ({ftype})\n"
    else:
        text = "❌ Hech qanday kod topilmadi"
    await message.answer(text)


@dp.message(Command(commands=["test"]))
async def cmd_test(message: Message):
    if message.from_user.id != ADMIN_USER_ID:
        return
    db.save_movie("test123", "AgADAgADrqcxG...", "Test video", "video")
    await message.answer("✓ Test code 'test123' saved\n\nNow try: /gettest")


@dp.message(Command(commands=["gettest"]))
async def cmd_gettest(message: Message):
    if message.from_user.id != ADMIN_USER_ID:
        return
    result = db.get_movie("test123")
    if result:
        await message.answer(f"✓ Found: {result}")
    else:
        await message.answer("✗ Not found in DB")


@dp.message(Command(commands=["debug"]))
async def cmd_debug(message: Message):
    if message.from_user.id != ADMIN_USER_ID:
        return
    cursor = db.connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM movies")
    count = cursor.fetchone()[0]
    
    text = f"""🔧 Debug Info:
MANDATORY_CHANNEL: {MANDATORY_CHANNEL}
PRIVATE_MOVIE_CHANNEL: {PRIVATE_MOVIE_CHANNEL}
DB file: movies.db
Bazada filmlar: {count} ta

⚠️ MUHIM: Bot faqat U ISHGA TUSHIRILGANDAN KEYIN yuklangan videolarni qayd etadi. 
Eski videolar saqlanas yo'q.
Post qilgan yangi videolarni /list bilan tekshiring."""
    await message.answer(text)


@dp.message(Command(commands=["addsub"]))
async def cmd_addsub(message: Message):
    """Add subscription for user: /addsub user_id [expires_at]"""
    if message.from_user.id != ADMIN_USER_ID:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Foydalanish: /addsub user_id [YYYY-MM-DD]\n\nMisol: /addsub 123456789\nMisol (muddat bilan): /addsub 123456789 2025-12-31")
        return
    
    try:
        user_id = int(parts[1])
        expires_at = parts[2] if len(parts) > 2 else None
        db.add_subscription(user_id, expires_at)
        await message.answer(f"✅ Obuna qo'shildi: {user_id}\nMuddat: {expires_at or 'Cheksiz'}")
    except ValueError:
        await message.answer("❌ User ID noto'g'ri")


@dp.message(Command(commands=["remsub"]))
async def cmd_remsub(message: Message):
    """Remove subscription: /remsub user_id"""
    if message.from_user.id != ADMIN_USER_ID:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Foydalanish: /remsub user_id\n\nMisol: /remsub 123456789")
        return
    
    try:
        user_id = int(parts[1])
        db.remove_subscription(user_id)
        await message.answer(f"✅ Obuna bekor qilindi: {user_id}")
    except ValueError:
        await message.answer("❌ User ID noto'g'ri")


@dp.message(Command(commands=["subslist"]))
async def cmd_subslist(message: Message):
    """List all active subscribers"""
    if message.from_user.id != ADMIN_USER_ID:
        return
    
    subscribers = db.get_all_subscribers()
    if not subscribers:
        await message.answer("📋 Hech qanday faol obunachi topilmadi")
        return
    
    text = f"📋 Faol obunachi ({len(subscribers)} ta):\n\n"
    for user_id, is_active, created_at, expires_at in subscribers:
        status = "✅" if is_active else "❌"
        expiry = f"Muddat: {expires_at}" if expires_at else "Cheksiz"
        text += f"{status} ID: {user_id}\n   Yaratildi: {created_at}\n   {expiry}\n\n"
    
    await message.answer(text)


@dp.message(Command(commands=["subscount"]))
async def cmd_subscount(message: Message):
    """Get active subscriber count"""
    if message.from_user.id != ADMIN_USER_ID:
        return
    
    count = db.get_subscriber_count()
    await message.answer(f"📊 Faol obunachi: {count} ta")


@dp.message(Command(commands=["clear"]))
async def cmd_clear(message: Message):
    if message.from_user.id != ADMIN_USER_ID:
        return
    with db.connection:
        db.connection.execute("DELETE FROM movies")
    await message.answer("✓ Barcha kodlar o'chirildi")


@dp.callback_query(F.data.startswith("lang_"))
async def select_language(callback_query):
    lang = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id
    user_languages[user_id] = lang
    await callback_query.answer()
    
    # Check if user is member of mandatory channel
    is_member = await check_mandatory_channel(user_id)
    
    if not is_member:
        channel_url = get_channel_url(MANDATORY_CHANNEL)
        buttons = get_subscription_buttons(lang, channel_url)
        await callback_query.message.edit_text(translate("need_channel", lang), reply_markup=buttons)
        return
    
    # User is member - automatically add subscription to database if not exists
    if not check_subscription(user_id):
        db.add_subscription(user_id)
        logger.info(f"✅ Auto-added subscription for user {user_id}")
    
    await callback_query.message.edit_text(translate("ask_code", lang))


@dp.callback_query(F.data.startswith("check_sub_"))
async def check_subscription_callback(callback_query):
    """Check if user has subscribed and is member of channel"""
    lang = callback_query.data.split("_")[2]
    user_id = callback_query.from_user.id
    user_languages[user_id] = lang
    await callback_query.answer()
    
    # Check channel membership
    is_member = await check_mandatory_channel(user_id)
    if not is_member:
        channel_url = get_channel_url(MANDATORY_CHANNEL)
        buttons = get_subscription_buttons(lang, channel_url)
        await callback_query.message.edit_text(translate("need_channel", lang), reply_markup=buttons)
        return
    
    # User is channel member - automatically add subscription to database
    if not check_subscription(user_id):
        db.add_subscription(user_id)
        logger.info(f"✅ Auto-added subscription for user {user_id}")
    
    # All checks passed
    await callback_query.message.edit_text(translate("already_member", lang), reply_markup=LANG_BUTTONS)


@dp.message()
async def receive_code(message: Message):
    user_id = message.from_user.id
    user_lang = user_languages.get(user_id, "en")
    
    # Check if member of mandatory channel
    is_member = await check_mandatory_channel(user_id)
    
    if not is_member:
        channel_url = get_channel_url(MANDATORY_CHANNEL)
        buttons = get_subscription_buttons(user_lang, channel_url)
        await message.answer(translate("need_channel", user_lang), reply_markup=buttons)
        return
    
    # User is member - automatically add subscription to database if not exists
    if not check_subscription(user_id):
        db.add_subscription(user_id)
        logger.info(f"✅ Auto-added subscription for user {user_id}")
    
    code = message.text.strip() if message.text else ""
    if not code:
        await message.answer(translate("not_found", user_lang))
        return

    movie = db.get_movie(code)
    if not movie:
        await message.answer(translate("not_found", user_lang))
        return

    file_id, caption, file_type = movie
    if file_type == "video":
        await message.answer_video(video=file_id, caption=caption)
    else:
        await message.answer_document(document=file_id, caption=caption)


@dp.channel_post()
async def channel_post_handler(message: Message):
    logger.info("📢 Channel post: chat_id=%s username=%s caption='%s' video=%s doc=%s", 
                message.chat.id, message.chat.username or "N/A", 
                message.caption or "", bool(message.video), bool(message.document))
    
    chat_match = False
    if PRIVATE_MOVIE_CHANNEL.startswith("@"):
        chat_match = message.chat.username == PRIVATE_MOVIE_CHANNEL.lstrip("@")
    else:
        try:
            chat_match = int(PRIVATE_MOVIE_CHANNEL) == message.chat.id
        except ValueError:
            chat_match = False

    if not chat_match:
        logger.info("  ↳ Not our channel (looking for: %s)", PRIVATE_MOVIE_CHANNEL)
        return

    caption = message.caption or ""
    code = caption.strip() if caption else ""
    
    if not code:
        logger.info("  ↳ No caption")
        return

    if message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
    else:
        logger.info("  ↳ Not video or document")
        return

    db.save_movie(code, file_id, caption, file_type)
    logger.info("  ✓ SAVED: code='%s' type=%s", code, file_type)


async def main():
    logger.info("Starting NetMovi bot")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
