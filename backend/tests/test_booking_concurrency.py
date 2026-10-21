import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo

from database import create_appointment_in_db


class BookingConcurrencyTests(unittest.TestCase):
    def test_same_slot_can_only_be_booked_once(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
            connect_timeout=5,
            options="-c statement_timeout=10000",
        )
        marker = f"Concurrency Test {uuid4()}"
        starts_at = datetime.now(timezone.utc) + timedelta(days=30)
        barrier = Barrier(2)

        def book():
            barrier.wait(timeout=10)

            try:
                create_appointment_in_db(
                    marker,
                    "+306900000000",
                    "00000000000",
                    starts_at,
                )
                return "created"
            except psycopg.errors.UniqueViolation:
                return "conflict"

        with psycopg.connect(test_url, autocommit=True) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT current_database()"
                ).fetchone()[0],
                "appointments_migration_test",
            )

            try:
                with patch.dict(os.environ, {"DATABASE_URL": test_url}):
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        futures = [
                            executor.submit(book),
                            executor.submit(book),
                        ]
                        results = [
                            future.result(timeout=20)
                            for future in futures
                        ]

                self.assertCountEqual(
                    results,
                    ["created", "conflict"],
                )

                count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM appointments
                    WHERE starts_at = %s;
                    """,
                    (starts_at,),
                ).fetchone()[0]

                self.assertEqual(count, 1)
            finally:
                connection.execute(
                    """
                    DELETE FROM appointments
                    WHERE patient_name = %s AND starts_at = %s;
                    """,
                    (marker, starts_at),
                )