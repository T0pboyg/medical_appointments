import os
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from unittest.mock import patch

from database import (
    cancel_appointment_in_db,
    get_booked_times_for_date,
)

class CancellationTests(unittest.TestCase):
    def test_cancelled_slot_can_be_booked_again(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        marker = f"Cancellation Test {uuid4()}"
        starts_at = datetime.now(timezone.utc) + timedelta(days=30)

        with psycopg.connect(test_url) as connection:
            try:
                original_id = connection.execute(
                    """
                    INSERT INTO appointments (
                        patient_name, patient_phone,
                        patient_amka, starts_at
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        marker,
                        "+306900000000",
                        "00000000000",
                        starts_at,
                    ),
                ).fetchone()[0]

                connection.execute(
                    """
                    UPDATE appointments
                    SET cancelled_at = CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """,
                    (original_id,),
                )

                replacement_id = connection.execute(
                    """
                    INSERT INTO appointments (
                        patient_name, patient_phone,
                        patient_amka, starts_at
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        marker,
                        "+306900000000",
                        "00000000000",
                        starts_at,
                    ),
                ).fetchone()[0]

                self.assertNotEqual(original_id, replacement_id)

                counts = connection.execute(
                    """
                    SELECT
                        COUNT(*),
                        COUNT(*) FILTER (
                            WHERE cancelled_at IS NULL
                        )
                    FROM appointments
                    WHERE starts_at = %s;
                    """,
                    (starts_at,),
                ).fetchone()

                self.assertEqual(counts, (2, 1))
            finally:
                connection.rollback()



    def test_audit_failure_rolls_back_cancellation(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        marker = f"Cancellation Rollback Test {uuid4()}"
        starts_at = datetime.now(timezone.utc) + timedelta(days=30)

        with psycopg.connect(test_url, autocommit=True) as connection:
            appointment_id = connection.execute(
                """
                INSERT INTO appointments (
                    patient_name, patient_phone,
                    patient_amka, starts_at
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    marker,
                    "+306900000000",
                    "00000000000",
                    starts_at,
                ),
            ).fetchone()[0]

            try:
                with patch.dict(
                    os.environ,
                    {"DATABASE_URL": test_url},
                ):
                    with self.assertRaises(
                        psycopg.errors.NotNullViolation
                    ):
                        cancel_appointment_in_db(
                            appointment_id,
                            "test-issuer",
                            "test-subject",
                            None,
                        )

                cancelled_at = connection.execute(
                    """
                    SELECT cancelled_at
                    FROM appointments
                    WHERE id = %s;
                    """,
                    (appointment_id,),
                ).fetchone()[0]

                self.assertIsNone(cancelled_at)
            finally:
                connection.execute(
                    "DELETE FROM appointments WHERE id = %s",
                    (appointment_id,),
                )


    def test_cancellation_is_recorded_once(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        starts_at = datetime.now(timezone.utc) + timedelta(days=30)
        correlation_id = uuid4()

        with psycopg.connect(test_url, autocommit=True) as connection:
            appointment_id = connection.execute(
                """
                INSERT INTO appointments (
                    patient_name, patient_phone,
                    patient_amka, starts_at
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    f"Cancellation Test {uuid4()}",
                    "+306900000000",
                    "00000000000",
                    starts_at,
                ),
            ).fetchone()[0]

            try:
                with patch.dict(
                    os.environ,
                    {"DATABASE_URL": test_url},
                ):
                    first = cancel_appointment_in_db(
                        appointment_id,
                        "test-issuer",
                        "test-subject",
                        correlation_id,
                    )
                    second = cancel_appointment_in_db(
                        appointment_id,
                        "test-issuer",
                        "test-subject",
                        uuid4(),
                    )

                self.assertEqual(first["id"], appointment_id)
                self.assertIsNotNone(first["cancelled_at"])
                self.assertIsNone(second)

                events = connection.execute(
                    """
                    SELECT actor_issuer, actor_subject,
                           action, correlation_id
                    FROM audit_events
                    WHERE appointment_id = %s;
                    """,
                    (appointment_id,),
                ).fetchall()

                self.assertEqual(
                    events,
                    [(
                        "test-issuer",
                        "test-subject",
                        "appointment.cancelled",
                        correlation_id,
                    )],
                )
            finally:
                connection.execute(
                    "DELETE FROM audit_events WHERE appointment_id = %s",
                    (appointment_id,),
                )
                connection.execute(
                    "DELETE FROM appointments WHERE id = %s",
                    (appointment_id,),
                )


    def test_cancelled_appointment_does_not_block_availability(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        clinic_timezone = timezone(timedelta(hours=2))
        starts_at = datetime(
            datetime.now(timezone.utc).year + 1,
            1, 15, 10, 0,
            tzinfo=clinic_timezone,
        )

        with psycopg.connect(test_url, autocommit=True) as connection:
            appointment_id = connection.execute(
                """
                INSERT INTO appointments (
                    patient_name, patient_phone,
                    patient_amka, starts_at, cancelled_at
                )
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                RETURNING id;
                """,
                (
                    f"Cancelled Availability Test {uuid4()}",
                    "+306900000000",
                    "00000000000",
                    starts_at,
                ),
            ).fetchone()[0]

            try:
                with patch.dict(
                    os.environ,
                    {"DATABASE_URL": test_url},
                ):
                    booked = get_booked_times_for_date(
                        starts_at.date()
                    )

                self.assertNotIn("10:00", booked)
            finally:
                connection.execute(
                    "DELETE FROM appointments WHERE id = %s",
                    (appointment_id,),
                )

    def test_started_appointment_cannot_be_cancelled(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )

        with psycopg.connect(test_url, autocommit=True) as connection:
            appointment_id = connection.execute(
                """
                INSERT INTO appointments (
                    patient_name, patient_phone,
                    patient_amka, starts_at
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    f"Past Cancellation Test {uuid4()}",
                    "+306900000000",
                    "00000000000",
                    datetime.now(timezone.utc) - timedelta(minutes=5),
                ),
            ).fetchone()[0]

            try:
                with patch.dict(
                    os.environ,
                    {"DATABASE_URL": test_url},
                ):
                    result = cancel_appointment_in_db(
                        appointment_id,
                        "test-issuer",
                        "test-subject",
                        uuid4(),
                    )

                self.assertIsNone(result)

                cancelled_at = connection.execute(
                    "SELECT cancelled_at FROM appointments WHERE id = %s",
                    (appointment_id,),
                ).fetchone()[0]
                self.assertIsNone(cancelled_at)

                events = connection.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE appointment_id = %s",
                    (appointment_id,),
                ).fetchone()[0]
                self.assertEqual(events, 0)
            finally:
                connection.execute(
                    "DELETE FROM audit_events WHERE appointment_id = %s",
                    (appointment_id,),
                )
                connection.execute(
                    "DELETE FROM appointments WHERE id = %s",
                    (appointment_id,),
                )