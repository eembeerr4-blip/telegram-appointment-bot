from datetime import date, timedelta

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class BookingCallback(CallbackData, prefix="booking", sep="#"):
    action: str
    value: str


booking_cb = BookingCallback


def get_service_inline_keyboard() -> InlineKeyboardMarkup:
    services = [
        ("💇 Жіноча стрижка", "women_cut"),
        ("💈 Чоловіча стрижка", "men_cut"),
        ("✨ Фарбування", "coloring"),
        ("💅 Манікюр", "manicure"),
        ("🦶 Педикюр", "pedicure"),
    ]
    keyboard = []
    for text, value in services:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=booking_cb(action="service", value=value).pack(),
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                text="↩️ Назад",
                callback_data=booking_cb(action="back", value="service").pack(),
            )
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                text="❌ Відмінити",
                callback_data=booking_cb(action="cancel", value="").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_calendar_keyboard(start_date: date) -> InlineKeyboardMarkup:
    keyboard = []
    row = []
    for offset in range(14):
        day = start_date + timedelta(days=offset)
        row.append(
            InlineKeyboardButton(
                text=day.strftime("%d.%m"),
                callback_data=booking_cb(action="date", value=day.isoformat()).pack(),
            )
        )
        if len(row) == 7:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append(
        [
            InlineKeyboardButton(
                text="↩️ Назад",
                callback_data=booking_cb(action="back", value="service").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_timeslot_keyboard(date_iso: str) -> InlineKeyboardMarkup:
    slots = [
        "09:00",
        "09:30",
        "10:00",
        "10:30",
        "11:00",
        "11:30",
        "12:00",
        "12:30",
        "13:00",
        "13:30",
        "14:00",
        "14:30",
        "15:00",
        "15:30",
        "16:00",
        "16:30",
        "17:00",
        "17:30",
        "18:00",
        "18:30",
    ]
    keyboard = []
    for index in range(0, len(slots), 3):
        row = [
            InlineKeyboardButton(
                text=slot,
                callback_data=booking_cb(action="time", value=slot).pack(),
            )
            for slot in slots[index : index + 3]
        ]
        keyboard.append(row)
    keyboard.append(
        [
            InlineKeyboardButton(
                text="↩️ Назад",
                callback_data=booking_cb(action="back", value="date").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text="✅ Підтвердити",
                callback_data=booking_cb(action="confirm", value="yes").pack(),
            ),
            InlineKeyboardButton(
                text="🔄 Інший час",
                callback_data=booking_cb(action="confirm", value="no").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="❌ Відмінити",
                callback_data=booking_cb(action="cancel", value="").pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_user_appointments_keyboard(appointments: list[dict]) -> InlineKeyboardMarkup | None:
    if not appointments:
        return None

    keyboard = []
    for appointment in appointments:
        appointment_id = appointment.get("id")
        if not appointment_id:
            continue
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"❌ Скасувати #{appointment_id}",
                    callback_data=booking_cb(action="cancel_appointment", value=str(appointment_id)).pack(),
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                text="🏠 Головне меню",
                callback_data=booking_cb(action="close", value="").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
