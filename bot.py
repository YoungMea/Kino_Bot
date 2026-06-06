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
}

LANG_BUTTONS = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
    ]
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
    
    if not await check_mandatory_channel(user_id):
        invite_link = f"https://t.me/{MANDATORY_CHANNEL.lstrip('@')}" if MANDATORY_CHANNEL.startswith("@") else MANDATORY_CHANNEL
        await callback_query.message.edit_text(translate("need_join", lang).format(invite_link))
        return

    await callback_query.message.edit_text(translate("ask_code", lang))


@dp.message()
async def receive_code(message: Message):
    user_id = message.from_user.id
    user_lang = user_languages.get(user_id, "en")
    
    if not await check_mandatory_channel(user_id):
        invite_link = f"https://t.me/{MANDATORY_CHANNEL.lstrip('@')}" if MANDATORY_CHANNEL.startswith("@") else MANDATORY_CHANNEL
        await message.answer(translate("need_join", user_lang).format(invite_link))
        return

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
