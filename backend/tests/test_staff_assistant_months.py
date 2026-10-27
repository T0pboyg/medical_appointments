import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from staff_assistant_intent import resolve_period
from unittest.mock import patch
from staff_assistant import prepare_response


class StaffAssistantMonthTests(unittest.TestCase):
    def test_next_month_uses_calendar_boundaries(self):
        cases = [
            # Month with 30 days.
            ((2026, 10, 27), date(2026, 11, 1), date(2026, 11, 30)),
            # February, normal year.
            ((2027, 1, 31), date(2027, 2, 1), date(2027, 2, 28)),
            # February, leap year.
            ((2028, 1, 31), date(2028, 2, 1), date(2028, 2, 29)),
            # Month with 31 days.
            ((2026, 7, 15), date(2026, 8, 1), date(2026, 8, 31)),
            # Change of year.
            ((2026, 12, 31), date(2027, 1, 1), date(2027, 1, 31)),
        ]

        for today, expected_start, expected_end in cases:
            with self.subTest(today=today):
                now = datetime(
                    *today,
                    hour=12,
                    tzinfo=ZoneInfo("Europe/Athens"),
                )

                result = resolve_period(
                    "δείξε μου όλα τα ραντεβού του επόμενου μήνα",
                    now=now,
                )

                self.assertEqual(
                    result,
                    (expected_start, expected_end),
                )

    def test_current_and_previous_month_phrases(self):
        now = datetime(
            2027, 1, 15, 12,
            tzinfo=ZoneInfo("Europe/Athens"),
        )

        cases = [
            (
                "δείξε τα ραντεβού αυτόν τον μήνα",
                (date(2027, 1, 1), date(2027, 1, 31)),
            ),
            (
                "δείξε τα ραντεβού του τρέχοντος μήνα",
                (date(2027, 1, 1), date(2027, 1, 31)),
            ),
            (
                "δείξε τα ραντεβού τον προηγούμενο μήνα",
                (date(2026, 12, 1), date(2026, 12, 31)),
            ),
            (
                "δείξε τα ραντεβού του περασμένου μήνα",
                (date(2026, 12, 1), date(2026, 12, 31)),
            ),
        ]

        for message, expected in cases:
            with self.subTest(message=message):
                self.assertEqual(
                    resolve_period(message, now=now),
                    expected,
                )

    def test_month_is_based_on_athens_date(self):
        # In UTC it is still December; in Athens it is January.
        now = datetime(
            2026, 12, 31, 22, 30,
            tzinfo=ZoneInfo("UTC"),
        )

        self.assertEqual(
            resolve_period(
                "δείξε τα ραντεβού του επόμενου μήνα",
                now=now,
            ),
            (date(2027, 2, 1), date(2027, 2, 28)),
        )

    
    def test_monthly_list_searches_every_day_and_displays_period(self):
        now = datetime(
            2026, 10, 27, 12,
            tzinfo=ZoneInfo("Europe/Athens"),
        )
        session = {
            "issuer": "synthetic-issuer",
            "subject": "synthetic-staff",
            "csrf_token": "synthetic-csrf",
        }
        appointment = {
            "id": 42,
            "patient_name": "Synthetic Patient",
            "starts_at": datetime(
                2026, 11, 9, 10,
                tzinfo=ZoneInfo("Europe/Athens"),
            ),
        }

        def lookup(*, day, appointment_id, future_only):
            if day == date(2026, 11, 9):
                return [appointment]
            return []

        with patch(
            "staff_assistant.find_staff_appointments",
            side_effect=lookup,
        ) as read:
            result = prepare_response(
                "δείξε μου όλα τα ραντεβού του επόμενου μήνα",
                {
                    "action": "list",
                    "patient_name": None,
                    "appointment_id": None,
                },
                session,
                now=now,
            )

        self.assertEqual(read.call_count, 30)
        self.assertEqual(
            [call.kwargs["day"] for call in read.call_args_list],
            [date(2026, 11, day) for day in range(1, 31)],
        )
        self.assertTrue(all(
            call.kwargs["future_only"] is False
            for call in read.call_args_list
        ))
        self.assertIn("01/11/2026", result["answer"])
        self.assertIn("30/11/2026", result["answer"])
        self.assertEqual(
            [item["id"] for item in result["appointments"]],
            [42],
        )
        self.assertNotIn(
            "confirmation_token",
            result["appointments"][0],
        )

    def test_ambiguous_month_does_not_allow_id_only_cancellation(self):
        session = {
            "issuer": "synthetic-issuer",
            "subject": "synthetic-staff",
            "csrf_token": "synthetic-csrf",
        }
        now = datetime(
            2026, 10, 27, 12,
            tzinfo=ZoneInfo("Europe/Athens"),
        )

        with patch(
            "staff_assistant.find_staff_appointments",
            side_effect=AssertionError(
                "An ambiguous month must not be ignored."
            ),
        ):
            result = prepare_response(
                "ακύρωσε το ραντεβού #42 "
                "τον επόμενο ή τον προηγούμενο μήνα",
                {
                    "action": "cancel",
                    "patient_name": None,
                    "appointment_id": 42,
                },
                session,
                now=now,
            )

        self.assertFalse(result.get("appointments"))
    

    def test_named_month_without_year_uses_current_year(self):
        now = datetime(
            2026, 10, 27, 12,
            tzinfo=ZoneInfo("Europe/Athens"),
        )

        cases = [
            ("του Νοέμβρη", date(2026, 11, 1), date(2026, 11, 30)),
            ("του Νοεμβρίου", date(2026, 11, 1), date(2026, 11, 30)),
            ("τον Νοέμβριο", date(2026, 11, 1), date(2026, 11, 30)),
            ("του Γενάρη", date(2026, 1, 1), date(2026, 1, 31)),
            ("του Ιανουαρίου", date(2026, 1, 1), date(2026, 1, 31)),
        ]

        for phrase, start, end in cases:
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    resolve_period(
                        f"δείξε μου όλα τα ραντεβού {phrase}",
                        now=now,
                    ),
                    (start, end),
                )

    def test_named_month_with_explicit_year(self):
        now = datetime(
            2026, 10, 27, 12,
            tzinfo=ZoneInfo("Europe/Athens"),
        )

        cases = [
            ("του Νοεμβρίου 2027", date(2027, 11, 1), date(2027, 11, 30)),
            ("του Φλεβάρη 2028", date(2028, 2, 1), date(2028, 2, 29)),
            ("του Φεβρουαρίου 2027", date(2027, 2, 1), date(2027, 2, 28)),
            ("του Δεκεμβρίου 2026", date(2026, 12, 1), date(2026, 12, 31)),
        ]

        for phrase, start, end in cases:
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    resolve_period(
                        f"δείξε τα ραντεβού {phrase}",
                        now=now,
                    ),
                    (start, end),
                )

    def test_named_month_rejects_conflicting_constraints(self):
        now = datetime(
            2026, 10, 27, 12,
            tzinfo=ZoneInfo("Europe/Athens"),
        )

        messages = [
            "δείξε τα ραντεβού Νοεμβρίου ή Δεκεμβρίου",
            "δείξε τα ραντεβού Νοεμβρίου 2027 ή 2028",
            "δείξε τα ραντεβού στις 7 Νοεμβρίου 2027",
            "δείξε τα ραντεβού Νοεμβρίου την επόμενη εβδομάδα",
            "δείξε τα ραντεβού Νοεμβρίου 0000",
        ]

        for message in messages:
            with self.subTest(message=message):
                self.assertIsNone(
                    resolve_period(message, now=now)
                )