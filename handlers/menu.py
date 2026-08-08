from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import get_admin_chat_id, SALON_ADDRESS, SALON_PHONE
from database import get_todays_appointments_async, get_user_appointments_async
from keyboards.booking import get_user_appointments_keyboard
from keyboards.main_menu import get_main_keyboard
from bot_utils import format_user_appointments, format_today_appointments

router = Router()


@router.message(lambda message: message.text in {"📍 Адреса"})
async def show_address(message: Message) -> None:
    await message.answer(f"📍 Адреса салону:\n{SALON_ADDRESS}", reply_markup=get_main_keyboard())


@router.message(lambda message: message.text in {"📞 Зателефонувати"})
async def show_phone(message: Message) -> None:
    await message.answer(f"📞 Телефон салону:\n{SALON_PHONE}", reply_markup=get_main_keyboard())


@router.message(lambda message: message.text in {"📅 Мої записи"})
async def show_my_appointments(message: Message) -> None:
    appointments = await get_user_appointments_async(message.from_user.id)
    text = format_user_appointments(appointments)
    keyboard = get_user_appointments_keyboard([dict(row) for row in appointments])
    await message.answer(text, reply_markup=keyboard or get_main_keyboard())


@router.message(lambda message: message.text in {"💎 Ціни"})
async def show_prices(message: Message) -> None:
    await message.answer(
        "Наші ціни: 💎\n\n"
        "💇 Жіноча стрижка — 600 ₴\n"
        "💈 Чоловіча стрижка — 400 ₴\n"
        "✨ Фарбування — від 1200 ₴\n"
        "💅 Манікюр — 500 ₴\n"
        "🦶 Педикюр — 700 ₴",
        reply_markup=get_main_keyboard(),
    )


@router.message(lambda message: message.text in {"📝 Записатися"})
async def start_booking(message: Message, state: FSMContext) -> None:
    from handlers.booking import BookingStates

    await state.set_state(BookingStates.waiting_for_name)
    sent = await message.answer(
        "Чудово! Давайте оформимо запис 😊\n\nЯк вас звати?",
        reply_markup=None,
    )
    await state.update_data(last_bot_msg_id=sent.message_id)


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    admin_id = await get_admin_chat_id(message.bot)
    if not admin_id or message.from_user.id != admin_id:
        await message.answer("У вас немає доступу до цієї команди.")
        return

    today = date.today().isoformat()
    appointments = await get_todays_appointments_async(today)
    await message.answer(format_today_appointments(appointments), reply_markup=get_main_keyboard())
