import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from main import app


class BlockedAvailabilityTests(unittest.TestCase):
    def test_partial_overlap_removes_whole_slots(self):
        clinic_timezone = ZoneInfo("Europe/Athens")
        booking_date = (
            datetime.now(clinic_timezone).date() + timedelta(days=7)
        )

        while booking_date.weekday() >= 5:
            booking_date += timedelta(days=1)

        block_start = datetime(
            booking_date.year,
            booking_date.month,
            booking_date.day,
            10,
            15,
            tzinfo=clinic_timezone,
        )
        block_end = block_start + timedelta(minutes=30)

        with (
            patch(
                "main.get_booked_times_for_date",
                return_value=[],
            ),
            patch(
                "main.get_active_blocks_for_date",
                return_value=[
                    {
                        "starts_at": block_start,
                        "ends_at": block_end,
                    }
                ],
                create=True,
            ),
            TestClient(app) as client,
        ):
            response = client.get(
                "/availability",
                params={"date": booking_date.isoformat()},
            )

        self.assertEqual(response.status_code, 200)
        slots = response.json()

        self.assertNotIn("10:00", slots)
        self.assertNotIn("10:30", slots)
        self.assertIn("09:30", slots)
        self.assertIn("11:00", slots)