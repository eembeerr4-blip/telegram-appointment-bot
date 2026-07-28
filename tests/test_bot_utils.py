import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import date, datetime, timedelta

from bot_utils import format_appointment_message, format_user_appointments
from handlers.booking import BookingStates, handle_booking_callback, process_name, process_phone
from keyboards.booking import (
    booking_cb,
    get_calendar_keyboard,
    get_service_inline_keyboard,
    get_user_appointments_keyboard,
)
from main import get_reminder_action


class DummyState:
    def __init__(self) -> None:
        self.data: dict = {}
        self.state = None

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, state) -> None:
        self.state = state

    async def get_data(self) -> dict:
        return self.data

    async def clear(self) -> None:
        self.data = {}
        self.state = None


class DummyBot:
    def __init__(self) -> None:
        self.edited_messages: list[dict] = []

    async def edit_message_text(self, **kwargs) -> None:
        self.edited_messages.append(kwargs)


class DummyMessage:
    def __init__(self, text: str | None = None) -> None:
        self.chat = SimpleNamespace(id=1)
        self.message_id = 10
        self.bot = DummyBot()
        self.text = text
        self.contact = None
        self.answer_calls: list[tuple[tuple, dict]] = []

    async def answer(self, *args, **kwargs) -> None:
        self.answer_calls.append((args, kwargs))
        return SimpleNamespace(message_id=999)


class DummyCallbackQuery:
    def __init__(self, data: str) -> None:
        self.message = DummyMessage()
        self.data = data
        self.from_user = SimpleNamespace(id=123)
        self.bot = DummyBot()
        self.answer_calls: list[tuple[tuple, dict]] = []

    async def answer(self, *args, **kwargs) -> None:
        self.answer_calls.append((args, kwargs))


class BotUtilsTests(unittest.TestCase):
    def test_format_appointment_message_contains_all_details(self) -> None:
        message = format_appointment_message(
            name="Анна",
            phone="+380501112233",
            service="💇 Жіноча стрижка",
            date_time="30.07 о 15:00",
        )

        self.assertIn("Анна", message)
        self.assertIn("+380501112233", message)
        self.assertIn("💇 Жіноча стрижка", message)
        self.assertIn("30.07 о 15:00", message)

    def test_format_user_appointments_returns_empty_state(self) -> None:
        self.assertEqual(format_user_appointments([]), "У вас поки немає записів.")

    def test_service_inline_keyboard_contains_services(self) -> None:
        keyboard = get_service_inline_keyboard()
        buttons = [button.text for row in keyboard.inline_keyboard for button in row]
        self.assertIn("💇 Жіноча стрижка", buttons)
        self.assertIn("❌ Відмінити", buttons)
        self.assertIn("↩️ Назад", buttons)

    def test_user_appointments_keyboard_contains_cancel_buttons(self) -> None:
        appointments = [{"id": 1, "service": "Манікюр", "date_time": "01.01.2026 о 10:00", "status": "new"}]
        keyboard = get_user_appointments_keyboard(appointments)
        buttons = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        self.assertTrue(any("cancel_appointment" in callback and "1" in callback for callback in buttons))

    def test_booking_callback_supports_time_values(self) -> None:
        packed = booking_cb(action="time", value="14:30").pack()
        self.assertIsInstance(packed, str)
        self.assertIn("time", packed)

    def test_reminder_action_is_triggered_one_hour_before(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0)
        appointment_dt = now + timedelta(minutes=59)
        self.assertEqual(get_reminder_action(appointment_dt, now), "1h")

    def test_reminder_action_is_not_triggered_too_early(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0)
        appointment_dt = now + timedelta(minutes=61)
        self.assertIsNone(get_reminder_action(appointment_dt, now))

    def test_calendar_keyboard_contains_date_buttons(self) -> None:
        keyboard = get_calendar_keyboard(date.today())
        buttons = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        self.assertTrue(any("date" in callback for callback in buttons))


class BookingFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_name_and_phone_steps_update_state(self) -> None:
        state = DummyState()
        name_message = DummyMessage("Анна")

        await process_name(name_message, state)
        self.assertEqual(state.state, BookingStates.waiting_for_phone)
        self.assertEqual(state.data["name"], "Анна")

        phone_message = DummyMessage("+380501112233")
        await process_phone(phone_message, state)
        self.assertEqual(state.state, BookingStates.waiting_for_service)
        self.assertEqual(state.data["phone"], "+380501112233")

    async def test_service_selection_transitions_to_date_state(self) -> None:
        state = DummyState()
        state.data = {"name": "Анна", "phone": "+380501112233", "last_bot_msg_id": 1}
        callback = DummyCallbackQuery(booking_cb(action="service", value="women_cut").pack())

        await handle_booking_callback(callback, state, booking_cb(action="service", value="women_cut"))

        self.assertEqual(state.state, BookingStates.waiting_for_date)
        self.assertEqual(state.data["service"], "💇 Жіноча стрижка")
        self.assertEqual(callback.answer_calls[0][0], ())

    async def test_back_button_returns_to_service_selection(self) -> None:
        state = DummyState()
        state.data = {"name": "Анна", "phone": "+380501112233", "last_bot_msg_id": 1}
        callback = DummyCallbackQuery(booking_cb(action="back", value="service").pack())

        await handle_booking_callback(callback, state, booking_cb(action="back", value="service"))

        self.assertEqual(state.state, BookingStates.waiting_for_service)

    async def test_date_and_time_steps_update_state(self) -> None:
        state = DummyState()
        state.data = {"name": "Анна", "phone": "+380501112233", "service": "💇 Жіноча стрижка"}

        date_callback = DummyCallbackQuery(booking_cb(action="date", value="2026-07-30").pack())
        await handle_booking_callback(date_callback, state, booking_cb(action="date", value="2026-07-30"))
        self.assertEqual(state.state, BookingStates.waiting_for_time)
        self.assertEqual(state.data["date_iso"], "2026-07-30")

        time_callback = DummyCallbackQuery(booking_cb(action="time", value="14:30").pack())
        await handle_booking_callback(time_callback, state, booking_cb(action="time", value="14:30"))
        self.assertEqual(state.state, BookingStates.waiting_for_confirm)
        self.assertEqual(state.data["time"], "14:30")

    async def test_confirm_step_can_return_to_time_selection(self) -> None:
        state = DummyState()
        state.data = {"name": "Анна", "phone": "+380501112233", "date_iso": "2026-07-30", "time": "14:30"}
        callback = DummyCallbackQuery(booking_cb(action="confirm", value="no").pack())

        await handle_booking_callback(callback, state, booking_cb(action="confirm", value="no"))

        self.assertEqual(state.state, BookingStates.waiting_for_time)


if __name__ == "__main__":
    unittest.main()
