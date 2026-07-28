from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="💎 Ціни"), KeyboardButton(text="📝 Записатися")],
        [KeyboardButton(text="📅 Мої записи"), KeyboardButton(text="📞 Зателефонувати")],
        [KeyboardButton(text="📍 Адреса")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
