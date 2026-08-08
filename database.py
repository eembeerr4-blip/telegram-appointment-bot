import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "database" / "salon.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_appointment_columns(conn: sqlite3.Connection) -> None:
    existing_columns = [row[1] for row in conn.execute("PRAGMA table_info(appointments)").fetchall()]

    if "datetime_iso" not in existing_columns:
        conn.execute("ALTER TABLE appointments ADD COLUMN datetime_iso TEXT")
    if "reminder_1h_sent" not in existing_columns:
        conn.execute("ALTER TABLE appointments ADD COLUMN reminder_1h_sent INTEGER NOT NULL DEFAULT 0")
    if "reminder_30m_sent" not in existing_columns:
        conn.execute("ALTER TABLE appointments ADD COLUMN reminder_30m_sent INTEGER NOT NULL DEFAULT 0")


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                name TEXT,
                phone TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                service TEXT NOT NULL,
                date_time TEXT NOT NULL,
                datetime_iso TEXT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                reminder_1h_sent INTEGER NOT NULL DEFAULT 0,
                reminder_30m_sent INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_appointments_telegram_id
            ON appointments (telegram_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_appointments_datetime_iso
            ON appointments (datetime_iso)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_appointments_status
            ON appointments (status)
            """
        )
        _ensure_appointment_columns(conn)
        conn.commit()


async def init_db_async() -> None:
    await asyncio.to_thread(init_db)


async def save_user_async(telegram_id: int, name: str, phone: str) -> None:
    await asyncio.to_thread(save_user, telegram_id, name, phone)


def save_user(telegram_id: int, name: str, phone: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id) VALUES (?)",
            (telegram_id,),
        )
        conn.execute(
            "UPDATE users SET name = ?, phone = ? WHERE telegram_id = ?",
            (name, phone, telegram_id),
        )
        conn.commit()


async def save_appointment_async(telegram_id: int, service: str, date_time: str, datetime_iso: str) -> None:
    await asyncio.to_thread(save_appointment, telegram_id, service, date_time, datetime_iso)


def save_appointment(telegram_id: int, service: str, date_time: str, datetime_iso: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO appointments (telegram_id, service, date_time, datetime_iso, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                telegram_id,
                service,
                date_time,
                datetime_iso,
                datetime.now().isoformat(),
                "new",
            ),
        )
        conn.commit()


async def get_user_appointments_async(telegram_id: int) -> list[sqlite3.Row]:
    return await asyncio.to_thread(get_user_appointments, telegram_id)


def get_user_appointments(telegram_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, service, date_time, status, datetime_iso
            FROM appointments
            WHERE telegram_id = ?
            ORDER BY datetime_iso DESC, id DESC
            """,
            (telegram_id,),
        ).fetchall()


async def is_slot_available_async(datetime_iso: str) -> bool:
    return await asyncio.to_thread(is_slot_available, datetime_iso)


def is_slot_available(datetime_iso: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(1) as count
            FROM appointments
            WHERE datetime_iso = ?
              AND status != 'cancelled'
            """,
            (datetime_iso,),
        ).fetchone()
        return row["count"] == 0


async def cancel_appointment_async(telegram_id: int, appointment_id: int) -> bool:
    return await asyncio.to_thread(cancel_appointment, telegram_id, appointment_id)


def cancel_appointment(telegram_id: int, appointment_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE appointments
            SET status = 'cancelled', reminder_1h_sent = 1, reminder_30m_sent = 1
            WHERE id = ? AND telegram_id = ? AND status != 'cancelled'
            """,
            (appointment_id, telegram_id),
        )
        conn.commit()
        return cursor.rowcount > 0


async def get_todays_appointments_async(day_iso: str) -> list[sqlite3.Row]:
    return await asyncio.to_thread(get_todays_appointments, day_iso)


def get_todays_appointments(day_iso: str) -> list[sqlite3.Row]:
    start = f"{day_iso}T00:00:00"
    end = f"{day_iso}T23:59:59"
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT a.id,
                   a.telegram_id,
                   a.service,
                   a.date_time,
                   a.status,
                   a.datetime_iso,
                   u.name,
                   u.phone
            FROM appointments a
            LEFT JOIN users u ON u.telegram_id = a.telegram_id
            WHERE a.datetime_iso >= ?
              AND a.datetime_iso <= ?
              AND a.status != 'cancelled'
            ORDER BY a.datetime_iso ASC
            """,
            (start, end),
        ).fetchall()


async def get_active_appointments_async() -> list[sqlite3.Row]:
    return await asyncio.to_thread(get_active_appointments)


def get_active_appointments() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, telegram_id, service, date_time, status, datetime_iso, reminder_1h_sent, reminder_30m_sent
            FROM appointments
            WHERE status != 'cancelled'
              AND datetime_iso IS NOT NULL
            """
        ).fetchall()


async def get_upcoming_reminder_appointments_async(now_iso: str, deadline_iso: str) -> list[sqlite3.Row]:
    return await asyncio.to_thread(get_upcoming_reminder_appointments, now_iso, deadline_iso)


def get_upcoming_reminder_appointments(now_iso: str, deadline_iso: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, telegram_id, service, date_time, status, datetime_iso, reminder_1h_sent, reminder_30m_sent
            FROM appointments
            WHERE status != 'cancelled'
              AND datetime_iso IS NOT NULL
              AND datetime_iso >= ?
              AND datetime_iso <= ?
            ORDER BY datetime_iso ASC
            """,
            (now_iso, deadline_iso),
        ).fetchall()


async def mark_reminder_sent_async(appointment_id: int, reminder_type: str) -> None:
    await asyncio.to_thread(mark_reminder_sent, appointment_id, reminder_type)


def mark_reminder_sent(appointment_id: int, reminder_type: str) -> None:
    if reminder_type not in {"1h", "30m"}:
        return
    column = "reminder_1h_sent" if reminder_type == "1h" else "reminder_30m_sent"
    with get_connection() as conn:
        conn.execute(
            f"UPDATE appointments SET {column} = 1 WHERE id = ?",
            (appointment_id,),
        )
        conn.commit()
