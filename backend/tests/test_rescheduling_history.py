import os
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo


class ReschedulingHistoryTests(unittest.TestCase):
    def test_history_constraint_accepts_only_valid_time_pairs(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        previous = datetime(2030, 1, 7, 8, tzinfo=timezone.utc)
        new = previous + timedelta(minutes=30)

        with psycopg.connect(test_url) as connection:
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
                        f"Synthetic History {uuid4()}",
                        "+306900000000",
                        "00000000000",
                        previous + timedelta(
                            microseconds=uuid4().int % 900000 + 1
                        ),
                    ),
                ).fetchone()[0]

                def insert_event(action, old_time, new_time):
                    connection.execute(
                        """
                        INSERT INTO audit_events (
                            actor_issuer, actor_subject,
                            action, appointment_id, correlation_id,
                            previous_starts_at, new_starts_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """,
                        (
                            "synthetic-issuer",
                            "synthetic-staff",
                            action,
                            appointment_id,
                            uuid4(),
                            old_time,
                            new_time,
                        ),
                    )

                # Existing events without recorded times remain valid.
                insert_event("appointment.rescheduled", None, None)
                insert_event("appointment.cancelled", None, None)

                # New rescheduling events can contain both times.
                insert_event("appointment.rescheduled", previous, new)

                invalid_events = [
                    ("appointment.rescheduled", previous, None),
                    ("appointment.rescheduled", None, new),
                    ("appointment.rescheduled", previous, previous),
                    ("appointment.cancelled", previous, new),
                ]

                for action, old_time, new_time in invalid_events:
                    with self.subTest(
                        action=action,
                        old_time=old_time,
                        new_time=new_time,
                    ):
                        with self.assertRaises(
                            psycopg.errors.CheckViolation
                        ):
                            # Savepoint keeps the outer transaction usable.
                            with connection.transaction():
                                insert_event(action, old_time, new_time)

                count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM audit_events
                    WHERE appointment_id = %s;
                    """,
                    (appointment_id,),
                ).fetchone()[0]

                self.assertEqual(count, 3)

            finally:
                # Remove all synthetic records, including successful inserts.
                connection.rollback()

