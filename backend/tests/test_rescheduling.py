import os
import unittest
from datetime import datetime, time, timedelta
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
from psycopg.conninfo import make_conninfo

from database import reschedule_appointment_in_db


class ReschedulingTests(unittest.TestCase):
    def test_reschedule_preserves_identity_and_records_audit(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        clinic_timezone = ZoneInfo("Europe/Athens")

        day = (
            datetime.now(clinic_timezone).date()
            + timedelta(days=365 + uuid4().int % 3000)
        )
        while day.weekday() >= 5:
            day += timedelta(days=1)

        original_start = datetime.combine(
            day, time(9), tzinfo=clinic_timezone
        )
        new_start = original_start + timedelta(minutes=30)
        marker = f"Synthetic Rescheduling {uuid4()}"
        correlation_id = uuid4()

        with psycopg.connect(
            test_url, autocommit=True
        ) as connection:
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
                    original_start,
                ),
            ).fetchone()[0]

            try:
                with patch.dict(
                    os.environ, {"DATABASE_URL": test_url}
                ):
                    result = reschedule_appointment_in_db(
                        appointment_id,
                        new_start,
                        "synthetic-issuer",
                        "synthetic-staff",
                        correlation_id,
                        expected_starts_at=original_start,
                    )

                self.assertEqual(result["id"], appointment_id)
                self.assertEqual(result["starts_at"], new_start)

                saved = connection.execute(
                    """
                    SELECT patient_name, patient_phone,
                           patient_amka, starts_at,
                           cancelled_at, no_show
                    FROM appointments
                    WHERE id = %s;
                    """,
                    (appointment_id,),
                ).fetchone()

                self.assertEqual(
                    saved,
                    (
                        marker,
                        "+306900000000",
                        "00000000000",
                        new_start,
                        None,
                        False,
                    ),
                )

                events = connection.execute(
                    """
                    SELECT action, actor_issuer,
                           actor_subject, correlation_id
                    FROM audit_events
                    WHERE appointment_id = %s;
                    """,
                    (appointment_id,),
                ).fetchall()

                self.assertEqual(
                    events,
                    [
                        (
                            "appointment.rescheduled",
                            "synthetic-issuer",
                            "synthetic-staff",
                            correlation_id,
                        )
                    ],
                )
                recorded_times = connection.execute(
                    """
                    SELECT previous_starts_at, new_starts_at
                    FROM audit_events
                    WHERE appointment_id = %s
                      AND action = 'appointment.rescheduled';
                    """,
                    (appointment_id,),
                ).fetchall()

                self.assertEqual(
                    recorded_times,
                    [(original_start, new_start)],
                )
            finally:
                connection.execute(
                    """
                    DELETE FROM audit_events
                    WHERE appointment_id = %s;
                    """,
                    (appointment_id,),
                )
                connection.execute(
                    "DELETE FROM appointments WHERE id = %s;",
                    (appointment_id,),
                )
    

    def test_occupied_slot_preserves_original_appointment(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        clinic_timezone = ZoneInfo("Europe/Athens")

        day = (
            datetime.now(clinic_timezone).date()
            + timedelta(days=365 + uuid4().int % 3000)
        )
        while day.weekday() >= 5:
            day += timedelta(days=1)

        original_start = datetime.combine(
            day, time(10), tzinfo=clinic_timezone
        )
        occupied_start = original_start + timedelta(minutes=30)
        marker = f"Synthetic Occupied Slot {uuid4()}"
        appointment_ids = []

        with psycopg.connect(
            test_url, autocommit=True
        ) as connection:
            try:
                for starts_at in (original_start, occupied_start):
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
                    appointment_ids.append(appointment_id)

                original_id, occupied_id = appointment_ids

                with patch.dict(
                    os.environ, {"DATABASE_URL": test_url}
                ):
                    with self.assertRaises(
                        psycopg.errors.UniqueViolation
                    ):
                        reschedule_appointment_in_db(
                            original_id,
                            occupied_start,
                            "synthetic-issuer",
                            "synthetic-staff",
                            uuid4(),
                            expected_starts_at=original_start,
                        )

                for appointment_id, expected_start in (
                    (original_id, original_start),
                    (occupied_id, occupied_start),
                ):
                    saved = connection.execute(
                        """
                        SELECT starts_at, cancelled_at
                        FROM appointments
                        WHERE id = %s;
                        """,
                        (appointment_id,),
                    ).fetchone()

                    self.assertEqual(
                        saved, (expected_start, None)
                    )

                audit_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM audit_events
                    WHERE appointment_id = ANY(%s)
                      AND action = 'appointment.rescheduled';
                    """,
                    (appointment_ids,),
                ).fetchone()[0]

                self.assertEqual(audit_count, 0)
            finally:
                connection.execute(
                    """
                    DELETE FROM audit_events
                    WHERE appointment_id = ANY(%s);
                    """,
                    (appointment_ids,),
                )
                connection.execute(
                    """
                    DELETE FROM appointments
                    WHERE id = ANY(%s);
                    """,
                    (appointment_ids,),
                )

    
    def test_blocked_slot_preserves_original_appointment(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        clinic_timezone = ZoneInfo("Europe/Athens")

        day = (
            datetime.now(clinic_timezone).date()
            + timedelta(days=365 + uuid4().int % 3000)
        )
        while day.weekday() >= 5:
            day += timedelta(days=1)

        original_start = datetime.combine(
            day, time(11), tzinfo=clinic_timezone
        )
        new_start = original_start + timedelta(hours=1)
        appointment_id = None
        block_id = None

        with psycopg.connect(
            test_url, autocommit=True
        ) as connection:
            try:
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
                        f"Synthetic Blocked Move {uuid4()}",
                        "+306900000000",
                        "00000000000",
                        original_start,
                    ),
                ).fetchone()[0]

                # Overlaps only the final 15 minutes of the new slot.
                block_id = connection.execute(
                    """
                    INSERT INTO availability_blocks (
                        starts_at, ends_at, reason
                    )
                    VALUES (%s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        new_start + timedelta(minutes=15),
                        new_start + timedelta(minutes=45),
                        "Synthetic rescheduling test",
                    ),
                ).fetchone()[0]

                with patch.dict(
                    os.environ, {"DATABASE_URL": test_url}
                ):
                    with self.assertRaises(
                        psycopg.errors.CheckViolation
                    ):
                        reschedule_appointment_in_db(
                            appointment_id,
                            new_start,
                            "synthetic-issuer",
                            "synthetic-staff",
                            uuid4(),
                            expected_starts_at=original_start,
                        )

                saved = connection.execute(
                    """
                    SELECT starts_at, cancelled_at
                    FROM appointments
                    WHERE id = %s;
                    """,
                    (appointment_id,),
                ).fetchone()

                self.assertEqual(saved, (original_start, None))

                audit_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM audit_events
                    WHERE appointment_id = %s
                      AND action = 'appointment.rescheduled';
                    """,
                    (appointment_id,),
                ).fetchone()[0]

                self.assertEqual(audit_count, 0)
            finally:
                connection.execute(
                    "DELETE FROM audit_events WHERE appointment_id = %s;",
                    (appointment_id,),
                )
                connection.execute(
                    "DELETE FROM appointments WHERE id = %s;",
                    (appointment_id,),
                )
                connection.execute(
                    "DELETE FROM availability_blocks WHERE id = %s;",
                    (block_id,),
                )


    def test_audit_failure_rolls_back_rescheduling(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        clinic_timezone = ZoneInfo("Europe/Athens")

        day = (
            datetime.now(clinic_timezone).date()
            + timedelta(days=365 + uuid4().int % 3000)
        )
        while day.weekday() >= 5:
            day += timedelta(days=1)

        original_start = datetime.combine(
            day, time(14), tzinfo=clinic_timezone
        )
        new_start = original_start + timedelta(minutes=30)
        appointment_id = None

        with psycopg.connect(
            test_url, autocommit=True
        ) as connection:
            try:
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
                        f"Synthetic Audit Rollback {uuid4()}",
                        "+306900000000",
                        "00000000000",
                        original_start,
                    ),
                ).fetchone()[0]

                with patch.dict(
                    os.environ, {"DATABASE_URL": test_url}
                ):
                    # correlation_id is NOT NULL in audit_events.
                    # The UPDATE runs first; the audit INSERT must fail.
                    with self.assertRaises(
                        psycopg.errors.NotNullViolation
                    ):
                        reschedule_appointment_in_db(
                            appointment_id,
                            new_start,
                            "synthetic-issuer",
                            "synthetic-staff",
                            None,
                            expected_starts_at=original_start,
                        )

                saved = connection.execute(
                    """
                    SELECT starts_at, cancelled_at
                    FROM appointments
                    WHERE id = %s;
                    """,
                    (appointment_id,),
                ).fetchone()

                self.assertEqual(saved, (original_start, None))

                audit_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM audit_events
                    WHERE appointment_id = %s;
                    """,
                    (appointment_id,),
                ).fetchone()[0]

                self.assertEqual(audit_count, 0)
            finally:
                connection.execute(
                    "DELETE FROM audit_events WHERE appointment_id = %s;",
                    (appointment_id,),
                )
                connection.execute(
                    "DELETE FROM appointments WHERE id = %s;",
                    (appointment_id,),
                )


    def test_stale_request_does_not_overwrite_new_time(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        clinic_timezone = ZoneInfo("Europe/Athens")

        day = (
            datetime.now(clinic_timezone).date()
            + timedelta(days=365 + uuid4().int % 3000)
        )
        while day.weekday() >= 5:
            day += timedelta(days=1)

        original_start = datetime.combine(
            day, time(15), tzinfo=clinic_timezone
        )
        first_new_start = original_start + timedelta(minutes=30)
        stale_new_start = original_start + timedelta(hours=1)
        appointment_id = None

        with psycopg.connect(
            test_url, autocommit=True
        ) as connection:
            try:
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
                        f"Synthetic Stale Move {uuid4()}",
                        "+306900000000",
                        "00000000000",
                        original_start,
                    ),
                ).fetchone()[0]

                first_correlation_id = uuid4()

                with patch.dict(
                    os.environ, {"DATABASE_URL": test_url}
                ):
                    first = reschedule_appointment_in_db(
                        appointment_id,
                        first_new_start,
                        "synthetic-issuer",
                        "synthetic-staff",
                        first_correlation_id,
                        expected_starts_at=original_start,
                    )
                    self.assertEqual(
                        first["starts_at"], first_new_start
                    )

                    stale = reschedule_appointment_in_db(
                        appointment_id,
                        stale_new_start,
                        "synthetic-issuer",
                        "synthetic-staff",
                        uuid4(),
                        expected_starts_at=original_start,
                    )

                self.assertIsNone(stale)

                saved_start = connection.execute(
                    """
                    SELECT starts_at
                    FROM appointments
                    WHERE id = %s;
                    """,
                    (appointment_id,),
                ).fetchone()[0]

                self.assertEqual(saved_start, first_new_start)

                events = connection.execute(
                    """
                    SELECT action, correlation_id
                    FROM audit_events
                    WHERE appointment_id = %s;
                    """,
                    (appointment_id,),
                ).fetchall()

                self.assertEqual(
                    events,
                    [
                        (
                            "appointment.rescheduled",
                            first_correlation_id,
                        )
                    ],
                )

            finally:
                connection.execute(
                    "DELETE FROM audit_events WHERE appointment_id = %s;",
                    (appointment_id,),
                )
                connection.execute(
                    "DELETE FROM appointments WHERE id = %s;",
                    (appointment_id,),
                )
