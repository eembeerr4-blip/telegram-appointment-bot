import asyncio
import contextlib
import logging
import sys
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiolimiter import AsyncLimiter

from config import BOT_TOKEN, get_admin_chat_id
from database import (
    get_upcoming_reminder_appointments_async,
    init_db_async,
    mark_reminder_sent_async,
)
from handlers.booking import router as booking_router
from handlers.menu import router as menu_router
from handlers.start import router
from middlewares.throttling import ThrottlingMiddleware, UpdateDedupMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_reminder_action(appointment_dt: datetime, now: datetime) -> str | None:
    if appointment_dt <= now:
        return None

    delta = appointment_dt - now
    if timedelta(0) < delta <= timedelta(minutes=30):
        return "30m"
    if timedelta(minutes=30) < delta <= timedelta(minutes=60):
        return "1h"
    return None


async def reminder_worker(bot: Bot) -> None:
    global_limiter = AsyncLimiter(10, 1)
    chat_limiters: dict[int, AsyncLimiter] = {}

    async def send_reminder_message(chat_id: int, text: str) -> None:
        limiter = chat_limiters.setdefault(chat_id, AsyncLimiter(2, 1))
        async with global_limiter:
            async with limiter:
                await bot.send_message(chat_id, text)

    async def run_once() -> None:
        now = datetime.now()
        deadline = now + timedelta(minutes=60)
        upcoming = await get_upcoming_reminder_appointments_async(now.isoformat(), deadline.isoformat())

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

            if reminder_action == "30m" and bool(appointment.get("reminder_30m_sent")):
                continue
            if reminder_action == "1h" and bool(appointment.get("reminder_1h_sent")):
                continue

            try:
                await send_reminder_message(
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

            await mark_reminder_sent_async(appointment["id"], reminder_action)

    while True:
        try:
            await run_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Reminder worker iteration failed")
        await asyncio.sleep(30)


async def main() -> None:
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is not set. Please fill the .env file.")
        sys.exit(1)

    await init_db_async()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.update.outer_middleware(UpdateDedupMiddleware())
    dp.message.outer_middleware(ThrottlingMiddleware())
    dp.callback_query.outer_middleware(ThrottlingMiddleware())
    dp.include_router(router)
    dp.include_router(menu_router)
    dp.include_router(booking_router)

    @dp.errors()
    async def handle_error(event) -> bool:
        logging.error("Unhandled error", exc_info=(type(event.exception), event.exception, event.exception.__traceback__))
        return True

    reminder_task = asyncio.create_task(reminder_worker(bot))

    try:
        admin_chat_id = await get_admin_chat_id(bot)
        if admin_chat_id:
            logging.info("Admin chat resolved: %s", admin_chat_id)
        else:
            logging.info("Admin chat not resolved; using configured admin settings if available")
        logging.info("Bot started successfully")
        await dp.start_polling(bot)
    finally:
        if not reminder_task.done():
            reminder_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reminder_task
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
