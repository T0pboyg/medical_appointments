import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from zoneinfo import ZoneInfo

from database import (
    create_appointment_in_db,
    create_availability_block,
    get_active_blocks_for_date,
    release_availability_block,
)

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier


class AvailabilityBlockTests(unittest.TestCase):
    def test_block_creation_records_audit(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        starts_at = datetime.now(timezone.utc) + timedelta(days=60)
        ends_at = starts_at + timedelta(hours=1)
        correlation_id = uuid4()
        reason = f"Block Test {uuid4()}"

        with psycopg.connect(test_url, autocommit=True) as connection:
            try:
                with patch.dict(
                    os.environ,
                    {"DATABASE_URL": test_url},
                ):
                    block = create_availability_block(
                        starts_at,
                        ends_at,
                        reason,
                        "test-issuer",
                        "test-subject",
                        correlation_id,
                    )

                self.assertIsNotNone(block)
                self.assertEqual(block["starts_at"], starts_at)
                self.assertEqual(block["ends_at"], ends_at)

                events = connection.execute(
                    """
                    SELECT actor_issuer, actor_subject, action,
                           appointment_id, correlation_id
                    FROM audit_events
                    WHERE availability_block_id = %s;
                    """,
                    (block["id"],),
                ).fetchall()

                self.assertEqual(
                    events,
                    [(
                        "test-issuer",
                        "test-subject",
                        "availability_block.created",
                        None,
                        correlation_id,
                    )],
                )
            finally:
                connection.execute(
                    """
                    DELETE FROM audit_events
                    WHERE availability_block_id IN (
                        SELECT id FROM availability_blocks
                        WHERE reason = %s
                    );
                    """,
                    (reason,),
                )
                connection.execute(
                    "DELETE FROM availability_blocks WHERE reason = %s",
                    (reason,),
                )


    def test_block_overlapping_appointment_is_rejected(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        starts_at = datetime.now(timezone.utc) + timedelta(days=60)
        reason = f"Overlap Block Test {uuid4()}"

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
                    f"Block Appointment Test {uuid4()}",
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
                    result = create_availability_block(
                        starts_at + timedelta(minutes=15),
                        starts_at + timedelta(hours=1),
                        reason,
                        "test-issuer",
                        "test-subject",
                        uuid4(),
                    )

                self.assertIsNone(result)

                count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM availability_blocks
                    WHERE reason = %s;
                    """,
                    (reason,),
                ).fetchone()[0]

                self.assertEqual(count, 0)
            finally:
                connection.execute(
                    """
                    DELETE FROM audit_events
                    WHERE availability_block_id IN (
                        SELECT id FROM availability_blocks
                        WHERE reason = %s
                    );
                    """,
                    (reason,),
                )
                connection.execute(
                    "DELETE FROM availability_blocks WHERE reason = %s",
                    (reason,),
                )
                connection.execute(
                    "DELETE FROM appointments WHERE id = %s",
                    (appointment_id,),
                )


    def test_overlapping_blocks_are_rejected(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        starts_at = datetime.now(timezone.utc) + timedelta(days=60)
        reason = f"Overlapping Blocks Test {uuid4()}"

        with psycopg.connect(test_url, autocommit=True) as connection:
            try:
                with patch.dict(
                    os.environ,
                    {"DATABASE_URL": test_url},
                ):
                    first = create_availability_block(
                        starts_at,
                        starts_at + timedelta(hours=1),
                        reason,
                        "test-issuer",
                        "test-subject",
                        uuid4(),
                    )
                    second = create_availability_block(
                        starts_at + timedelta(minutes=30),
                        starts_at + timedelta(hours=2),
                        reason,
                        "test-issuer",
                        "test-subject",
                        uuid4(),
                    )

                self.assertIsNotNone(first)
                self.assertIsNone(second)

                count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM availability_blocks
                    WHERE reason = %s;
                    """,
                    (reason,),
                ).fetchone()[0]

                self.assertEqual(count, 1)
            finally:
                connection.execute(
                    """
                    DELETE FROM audit_events
                    WHERE availability_block_id IN (
                        SELECT id FROM availability_blocks
                        WHERE reason = %s
                    );
                    """,
                    (reason,),
                )
                connection.execute(
                    "DELETE FROM availability_blocks WHERE reason = %s",
                    (reason,),
                )


    def test_booking_overlapping_block_is_rejected(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        starts_at = datetime.now(timezone.utc) + timedelta(days=60)
        marker = f"Blocked Booking Test {uuid4()}"

        with psycopg.connect(test_url, autocommit=True) as connection:
            try:
                with patch.dict(
                    os.environ,
                    {"DATABASE_URL": test_url},
                ):
                    block = create_availability_block(
                        starts_at + timedelta(minutes=15),
                        starts_at + timedelta(hours=1),
                        marker,
                        "test-issuer",
                        "test-subject",
                        uuid4(),
                    )
                    self.assertIsNotNone(block)

                    with self.assertRaises(
                        psycopg.errors.CheckViolation
                    ):
                        create_appointment_in_db(
                            marker,
                            "+306900000000",
                            "00000000000",
                            starts_at,
                        )

                count = connection.execute(
                    """
                    SELECT COUNT(*) FROM appointments
                    WHERE patient_name = %s;
                    """,
                    (marker,),
                ).fetchone()[0]

                self.assertEqual(count, 0)
            finally:
                connection.execute(
                    "DELETE FROM appointments WHERE patient_name = %s",
                    (marker,),
                )
                connection.execute(
                    """
                    DELETE FROM audit_events
                    WHERE availability_block_id IN (
                        SELECT id FROM availability_blocks
                        WHERE reason = %s
                    );
                    """,
                    (marker,),
                )
                connection.execute(
                    "DELETE FROM availability_blocks WHERE reason = %s",
                    (marker,),
                )

    def test_blocks_from_previous_day_are_returned(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        clinic_timezone = ZoneInfo("Europe/Athens")
        year = datetime.now(clinic_timezone).year + 1
        day_start = datetime(
            year, 1, 15, 0, 0,
            tzinfo=clinic_timezone,
        )
        starts_at = day_start - timedelta(hours=1)
        ends_at = day_start + timedelta(hours=10)
        reason = f"Cross Day Block Test {uuid4()}"

        with psycopg.connect(test_url, autocommit=True) as connection:
            block_id = connection.execute(
                """
                INSERT INTO availability_blocks (
                    starts_at, ends_at, reason
                )
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (starts_at, ends_at, reason),
            ).fetchone()[0]

            try:
                with patch.dict(
                    os.environ,
                    {"DATABASE_URL": test_url},
                ):
                    blocks = get_active_blocks_for_date(
                        day_start.date()
                    )

                self.assertIn(
                    {
                        "starts_at": starts_at,
                        "ends_at": ends_at,
                    },
                    blocks,
                )
            finally:
                connection.execute(
                    "DELETE FROM availability_blocks WHERE id = %s",
                    (block_id,),
                )


    def test_audit_failure_rolls_back_block_creation(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        starts_at = datetime.now(timezone.utc) + timedelta(days=60)
        reason = f"Block Rollback Test {uuid4()}"

        with psycopg.connect(test_url, autocommit=True) as connection:
            try:
                with patch.dict(
                    os.environ,
                    {"DATABASE_URL": test_url},
                ):
                    with self.assertRaises(
                        psycopg.errors.NotNullViolation
                    ):
                        create_availability_block(
                            starts_at,
                            starts_at + timedelta(hours=1),
                            reason,
                            "test-issuer",
                            "test-subject",
                            None,
                        )

                count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM availability_blocks
                    WHERE reason = %s;
                    """,
                    (reason,),
                ).fetchone()[0]

                self.assertEqual(count, 0)
            finally:
                connection.execute(
                    """
                    DELETE FROM audit_events
                    WHERE availability_block_id IN (
                        SELECT id FROM availability_blocks
                        WHERE reason = %s
                    );
                    """,
                    (reason,),
                )
                connection.execute(
                    "DELETE FROM availability_blocks WHERE reason = %s",
                    (reason,),
                )


    def test_concurrent_booking_and_block_cannot_both_succeed(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
            connect_timeout=5,
            options="-c statement_timeout=10000",
        )
        starts_at = datetime.now(timezone.utc) + timedelta(days=60)
        marker = f"Concurrent Block Test {uuid4()}"
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
                return "booking"
            except psycopg.errors.CheckViolation:
                return "rejected"

        def block():
            barrier.wait(timeout=10)

            result = create_availability_block(
                starts_at,
                starts_at + timedelta(hours=1),
                marker,
                "test-issuer",
                "test-subject",
                uuid4(),
            )

            return "block" if result is not None else "rejected"

        with psycopg.connect(test_url, autocommit=True) as connection:
            try:
                with patch.dict(
                    os.environ,
                    {"DATABASE_URL": test_url},
                ):
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        futures = [
                            executor.submit(book),
                            executor.submit(block),
                        ]
                        results = [
                            future.result(timeout=20)
                            for future in futures
                        ]

                self.assertEqual(results.count("rejected"), 1)
                self.assertEqual(
                    sum(
                        result in ("booking", "block")
                        for result in results
                    ),
                    1,
                )

                appointments = connection.execute(
                    """
                    SELECT COUNT(*) FROM appointments
                    WHERE patient_name = %s;
                    """,
                    (marker,),
                ).fetchone()[0]

                blocks = connection.execute(
                    """
                    SELECT COUNT(*) FROM availability_blocks
                    WHERE reason = %s;
                    """,
                    (marker,),
                ).fetchone()[0]

                self.assertEqual(appointments + blocks, 1)
            finally:
                connection.execute(
                    """
                    DELETE FROM audit_events
                    WHERE availability_block_id IN (
                        SELECT id FROM availability_blocks
                        WHERE reason = %s
                    );
                    """,
                    (marker,),
                )
                connection.execute(
                    "DELETE FROM availability_blocks WHERE reason = %s",
                    (marker,),
                )
                connection.execute(
                    "DELETE FROM appointments WHERE patient_name = %s",
                    (marker,),
                )


    def test_audit_failure_rolls_back_block_release(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        starts_at = datetime.now(timezone.utc) + timedelta(days=60)
        reason = f"Release Rollback Test {uuid4()}"

        with psycopg.connect(test_url, autocommit=True) as connection:
            block_id = connection.execute(
                """
                INSERT INTO availability_blocks (
                    starts_at, ends_at, reason
                )
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (
                    starts_at,
                    starts_at + timedelta(hours=1),
                    reason,
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
                        release_availability_block(
                            block_id,
                            "test-issuer",
                            "test-subject",
                            None,
                        )

                released_at = connection.execute(
                    """
                    SELECT released_at FROM availability_blocks
                    WHERE id = %s;
                    """,
                    (block_id,),
                ).fetchone()[0]

                self.assertIsNone(released_at)
            finally:
                connection.execute(
                    """
                    DELETE FROM audit_events
                    WHERE availability_block_id = %s;
                    """,
                    (block_id,),
                )
                connection.execute(
                    "DELETE FROM availability_blocks WHERE id = %s",
                    (block_id,),
                )


    def test_released_block_allows_booking_and_is_recorded_once(self):
        test_url = make_conninfo(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
        )
        starts_at = datetime.now(timezone.utc) + timedelta(days=60)
        marker = f"Released Block Test {uuid4()}"
        correlation_id = uuid4()

        with psycopg.connect(test_url, autocommit=True) as connection:
            try:
                with patch.dict(
                    os.environ,
                    {"DATABASE_URL": test_url},
                ):
                    block = create_availability_block(
                        starts_at,
                        starts_at + timedelta(hours=1),
                        marker,
                        "test-issuer",
                        "test-subject",
                        uuid4(),
                    )
                    self.assertIsNotNone(block)

                    first = release_availability_block(
                        block["id"],
                        "test-issuer",
                        "test-subject",
                        correlation_id,
                    )
                    second = release_availability_block(
                        block["id"],
                        "test-issuer",
                        "test-subject",
                        uuid4(),
                    )

                    appointment = create_appointment_in_db(
                        marker,
                        "+306900000000",
                        "00000000000",
                        starts_at,
                    )

                self.assertIsNotNone(first["released_at"])
                self.assertIsNone(second)
                self.assertIsNotNone(appointment["id"])

                events = connection.execute(
                    """
                    SELECT correlation_id
                    FROM audit_events
                    WHERE availability_block_id = %s
                      AND action = 'availability_block.released';
                    """,
                    (block["id"],),
                ).fetchall()

                self.assertEqual(events, [(correlation_id,)])
            finally:
                connection.execute(
                    "DELETE FROM appointments WHERE patient_name = %s",
                    (marker,),
                )
                connection.execute(
                    """
                    DELETE FROM audit_events
                    WHERE availability_block_id IN (
                        SELECT id FROM availability_blocks
                        WHERE reason = %s
                    );
                    """,
                    (marker,),
                )
                connection.execute(
                    "DELETE FROM availability_blocks WHERE reason = %s",
                    (marker,),
                )