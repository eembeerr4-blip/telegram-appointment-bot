
from __future__ import annotations

from typing import Any, Mapping, Sequence

STATUS_LABELS = {
    "new": "Новий",
    "confirmed": "Підтверджено",
    "cancelled": "Скасовано",
}


def get_status_label(status: str | None) -> str:
    return STATUS_LABELS.get(status or "", status or "")


def format_appointment_message(name: str, phone: str, service: str, date_time: str) -> str:
    return (
        "Нова заявка 📋\n\n"
        f"Ім'я:\n{name}\n\n"
        f"Телефон:\n{phone}\n\n"
        f"Послуга:\n{service}\n\n"
        f"Дата та час:\n{date_time}"
    )


def format_user_appointments(appointments: Sequence[Mapping[str, Any]]) -> str:
    if not appointments:
        return "У вас поки немає записів."

    lines = ["Ваші записи 📋"]
    for index, appointment in enumerate(appointments, start=1):
        service = appointment.get("service", "Не вказано")
        date_time = appointment.get("date_time", "Не вказано")
        status = appointment.get("status", "new")

        status_label = get_status_label(status)

        lines.append(f"\n{index}. {service}\n📅 {date_time}\n🟡 Статус: {status_label}")

    return "\n".join(lines)


def format_today_appointments(appointments: Sequence[Mapping[str, Any]]) -> str:
    if not appointments:
        return "Сьогодні немає записів."

    lines = ["Записи на сьогодні 📋"]
    for appointment in appointments:
        name = appointment.get("name", "Клієнт")
        phone = appointment.get("phone", "Не вказано")
        service = appointment.get("service", "Не вказано")
        date_time = appointment.get("date_time", "Не вказано")
        status = appointment.get("status", "new")

        status_label = get_status_label(status)

        lines.append(
            "\n"
            f"Ім'я: {name}\n"
            f"Телефон: {phone}\n"
            f"Послуга: {service}\n"
            f"Дата та час: {date_time}\n"
            f"Статус: {status_label}"
        )

    return "\n".join(lines)
