import unittest
from datetime import datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from psycopg.errors import UniqueViolation

from main import app
from rate_limits import require_booking_limit


class BookingConflictTests(unittest.TestCase):
    def test_duplicate_slot_returns_409(self):
        clinic_timezone = ZoneInfo("Europe/Athens")
        booking_date = (
            datetime.now(clinic_timezone).date() + timedelta(days=7)
        )

        while booking_date.weekday() >= 5:
            booking_date += timedelta(days=1)

        starts_at = datetime.combine(
            booking_date,
            time(10, 0),
            tzinfo=clinic_timezone,
        )
        previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[require_booking_limit] = lambda: None

        try:
            with (
                patch(
                    "main.create_appointment_in_db",
                    side_effect=UniqueViolation("Test conflict"),
                ) as create_booking,
                TestClient(app) as client,
            ):
                response = client.post(
                    "/appointments",
                    json={
                        "patient_name": "Conflict Test",
                        "patient_phone": "+306900000000",
                        "patient_AMKA": "00000000000",
                        "starts_at": starts_at.isoformat(),
                    },
                )

                create_booking.assert_called_once()
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"],
            "Η συγκεκριμένη ώρα έχει ήδη κρατηθεί.",
        )