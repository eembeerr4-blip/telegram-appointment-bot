import logging
from datetime import date, datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import get_admin_id
from database import (
    cancel_appointment,
    get_user_appointments,
    is_slot_available,
    save_appointment,
    save_user,
)
from keyboards.booking import (
    booking_cb,
    get_calendar_keyboard,
    get_confirm_keyboard,
    get_service_inline_keyboard,
    get_timeslot_keyboard,
    get_user_appointments_keyboard,
)
from keyboards.main_menu import get_main_keyboard
from bot_utils import format_appointment_message, format_user_appointments

router = Router()


class BookingStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_service = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_confirm = State()


SERVICE_LABELS = {
    "women_cut": "💇 Жіноча стрижка",
    "men_cut": "💈 Чоловіча стрижка",
    "coloring": "✨ Фарбування",
    "manicure": "💅 Манікюр",
    "pedicure": "🦶 Педикюр",
}


def format_datetime_text(date_iso: str | None, time_text: str | None) -> str:
    if not date_iso or not time_text:
        return "Не вибрано"
    try:
        dt = datetime.fromisoformat(f"{date_iso}T{time_text}:00")
        return dt.strftime("%d.%m.%Y о %H:%M")
    except ValueError:
        return "Не вказано"


async def _safe_edit_message(bot: Bot, chat_id: int, message_id: int, text: str, reply_markup=None) -> None:
    try:
        await bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
    except TelegramBadRequest:
        logging.debug("Unable to edit message %s in chat %s", message_id, chat_id)


