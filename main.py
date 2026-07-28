import asyncio
import logging
import sys
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from database import get_upcoming_reminder_appointments, init_db, mark_reminder_sent
from handlers.start import router
from handlers.menu import router as menu_router
from handlers.booking import router as booking_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_reminder_action(appointment_dt: datetime, now: datetime) -> str | None:
    if appointment_dt <= now:
        return None

    delta = appointment_dt - now
    if timedelta(0) < delta <= timedelta(minutes=60):
        return "1h"
    return None


async def reminder_worker(bot: Bot) -> None:
    async def run_once() -> None:
        now = datetime.now()
        deadline = now + timedelta(minutes=60)
        upcoming = get_upcoming_reminder_appointments(now.isoformat(), deadline.isoformat())

        for appointment in upcoming:
            try:
                appointment_dt = datetime.fromisoformat(appointment["datetime_iso"])
            except Exception:
                logging.exception("Invalid appointment datetime for reminder: %s", appointment.get("id"))
                continue

            if appointment["status"] == "cancelled":
                continue

            if appointment.get("telegram_id") is None:
                continue

            reminder_action = get_reminder_action(appointment_dt, now)
            if reminder_action is None:
                continue

            try:
                await bot.send_message(
                    int(appointment["telegram_id"]),
                    (
                        f"⏰ Нагадування про запис\n\n"
                        f"Послуга: {appointment['service']}\n"
                        f"Дата: {appointment['date_time']}\n"
                        f"Не забудьте прийти вчасно."
                    ),
                )
            except Exception:
                logging.exception("Failed to send reminder for appointment %s", appointment.get("id"))
                continue

            mark_reminder_sent(appointment["id"], reminder_action)

    while True:
        try:
            await run_once()
        except Exception:
            logging.exception("Reminder worker iteration failed")
        await asyncio.sleep(30)


async def main() -> None:
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is not set. Please fill the .env file.")
        sys.exit(1)

    init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    dp.include_router(menu_router)
    dp.include_router(booking_router)

    @dp.errors()
    async def handle_error(event) -> bool:
        logging.exception("Unhandled error: %s", event.exception)
        return True

    asyncio.create_task(reminder_worker(bot))

    logging.info("Bot started successfully")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
