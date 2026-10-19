import os
import unittest
from unittest.mock import patch

import psycopg

from migrate import apply_migrations, load_migrations


class MigrationTests(unittest.TestCase):
    def test_failed_migration_rolls_back(self):
        migrations = load_migrations()

        failing_migration = {
            "version": "002_rollback_test.sql",
            "checksum": "0" * 64,
            "sql": """
                CREATE TABLE public.migration_rollback_probe (
                    id INTEGER
                );
                SELECT 1 / 0;
            """,
        }

        with psycopg.connect(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
            autocommit=True,
        ) as connection:
            database = connection.execute(
                "SELECT current_database()"
            ).fetchone()[0]

            self.assertEqual(database, "appointments_migration_test")

            with patch(
                "migrate.load_migrations",
                return_value=migrations + [failing_migration],
            ):
                with self.assertRaises(psycopg.errors.DivisionByZero):
                    apply_migrations(connection)

            table = connection.execute(
                "SELECT to_regclass('public.migration_rollback_probe')"
            ).fetchone()[0]

            recorded = connection.execute(
                """
                SELECT COUNT(*)
                FROM public.schema_migrations
                WHERE version = %s;
                """,
                (failing_migration["version"],),
            ).fetchone()[0]

            self.assertIsNone(table)
            self.assertEqual(recorded, 0)
    def test_modified_migration_is_rejected(self):
        migrations = load_migrations()
        modified = [
            {**migration, "checksum": "0" * 64}
            for migration in migrations
        ]

        with psycopg.connect(
            os.environ["DATABASE_URL"],
            dbname="appointments_migration_test",
            autocommit=True,
        ) as connection:
            before = connection.execute(
                """
                SELECT version, checksum
                FROM public.schema_migrations
                ORDER BY version;
                """
            ).fetchall()

            with patch("migrate.load_migrations", return_value=modified):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "Το ιστορικό migrations δεν συμφωνεί",
                ):
                    apply_migrations(connection)

            after = connection.execute(
                """
                SELECT version, checksum
                FROM public.schema_migrations
                ORDER BY version;
                """
            ).fetchall()

            self.assertEqual(before, after)