import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()
SALON_ADDRESS = os.getenv("SALON_ADDRESS", "Адреса салону буде тут").strip()
SALON_PHONE = os.getenv("SALON_PHONE", "Телефон салону буде тут").strip()


def get_admin_id() -> int | None:
    if not ADMIN_ID:
        return None
    try:
        return int(ADMIN_ID)
    except ValueError:
        return None
