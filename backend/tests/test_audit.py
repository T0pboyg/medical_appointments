import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import psycopg
from psycopg.conninfo import make_conninfo

from database import update_appointment_no_show


class AuditTests(unittest.TestCase):
    def test_audit_failure_rolls_back_attendance(self):
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
                    "Audit Test",
                    "+306900000000",
                    "00000000000",
                    datetime.now(timezone.utc) - timedelta(days=1),
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
                        update_appointment_no_show(
                            appointment_id,
                            True,
                            "test-issuer",
                            "test-subject",
                            None,
                        )

                no_show = connection.execute(
                    "SELECT no_show FROM appointments WHERE id = %s",
                    (appointment_id,),
                ).fetchone()[0]

                self.assertFalse(no_show)
            finally:
                connection.execute(
                    "DELETE FROM appointments WHERE id = %s",
                    (appointment_id,),
                )