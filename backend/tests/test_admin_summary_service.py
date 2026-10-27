import unittest
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from admin_summary import get_admin_summary


class AdminSummaryServiceTests(unittest.TestCase):
    def test_today_is_based_on_athens_not_utc(self):
        # Sunday in UTC, already Monday in Athens.
        now = datetime(
            2030, 1, 6, 22, 30,
            tzinfo=ZoneInfo("UTC"),
        )
        counts = {
            "appointments_count": 0,
            "next_starts_at": None,
            "no_show_count": 0,
        }

        with patch(
            "admin_summary.get_appointment_summary_for_date",
            return_value=counts,
        ) as read, patch(
            "availability_service.get_booked_times_for_date",
            return_value=[],
        ), patch(
            "availability_service.get_active_blocks_for_date",
            return_value=[],
        ):
            result = get_admin_summary(now=now)

        self.assertEqual(result["date"], "2030-01-07")
        self.assertEqual(result["available_slots_count"], 16)

        read.assert_called_once_with(
            date(2030, 1, 7),
            now=now.astimezone(ZoneInfo("Europe/Athens")),
        )

    def test_available_count_excludes_past_booked_and_blocked_slots(self):
        clinic_timezone = ZoneInfo("Europe/Athens")
        now = datetime(
            2030, 1, 7, 10, 15,
            tzinfo=clinic_timezone,
        )
        next_start = datetime(
            2030, 1, 7, 10, 30,
            tzinfo=clinic_timezone,
        )
        counts = {
            "appointments_count": 5,
            "next_starts_at": next_start,
            "no_show_count": 1,
        }
        blocks = [
            {
                "starts_at": datetime(
                    2030, 1, 7, 11, 15,
                    tzinfo=clinic_timezone,
                ),
                "ends_at": datetime(
                    2030, 1, 7, 11, 45,
                    tzinfo=clinic_timezone,
                ),
            }
        ]

        with patch(
            "admin_summary.get_appointment_summary_for_date",
            return_value=counts,
        ), patch(
            "availability_service.get_booked_times_for_date",
            return_value=["10:30"],
        ), patch(
            "availability_service.get_active_blocks_for_date",
            return_value=blocks,
        ):
            result = get_admin_summary(now=now)

        # 13 future slots; one booked; two overlap the block.
        self.assertEqual(result["available_slots_count"], 10)
        self.assertEqual(result["appointments_count"], 5)
        self.assertEqual(result["no_show_count"], 1)
        self.assertEqual(
            datetime.fromisoformat(result["next_starts_at"]),
            next_start,
        )
        self.assertEqual(
            set(result),
            {
                "date",
                "appointments_count",
                "next_starts_at",
                "available_slots_count",
                "no_show_count",
            },
        )

    def test_weekend_and_after_closing_have_no_available_slots(self):
        clinic_timezone = ZoneInfo("Europe/Athens")
        times = [
            datetime(2030, 1, 6, 12, tzinfo=clinic_timezone),
            datetime(2030, 1, 7, 17, tzinfo=clinic_timezone),
        ]

        for now in times:
            with self.subTest(now=now):
                with patch(
                    "admin_summary.get_appointment_summary_for_date",
                    return_value={
                        "appointments_count": 0,
                        "next_starts_at": None,
                        "no_show_count": 0,
                    },
                ), patch(
                    "availability_service.get_booked_times_for_date",
                    return_value=[],
                ), patch(
                    "availability_service.get_active_blocks_for_date",
                    return_value=[],
                ):
                    result = get_admin_summary(now=now)

                self.assertEqual(result["available_slots_count"], 0)
                self.assertIsNone(result["next_starts_at"])