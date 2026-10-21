import unittest
from datetime import datetime, time, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from main import app
from rate_limits import require_booking_limit


class BookingTimezoneTests(unittest.TestCase):
    def test_utc_booking_uses_athens_winter_and_summer_time(self):
        clinic_timezone = ZoneInfo("Europe/Athens")
        year = datetime.now(clinic_timezone).year + 1
        previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[require_booking_limit] = lambda: None

        try:
            with TestClient(app) as client:
                for month, offset_hours in [(1, 2), (7, 3)]:
                    with self.subTest(month=month):
                        local_start = datetime(
                            year,
                            month,
                            15,
                            10,
                            0,
                            tzinfo=clinic_timezone,
                        )

                        while local_start.weekday() >= 5:
                            local_start += timedelta(days=1)

                        self.assertEqual(
                            local_start.utcoffset(),
                            timedelta(hours=offset_hours),
                        )

                        utc_start = local_start.astimezone(timezone.utc)

                        with patch(
                            "main.create_appointment_in_db",
                            return_value={
                                "id": 999,
                                "starts_at": utc_start,
                            },
                        ) as create_booking:
                            response = client.post(
                                "/appointments",
                                json={
                                    "patient_name": "Timezone Test",
                                    "patient_phone": "+306900000000",
                                    "patient_AMKA": "00000000000",
                                    "starts_at": utc_start.isoformat(),
                                },
                            )

                        self.assertEqual(
                            response.status_code,
                            201,
                            response.text,
                        )
                        create_booking.assert_called_once()
                        self.assertEqual(
                            create_booking.call_args.args[3],
                            utc_start,
                        )
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)

    def test_booking_without_timezone_is_rejected(self):
        clinic_timezone = ZoneInfo("Europe/Athens")
        booking_date = (
            datetime.now(clinic_timezone).date() + timedelta(days=7)
        )

        while booking_date.weekday() >= 5:
            booking_date += timedelta(days=1)

        starts_at = datetime.combine(booking_date, time(10, 0))
        previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[require_booking_limit] = lambda: None

        try:
            with (
                patch("main.create_appointment_in_db") as create_booking,
                TestClient(app) as client,
            ):
                response = client.post(
                    "/appointments",
                    json={
                        "patient_name": "Timezone Test",
                        "patient_phone": "+306900000000",
                        "patient_AMKA": "00000000000",
                        "starts_at": starts_at.isoformat(),
                    },
                )

                create_booking.assert_not_called()
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Η ημερομηνία πρέπει να περιλαμβάνει ζώνη ώρας.",
        )

    def test_opening_time_is_checked_in_athens_timezone(self):
        clinic_timezone = ZoneInfo("Europe/Athens")
        year = datetime.now(clinic_timezone).year + 1
        starts_at = datetime(
            year, 7, 15, 8, 0, tzinfo=timezone.utc
        )

        while starts_at.astimezone(clinic_timezone).weekday() >= 5:
            starts_at += timedelta(days=1)

        self.assertEqual(
            starts_at.astimezone(clinic_timezone).hour,
            11,
        )

        previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[require_booking_limit] = lambda: None

        try:
            with (
                patch(
                    "main.create_appointment_in_db",
                    return_value={"id": 999, "starts_at": starts_at},
                ) as create_booking,
                TestClient(app) as client,
            ):
                response = client.post(
                    "/appointments",
                    json={
                        "patient_name": "Timezone Test",
                        "patient_phone": "+306900000000",
                        "patient_AMKA": "00000000000",
                        "starts_at": starts_at.isoformat(),
                    },
                )

                self.assertEqual(
                    response.status_code, 201, response.text
                )
                create_booking.assert_called_once()
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)