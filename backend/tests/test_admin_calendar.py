import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from auth import require_staff
from main import app
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
from psycopg.conninfo import make_conninfo

from database import get_appointment_counts_for_month


class AdminCalendarRouteTests(unittest.TestCase):
    def setUp(self):
        self.previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[require_staff] = lambda: {
            "subject": "synthetic-staff"
        }
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.previous_overrides)

    def test_month_returns_counts_without_patient_details(self):
        days = [
            {"date": "2030-01-07", "count": 2},
            {"date": "2030-01-08", "count": 1},
        ]

        with patch(
            "main.get_appointment_counts_for_month",
            return_value=days,
        ) as read:
            response = self.client.get(
                "/appointments/calendar",
                params={"year": 2030, "month": 1},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["cache-control"], "no-store"
        )
        self.assertEqual(response.json(), {"days": days})
        read.assert_called_once_with(year=2030, month=1)

    def test_invalid_month_never_reaches_database(self):
        invalid_parameters = [
            {"year": 2030, "month": 0},
            {"year": 2030, "month": 13},
            {"year": 0, "month": 1},
            {"year": 10000, "month": 1},
            {"year": 2030},
            {"month": 1},
        ]

        for parameters in invalid_parameters:
            with self.subTest(parameters=parameters):
                with patch(
                    "main.get_appointment_counts_for_month"
                ) as read:
                    response = self.client.get(
                        "/appointments/calendar",
                        params=parameters,
                    )

                self.assertEqual(response.status_code, 422)
                read.assert_not_called()

    def test_calendar_requires_staff_login(self):
        app.dependency_overrides.pop(require_staff, None)

        with patch(
            "main.get_appointment_counts_for_month"
        ) as read:
            response = self.client.get(
                "/appointments/calendar",
                params={"year": 2030, "month": 1},
            )

        self.assertEqual(response.status_code, 401)
        read.assert_not_called()


class AdminCalendarDatabaseTests(unittest.TestCase):
    def test_month_bounds_daily_counts_and_cancelled_exclusion(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        clinic_timezone = ZoneInfo("Europe/Athens")

        # March includes the transition to summer time.
        start = datetime(
            2032, 3, 1, tzinfo=clinic_timezone
        ).astimezone(timezone.utc)
        end = datetime(
            2032, 4, 1, tzinfo=clinic_timezone
        ).astimezone(timezone.utc)

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
                before = {
                    row["date"]: row["count"]
                    for row in get_appointment_counts_for_month(
                        year=2032, month=3
                    )
                }

            try:
                records = [
                    (start - offset, None),  # February: excluded.
                    (start + offset, None),  # March 1.
                    (
                        start + timedelta(hours=1) + offset,
                        None,
                    ),                      # March 1 again.
                    (end - offset, None),   # March 31.
                    (end + offset, None),   # April: excluded.
                    (
                        start + timedelta(days=10) + offset,
                        datetime.now(timezone.utc),
                    ),                      # Cancelled: excluded.
                ]

                for starts_at, cancelled_at in records:
                    appointment_ids.append(
                        connection.execute(
                            """
                            INSERT INTO appointments (
                                patient_name, patient_phone,
                                patient_amka, starts_at,
                                cancelled_at
                            )
                            VALUES (%s, %s, %s, %s, %s)
                            RETURNING id;
                            """,
                            (
                                f"Synthetic Calendar {uuid4()}",
                                "+306900000000",
                                "00000000000",
                                starts_at,
                                cancelled_at,
                            ),
                        ).fetchone()[0]
                    )

                with patch.dict(
                    os.environ, {"DATABASE_URL": test_url}
                ):
                    rows = get_appointment_counts_for_month(
                        year=2032, month=3
                    )

                expected = before.copy()
                expected["2032-03-01"] = (
                    expected.get("2032-03-01", 0) + 2
                )
                expected["2032-03-31"] = (
                    expected.get("2032-03-31", 0) + 1
                )

                self.assertEqual(
                    {row["date"]: row["count"] for row in rows},
                    expected,
                )
                self.assertEqual(
                    [row["date"] for row in rows],
                    sorted(expected),
                )
                for row in rows:
                    self.assertEqual(
                        set(row), {"date", "count"}
                    )
            finally:
                connection.execute(
                    """
                    DELETE FROM appointments
                    WHERE id = ANY(%s);
                    """,
                    (appointment_ids,),
                )