import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").strip()
SALON_ADDRESS = os.getenv("SALON_ADDRESS", "Адреса салону буде тут").strip()
SALON_PHONE = os.getenv("SALON_PHONE", "Телефон салону буде тут").strip()


def get_admin_id() -> int | None:
    raw_value = (ADMIN_ID or "").strip()
    if not raw_value:
        return None
    if raw_value.startswith("@"):
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def get_admin_username() -> str | None:
    raw_value = (ADMIN_USERNAME or ADMIN_ID or "").strip()
    if not raw_value:
        return None
    if raw_value.isdigit():
        return None
    if raw_value.startswith("@"):
        return raw_value
    return raw_value


async def get_admin_chat_id(bot) -> int | None:
    admin_id = get_admin_id()
    if admin_id is not None:
        return admin_id

    username = get_admin_username()
    if not username or not getattr(bot, "get_chat", None):
        return None

    try:
        chat = await bot.get_chat(username)
        return int(chat.id)
    except Exception:
        return None
