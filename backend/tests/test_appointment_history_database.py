import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo

from database import get_appointment_history_from_db


class AppointmentHistoryDatabaseTests(unittest.TestCase):
    def test_app_role_reads_paginated_history_in_stable_order(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        stamp = datetime.now(timezone.utc)
        starts_at = stamp + timedelta(days=365)
        appointment_ids = []
        event_ids = []

        # Save the real function before patching the database connection.
        real_connect = psycopg.connect

        def connect_as_app(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            try:
                connection.execute("SET ROLE appointments_app;")
                role = connection.execute(
                    "SELECT current_user;"
                ).fetchone()
                self.assertEqual(
                    role["current_user"], "appointments_app"
                )
                return connection
            except Exception:
                connection.close()
                raise

        with real_connect(
            test_url, autocommit=True
        ) as connection:
            try:
                for index in range(2):
                    appointment_ids.append(
                        connection.execute(
                            """
                            INSERT INTO appointments (
                                patient_name, patient_phone,
                                patient_amka, starts_at
                            )
                            VALUES (%s, %s, %s, %s)
                            RETURNING id;
                            """,
                            (
                                f"Synthetic History Read {uuid4()}",
                                "+306900000000",
                                "00000000000",
                                starts_at + timedelta(hours=index),
                            ),
                        ).fetchone()[0]
                    )

                target_id, empty_id = appointment_ids

                # Equal timestamps exercise the descending ID tie-breaker.
                for index in range(3):
                    previous = (
                        None if index == 0
                        else starts_at + timedelta(minutes=30 * index)
                    )
                    new = (
                        None if previous is None
                        else previous + timedelta(minutes=30)
                    )

                    event_ids.append(
                        connection.execute(
                            """
                            INSERT INTO audit_events (
                                occurred_at, actor_issuer,
                                actor_subject, action,
                                appointment_id, correlation_id,
                                previous_starts_at, new_starts_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id;
                            """,
                            (
                                stamp,
                                "synthetic-issuer",
                                "synthetic-staff",
                                "appointment.rescheduled",
                                target_id,
                                uuid4(),
                                previous,
                                new,
                            ),
                        ).fetchone()[0]
                    )

                with patch.dict(
                    os.environ, {"DATABASE_URL": test_url}
                ), patch(
                    "database.psycopg.connect",
                    side_effect=connect_as_app,
                ):
                    first = get_appointment_history_from_db(
                        target_id, page=1, page_size=2
                    )
                    second = get_appointment_history_from_db(
                        target_id, page=2, page_size=2
                    )
                    empty = get_appointment_history_from_db(empty_id)

                self.assertEqual(
                    [event["id"] for event in first["events"]],
                    [event_ids[2], event_ids[1]],
                )
                self.assertEqual(
                    [event["id"] for event in second["events"]],
                    [event_ids[0]],
                )
                self.assertTrue(first["has_more"])
                self.assertFalse(second["has_more"])

                # Old events remain readable without invented times.
                legacy_event = second["events"][0]
                self.assertIsNone(legacy_event["previous_starts_at"])
                self.assertIsNone(legacy_event["new_starts_at"])

                self.assertEqual(empty["events"], [])
                self.assertFalse(empty["has_more"])

                expected_fields = {
                    "id", "occurred_at",
                    "actor_issuer", "actor_subject", "action",
                    "previous_starts_at", "new_starts_at",
                }
                for event in first["events"] + second["events"]:
                    self.assertEqual(set(event), expected_fields)
            finally:
                connection.execute(
                    """
                    DELETE FROM audit_events
                    WHERE appointment_id = ANY(%s);
                    """,
                    (appointment_ids,),
                )
                connection.execute(
                    "DELETE FROM appointments WHERE id = ANY(%s);",
                    (appointment_ids,),
                )