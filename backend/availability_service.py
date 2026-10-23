"""Public slot calculation shared by the booking form and assistant."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from database import get_active_blocks_for_date, get_booked_times_for_date

CLINIC_TIMEZONE = ZoneInfo('Europe/Athens')


def get_available_slots(day, *, now=None, booked_reader=None, blocks_reader=None):
    now = (now or datetime.now(CLINIC_TIMEZONE)).astimezone(CLINIC_TIMEZONE)
    if day < now.date() or day.weekday() >= 5:
        return []
    booked = (booked_reader or get_booked_times_for_date)(day)
    blocks = (blocks_reader or get_active_blocks_for_date)(day)
    opening = datetime.combine(day, time(9), tzinfo=CLINIC_TIMEZONE)
    slots = []
    for index in range(16):
        start = opening + timedelta(minutes=30 * index)
        end = start + timedelta(minutes=30)
        label = start.strftime('%H:%M')
        overlaps = any(start < block['ends_at'] and end > block['starts_at'] for block in blocks)
        if start > now and label not in booked and not overlaps:
            slots.append(label)
    return slots
