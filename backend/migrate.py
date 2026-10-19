import hashlib
import re
from pathlib import Path
import os

import psycopg

def ensure_migration_history(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS public.schema_migrations (
            version TEXT PRIMARY KEY,
            checksum TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            CHECK (checksum ~ '^[0-9a-f]{64}$')
        );
        """
    )

def load_migrations():
    directory = Path(__file__).resolve().parent / "migrations"

    if not directory.is_dir():
        raise RuntimeError("Δεν βρέθηκε ο φάκελος migrations.")

    migrations = []
    versions = set()

    for path in sorted(directory.glob("*.sql")):
        match = re.fullmatch(r"([0-9]{3})_[a-z0-9_]+\.sql", path.name)

        if match is None:
            raise RuntimeError(f"Μη έγκυρο όνομα migration: {path.name}")

        version = match.group(1)

        if version in versions:
            raise RuntimeError(f"Διπλός αριθμός migration: {version}")

        versions.add(version)
        content = path.read_bytes()

        migrations.append({
            "version": path.name,
            "checksum": hashlib.sha256(content).hexdigest(),
            "sql": content.decode("utf-8-sig"),
        })

    if not migrations:
        raise RuntimeError("Δεν βρέθηκαν SQL migrations.")

    return migrations

def check_existing_schema(connection):
    history_exists = connection.execute(
        "SELECT to_regclass('public.schema_migrations')"
    ).fetchone()[0]

    if history_exists is not None:
        recorded = connection.execute(
            "SELECT EXISTS (SELECT 1 FROM public.schema_migrations)"
        ).fetchone()[0]

        if recorded:
            return

    existing_tables = connection.execute(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename <> 'schema_migrations'
        ORDER BY tablename;
        """
    ).fetchall()

    if existing_tables:
        raise RuntimeError(
            "Υπάρχουν πίνακες χωρίς καταγεγραμμένο ιστορικό migrations. "
            "Απαιτείται έλεγχος και αρχική καταχώριση της υπάρχουσας δομής."
        )

def apply_migrations(connection):
    migrations = load_migrations()
    applied_now = []

    with connection.transaction():
        connection.execute(
            "SELECT pg_advisory_xact_lock(742019001)"
        )

        check_existing_schema(connection)
        ensure_migration_history(connection)

        history = connection.execute(
            """
            SELECT version, checksum
            FROM public.schema_migrations
            ORDER BY version;
            """
        ).fetchall()

        expected_history = [
            (item["version"], item["checksum"])
            for item in migrations[:len(history)]
        ]

        if history != expected_history:
            raise RuntimeError(
                "Το ιστορικό migrations δεν συμφωνεί με τα αρχεία. "
                "Ελέγξτε για τροποποιημένα ή απόντα αρχεία."
            )

        for migration in migrations[len(history):]:
            connection.execute(migration["sql"])

            connection.execute(
                """
                INSERT INTO public.schema_migrations (
                    version, checksum
                )
                VALUES (%s, %s);
                """,
                (migration["version"], migration["checksum"]),
            )

            applied_now.append(migration["version"])

    return applied_now

def get_schema_columns(connection):
    return connection.execute(
        """
        SELECT
            c.relname,
            a.attnum,
            a.attname,
            pg_catalog.format_type(a.atttypid, a.atttypmod),
            a.attnotnull,
            a.attidentity,
            pg_get_expr(d.adbin, d.adrelid)
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        JOIN pg_attribute AS a ON a.attrelid = c.oid
        LEFT JOIN pg_attrdef AS d
            ON d.adrelid = c.oid AND d.adnum = a.attnum
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p')
          AND c.relname <> 'schema_migrations'
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY c.relname, a.attnum;
        """
    ).fetchall()

def get_schema_rules(connection):
    constraints = connection.execute(
        """
        SELECT c.relname, con.conname,
               pg_get_constraintdef(con.oid, false)
        FROM pg_constraint AS con
        JOIN pg_class AS c ON c.oid = con.conrelid
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname <> 'schema_migrations'
        ORDER BY c.relname, con.conname;
        """
    ).fetchall()

    indexes = connection.execute(
        """
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename <> 'schema_migrations'
        ORDER BY tablename, indexname;
        """
    ).fetchall()

    return {
        "constraints": constraints,
        "indexes": indexes,
    }

def record_initial_schema(connection, reference):
    migrations = load_migrations()

    if len(migrations) != 1:
        raise RuntimeError(
            "Η αρχική καταχώριση απαιτεί ακριβώς μία migration."
        )

    initial = migrations[0]

    reference_history = reference.execute(
        """
        SELECT version, checksum
        FROM public.schema_migrations
        ORDER BY version;
        """
    ).fetchall()

    if reference_history != [
        (initial["version"], initial["checksum"])
    ]:
        raise RuntimeError("Μη έγκυρο ιστορικό βάσης αναφοράς.")

    current_database = connection.execute(
        "SELECT current_database()"
    ).fetchone()[0]

    reference_database = reference.execute(
        "SELECT current_database()"
    ).fetchone()[0]

    if current_database == reference_database:
        raise RuntimeError("Οι δύο βάσεις πρέπει να είναι διαφορετικές.")

    with connection.transaction():
        connection.execute(
            "SELECT pg_advisory_xact_lock(742019001)"
        )

        ensure_migration_history(connection)

        if connection.execute(
            "SELECT EXISTS (SELECT 1 FROM public.schema_migrations)"
        ).fetchone()[0]:
            raise RuntimeError("Υπάρχει ήδη ιστορικό migrations.")

        if (
            get_schema_columns(connection) != get_schema_columns(reference)
            or get_schema_rules(connection) != get_schema_rules(reference)
        ):
            raise RuntimeError("Η υπάρχουσα δομή δεν συμφωνεί.")

        connection.execute(
            """
            INSERT INTO public.schema_migrations (version, checksum)
            VALUES (%s, %s);
            """,
            (initial["version"], initial["checksum"]),
        )

    return initial["version"]

if __name__ == "__main__":
    with psycopg.connect(
        os.environ["DATABASE_URL"],
        autocommit=True,
    ) as connection:
        applied = apply_migrations(connection)

    print("Applied:", applied)