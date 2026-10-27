import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
from psycopg.conninfo import make_conninfo

from database import get_appointment_summary_for_date


class AdminSummaryDatabaseTests(unittest.TestCase):
    def test_counts_ignore_pagination_cancelled_and_other_days(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        clinic_timezone = ZoneInfo("Europe/Athens")
        now = datetime(
            2030, 1, 7, 12,
            tzinfo=clinic_timezone,
        )
        day = now.date()
        midnight = now.replace(hour=0)
        offset = timedelta(
            microseconds=uuid4().int % 900000 + 1
        )
        appointment_ids = []

        with psycopg.connect(
            test_url, autocommit=True
        ) as connection:
            with patch.dict(
                os.environ, {"DATABASE_URL": test_url}
            ):
                before = get_appointment_summary_for_date(
                    day, now=now
                )

            try:
                # 26 past appointments, including one no-show.
                # Deliberate synthetic timestamps test SQL aggregation,
                # independently of booking-form validation.
                records = [
                    (
                        midnight
                        + timedelta(hours=9, seconds=index)
                        + offset,
                        index == 0,
                        None,
                    )
                    for index in range(26)
                ]

                next_start = (
                    midnight + timedelta(hours=13) + offset
                )

                records.extend([
                    (next_start, False, None),
                    (
                        midnight + timedelta(hours=14) + offset,
                        False,
                        None,
                    ),
                    # Earlier future appointment, but cancelled.
                    (
                        midnight + timedelta(hours=12, minutes=30)
                        + offset,
                        False,
                        now,
                    ),
                    # Outside the selected day.
                    (
                        midnight - timedelta(seconds=1) + offset,
                        True,
                        None,
                    ),
                    (
                        midnight + timedelta(days=1) + offset,
                        True,
                        None,
                    ),
                ])

                for starts_at, no_show, cancelled_at in records:
                    appointment_ids.append(
                        connection.execute(
                            """
                            INSERT INTO appointments (
                                patient_name, patient_phone,
                                patient_amka, starts_at,
                                no_show, cancelled_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id;
                            """,
                            (
                                f"Synthetic Summary {uuid4()}",
                                "+306900000000",
                                "00000000000",
                                starts_at,
                                no_show,
                                cancelled_at,
                            ),
                        ).fetchone()[0]
                    )

                with patch.dict(
                    os.environ, {"DATABASE_URL": test_url}
                ):
                    result = get_appointment_summary_for_date(
                        day, now=now
                    )

                self.assertEqual(
                    result["appointments_count"],
                    before["appointments_count"] + 28,
                )
                self.assertEqual(
                    result["no_show_count"],
                    before["no_show_count"] + 1,
                )

                expected_next = next_start
                if before["next_starts_at"] is not None:
                    expected_next = min(
                        expected_next,
                        before["next_starts_at"],
                    )

                self.assertEqual(
                    result["next_starts_at"],
                    expected_next,
                )
                self.assertEqual(
                    set(result),
                    {
                        "appointments_count",
                        "no_show_count",
                        "next_starts_at",
                    },
                )
            finally:
                connection.execute(
                    """
                    DELETE FROM appointments
                    WHERE id = ANY(%s);
                    """,
                    (appointment_ids,),
                )