@router.message(BookingStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip():
        await message.answer("Будь ласка, введіть ім'я.")
        return

    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(BookingStates.waiting_for_phone)

    data = await state.get_data()
    last_bot_msg_id = data.get("last_bot_msg_id")
    text = f"Дякуємо, {name}! 😊\nТепер, будь ласка, вкажіть ваш номер телефону 📱"

    if last_bot_msg_id:
        await _safe_edit_message(message.bot, message.chat.id, last_bot_msg_id, text)
    else:
        sent = await message.answer(text)
        await state.update_data(last_bot_msg_id=sent.message_id)


@router.message(BookingStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext) -> None:
    if message.contact:
        phone = message.contact.phone_number
    elif message.text and message.text.strip():
        phone = message.text.strip()
    else:
        await message.answer("Будь ласка, введіть номер телефону.")
        return

    await state.update_data(phone=phone)
    await state.set_state(BookingStates.waiting_for_service)

    data = await state.get_data()
    last_bot_msg_id = data.get("last_bot_msg_id")
    text = "Дякуємо за ваш номер телефону! 😊\n\nОберіть послугу:"

    if last_bot_msg_id:
        await _safe_edit_message(
            message.bot,
            message.chat.id,
            last_bot_msg_id,
            text,
            reply_markup=get_service_inline_keyboard(),
        )
    else:
        sent = await message.answer(text, reply_markup=get_service_inline_keyboard())
        await state.update_data(last_bot_msg_id=sent.message_id)


@router.callback_query(booking_cb.filter())
async def handle_booking_callback(
    callback_query: CallbackQuery,
    state: FSMContext,
    callback_data: object,
) -> None:
    if isinstance(callback_data, dict):
        action = callback_data.get("action")
        value = callback_data.get("value")
    else:
        action = getattr(callback_data, "action", None)
        value = getattr(callback_data, "value", None)

    data = await state.get_data()
    message = callback_query.message

    if action == "service":
        service_label = SERVICE_LABELS.get(value, value)
        await state.update_data(service=service_label)
        await state.set_state(BookingStates.waiting_for_date)
        await callback_query.answer()
        await _safe_edit_message(
            callback_query.bot,
            message.chat.id,
            message.message_id,
            text="Оберіть дату запису:",
            reply_markup=get_calendar_keyboard(date.today()),
        )
        return

    if action == "date":
        await state.update_data(date_iso=value)
        await state.set_state(BookingStates.waiting_for_time)
        await callback_query.answer()
        await _safe_edit_message(
            callback_query.bot,
            message.chat.id,
            message.message_id,
            text=f"Оберіть час на {datetime.fromisoformat(value).strftime('%d.%m.%Y')}: ",
            reply_markup=get_timeslot_keyboard(value),
        )
        return

    if action == "time":
        await state.update_data(time=value)
        await state.set_state(BookingStates.waiting_for_confirm)
        await callback_query.answer()

        service = data.get("service", "Не вказано")
        time_text = value
        date_text = data.get("date_iso")
        appointment_text = format_datetime_text(date_text, time_text)

        await _safe_edit_message(
            callback_query.bot,
            message.chat.id,
            message.message_id,
            text=(
                f"Перевірте, будь ласка, деталі запису:\n\n"
                f"Послуга: {service}\n"
                f"Дата та час: {appointment_text}"
            ),
            reply_markup=get_confirm_keyboard(),
        )
        return

    if action == "confirm":
        await callback_query.answer()
        if value != "yes":
            await state.set_state(BookingStates.waiting_for_time)
            await _safe_edit_message(
                callback_query.bot,
                message.chat.id,
                message.message_id,
                text="Гаразд, оберіть інший доступний час:",
                reply_markup=get_timeslot_keyboard(data.get("date_iso", "")),
            )
            return

        date_iso = data.get("date_iso")
        time_text = data.get("time")
        service = data.get("service")
        name = data.get("name", "Клієнт")
        phone = data.get("phone", "Не вказано")

        if not date_iso or not time_text or not service:
            await callback_query.answer("Щось пішло не так. Спробуйте ще раз.", show_alert=True)
            return

        datetime_iso = f"{date_iso}T{time_text}:00"
        if not is_slot_available(datetime_iso):
            await callback_query.answer("Цей слот вже зайнятий. Оберіть інший час.", show_alert=True)
            await state.set_state(BookingStates.waiting_for_time)
            await _safe_edit_message(
                callback_query.bot,
                message.chat.id,
                message.message_id,
                text="Оберіть інший час, будь ласка:",
                reply_markup=get_timeslot_keyboard(date_iso),
            )
            return

        save_user(callback_query.from_user.id, name, phone)
        save_appointment(callback_query.from_user.id, service, format_datetime_text(date_iso, time_text), datetime_iso)

        admin_id = get_admin_id()
        if admin_id:
            try:
                await callback_query.bot.send_message(
                    admin_id,
                    format_appointment_message(name, phone, service, format_datetime_text(date_iso, time_text)),
                )
            except Exception:
                logging.exception(
                    "Не вдалося надіслати заявку адміністратору (ADMIN_ID=%s)", admin_id
                )

        await state.clear()
        await _safe_edit_message(
            callback_query.bot,
            message.chat.id,
            message.message_id,
            text=(
                "🎉 Ваш запис успішно створено!\n\n"
                "Ми надішлемо нагадування за годину та за 30 хвилин до вашого візиту."
            ),
            reply_markup=None,
        )
        await callback_query.message.answer(
            "Повертаємося до головного меню.", reply_markup=get_main_keyboard()
        )
        return

    if action == "back":
        await callback_query.answer()
        target = value
        if target == "phone":
            await state.set_state(BookingStates.waiting_for_phone)
            await _safe_edit_message(
                callback_query.bot,
                message.chat.id,
                message.message_id,
                text="Повернулися до кроку введення телефону.",
                reply_markup=None,
            )
            return
        if target == "service":
            await state.set_state(BookingStates.waiting_for_service)
            await _safe_edit_message(
                callback_query.bot,
                message.chat.id,
                message.message_id,
                text="Оберіть послугу:",
                reply_markup=get_service_inline_keyboard(),
            )
            return
        if target == "date":
            await state.set_state(BookingStates.waiting_for_date)
            await _safe_edit_message(
                callback_query.bot,
                message.chat.id,
                message.message_id,
                text="Оберіть дату запису:",
                reply_markup=get_calendar_keyboard(date.today()),
            )
            return
        return

    if action == "cancel":
        await callback_query.answer()
        await state.clear()
        await _safe_edit_message(
            callback_query.bot,
            message.chat.id,
            message.message_id,
            text="Ви відмінили запис. Щоб почати знову, оберіть відповідну кнопку в меню.",
            reply_markup=None,
        )
        await callback_query.message.answer("Головне меню:", reply_markup=get_main_keyboard())
        return

    if action == "cancel_appointment":
        appointment_id = int(value) if value.isdigit() else None
        if not appointment_id:
            await callback_query.answer("Невірний запис.", show_alert=True)
            return

        canceled = cancel_appointment(callback_query.from_user.id, appointment_id)
        if canceled:
            await callback_query.answer("Запис скасовано.")
        else:
            await callback_query.answer("Не вдалося скасувати запис.", show_alert=True)

        appointments = get_user_appointments(callback_query.from_user.id)
        text = format_user_appointments(appointments)
        keyboard = get_user_appointments_keyboard([dict(row) for row in appointments])

        if keyboard:
            await _safe_edit_message(callback_query.bot, message.chat.id, message.message_id, text, reply_markup=keyboard)
        else:
            await _safe_edit_message(callback_query.bot, message.chat.id, message.message_id, text)
            await callback_query.message.answer("Головне меню:", reply_markup=get_main_keyboard())
        return

    if action == "close":
        await callback_query.answer()
        await _safe_edit_message(callback_query.bot, message.chat.id, message.message_id, "Ось ваше головне меню:", reply_markup=None)
        await callback_query.message.answer("Головне меню:", reply_markup=get_main_keyboard())
        return


@router.callback_query(F.data.startswith("cancel_appointment:"))
async def handle_legacy_cancel_appointment(callback_query: CallbackQuery, state: FSMContext) -> None:
    appointment_id = callback_query.data.split(":", 1)[1] if callback_query.data and ":" in callback_query.data else None
    if not appointment_id or not appointment_id.isdigit():
        await callback_query.answer("Невірний запис.", show_alert=True)
        return

    canceled = cancel_appointment(callback_query.from_user.id, int(appointment_id))
    if canceled:
        await callback_query.answer("Запис скасовано.")
    else:
        await callback_query.answer("Не вдалося скасувати запис.", show_alert=True)

    appointments = get_user_appointments(callback_query.from_user.id)
    text = format_user_appointments(appointments)
    keyboard = get_user_appointments_keyboard([dict(row) for row in appointments])

    message = callback_query.message
    if keyboard:
        await _safe_edit_message(callback_query.bot, message.chat.id, message.message_id, text, reply_markup=keyboard)
    else:
        await _safe_edit_message(callback_query.bot, message.chat.id, message.message_id, text)
        await callback_query.message.answer("Головне меню:", reply_markup=get_main_keyboard())
