"""Staff dashboard summary, always calculated for clinic today."""

from datetime import datetime

from availability_service import CLINIC_TIMEZONE, get_available_slots
from database import get_appointment_summary_for_date


def get_admin_summary(*, now=None):
    current = (
        now or datetime.now(CLINIC_TIMEZONE)
    ).astimezone(CLINIC_TIMEZONE)
    today = current.date()

    counts = get_appointment_summary_for_date(
        today,
        now=current,
    )
    available_slots = get_available_slots(
        today,
        now=current,
    )

    next_start = counts["next_starts_at"]

    return {
        "date": today.isoformat(),
        "appointments_count": counts["appointments_count"],
        "next_starts_at": (
            next_start.isoformat()
            if next_start is not None
            else None
        ),
        "available_slots_count": len(available_slots),
        "no_show_count": counts["no_show_count"],
    }