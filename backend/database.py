import os
import psycopg
from psycopg.rows import dict_row


def check_connection():
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            return cursor.fetchone()[0]

def create_appointment_in_db(
    patient_name, patient_phone, patient_amka, starts_at
):
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(
        database_url,
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(742019002);"
            )

            cursor.execute(
                """
                SELECT id
                FROM availability_blocks
                WHERE released_at IS NULL
                  AND starts_at < %s + INTERVAL '30 minutes'
                  AND ends_at > %s
                LIMIT 1;
                """,
                (starts_at, starts_at),
            )

            if cursor.fetchone() is not None:
                raise psycopg.errors.CheckViolation(
                    "Booking overlaps an availability block."
                )

            cursor.execute(
                """
                INSERT INTO appointments (
                    patient_name, patient_phone,
                    patient_amka, starts_at
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id, patient_name, patient_phone,
                          patient_amka AS "patient_AMKA",
                          starts_at;
                """,
                (
                    patient_name,
                    patient_phone,
                    patient_amka,
                    starts_at,
                ),
            )

            return cursor.fetchone()

def get_appointments_from_db():
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, patient_name, patient_phone, starts_at,
                       patient_amka AS "patient_AMKA", no_show,
                       cancelled_at
                FROM appointments
                ORDER BY id;
                """
            )
            return cursor.fetchall()

def delete_appointment_from_db(
    appointment_id,
    actor_issuer,
    actor_subject,
    correlation_id,
):
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM appointments
                WHERE id = %s
                RETURNING id;
                """,
                (appointment_id,),
            )

            deleted = cursor.fetchone()

            if deleted is None:
                return False

            cursor.execute(
                """
                INSERT INTO audit_events (
                    actor_issuer,
                    actor_subject,
                    action,
                    appointment_id,
                    correlation_id
                )
                VALUES (%s, %s, %s, %s, %s);
                """,
                (
                    actor_issuer,
                    actor_subject,
                    "appointment.deleted",
                    appointment_id,
                    correlation_id,
                ),
            )

    return True

def get_booked_times_for_date(appointment_date):
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT starts_at AT TIME ZONE 'Europe/Athens'
                FROM appointments
                WHERE (starts_at AT TIME ZONE 'Europe/Athens')::date = %s
                  AND cancelled_at IS NULL
                ORDER BY starts_at;
                """,
                (appointment_date,),
            )
            return [row[0].strftime("%H:%M") for row in cursor.fetchall()]

def update_appointment_no_show(
    appointment_id,
    no_show,
    actor_issuer,
    actor_subject,
    correlation_id,
):
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE appointments
                SET no_show = %s
                WHERE id = %s
                  AND cancelled_at IS NULL
                  AND starts_at + INTERVAL '30 minutes'
                      <= CURRENT_TIMESTAMP
                RETURNING id, no_show;
                """,
                (no_show, appointment_id),
            )

            updated = cursor.fetchone()

            if updated is None:
                return None

            action = (
                "appointment.marked_no_show"
                if no_show
                else "appointment.marked_completed"
            )

            cursor.execute(
                """
                INSERT INTO audit_events (
                    actor_issuer,
                    actor_subject,
                    action,
                    appointment_id,
                    correlation_id
                )
                VALUES (%s, %s, %s, %s, %s);
                """,
                (
                    actor_issuer,
                    actor_subject,
                    action,
                    appointment_id,
                    correlation_id,
                ),
            )

            return updated


def cancel_appointment_in_db(
    appointment_id,
    actor_issuer,
    actor_subject,
    correlation_id,
    *,
    expected_starts_at=None,
    expected_patient_name=None,
):
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(
        database_url,
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE appointments
                SET cancelled_at = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND cancelled_at IS NULL
                  AND starts_at > CURRENT_TIMESTAMP
                  AND (%s::timestamptz IS NULL OR starts_at = %s)
                  AND (%s::text IS NULL OR patient_name = %s)
                RETURNING id, cancelled_at;
                """,
                (appointment_id, expected_starts_at, expected_starts_at,
                 expected_patient_name, expected_patient_name),
            )

            cancelled = cursor.fetchone()

            if cancelled is None:
                return None

            cursor.execute(
                """
                INSERT INTO audit_events (
                    actor_issuer,
                    actor_subject,
                    action,
                    appointment_id,
                    correlation_id
                )
                VALUES (%s, %s, %s, %s, %s);
                """,
                (
                    actor_issuer,
                    actor_subject,
                    "appointment.cancelled",
                    appointment_id,
                    correlation_id,
                ),
            )

    return cancelled


def find_staff_appointments(*, day=None, appointment_id=None, future_only=False):
    """Bounded staff lookup; never return phone numbers or national IDs."""
    if day is None and appointment_id is None:
        raise ValueError('A day or appointment ID is required')
    with psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row) as connection:
        rows = connection.execute(
            """
            SELECT id, patient_name, starts_at
            FROM appointments
            WHERE cancelled_at IS NULL
              AND (%s::date IS NULL OR (starts_at AT TIME ZONE 'Europe/Athens')::date = %s)
              AND (%s::integer IS NULL OR id = %s)
              AND (NOT %s OR starts_at > CURRENT_TIMESTAMP)
            ORDER BY starts_at
            LIMIT 201;
            """,
            (day, day, appointment_id, appointment_id, future_only),
        ).fetchall()
        return rows


def create_availability_block(
    starts_at,
    ends_at,
    reason,
    actor_issuer,
    actor_subject,
    correlation_id,
):
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(
        database_url,
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(742019002);"
            )

            cursor.execute(
                """
                SELECT id
                FROM appointments
                WHERE cancelled_at IS NULL
                  AND starts_at < %s
                  AND starts_at + INTERVAL '30 minutes' > %s
                LIMIT 1;
                """,
                (ends_at, starts_at),
            )

            if cursor.fetchone() is not None:
                return None

            cursor.execute(
                """
                SELECT id
                FROM availability_blocks
                WHERE released_at IS NULL
                  AND starts_at < %s
                  AND ends_at > %s
                LIMIT 1;
                """,
                (ends_at, starts_at),
            )

            if cursor.fetchone() is not None:
                return None

            cursor.execute(
                """
                INSERT INTO availability_blocks (
                    starts_at, ends_at, reason
                )
                VALUES (%s, %s, %s)
                RETURNING id, starts_at, ends_at, reason,
                          created_at, released_at;
                """,
                (starts_at, ends_at, reason),
            )
            block = cursor.fetchone()

            cursor.execute(
                """
                INSERT INTO audit_events (
                    actor_issuer,
                    actor_subject,
                    action,
                    availability_block_id,
                    correlation_id
                )
                VALUES (%s, %s, %s, %s, %s);
                """,
                (
                    actor_issuer,
                    actor_subject,
                    "availability_block.created",
                    block["id"],
                    correlation_id,
                ),
            )

    return block


def get_active_blocks_for_date(appointment_date):
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(
        database_url,
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT starts_at, ends_at
                FROM availability_blocks
                WHERE released_at IS NULL
                  AND starts_at < (
                      (%s::date + 1)::timestamp
                      AT TIME ZONE 'Europe/Athens'
                  )
                  AND ends_at > (
                      %s::date::timestamp
                      AT TIME ZONE 'Europe/Athens'
                  )
                ORDER BY starts_at;
                """,
                (appointment_date, appointment_date),
            )

            return cursor.fetchall()


def release_availability_block(
    block_id,
    actor_issuer,
    actor_subject,
    correlation_id,
):
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(
        database_url,
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(742019002);"
            )

            cursor.execute(
                """
                UPDATE availability_blocks
                SET released_at = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND released_at IS NULL
                RETURNING id, starts_at, ends_at, reason,
                          created_at, released_at;
                """,
                (block_id,),
            )

            released = cursor.fetchone()

            if released is None:
                return None

            cursor.execute(
                """
                INSERT INTO audit_events (
                    actor_issuer,
                    actor_subject,
                    action,
                    availability_block_id,
                    correlation_id
                )
                VALUES (%s, %s, %s, %s, %s);
                """,
                (
                    actor_issuer,
                    actor_subject,
                    "availability_block.released",
                    block_id,
                    correlation_id,
                ),
            )

    return released


def get_availability_blocks():
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(
        database_url,
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, starts_at, ends_at, reason,
                       created_at, released_at
                FROM availability_blocks
                WHERE released_at IS NULL
                  AND ends_at > CURRENT_TIMESTAMP
                ORDER BY starts_at, id;
                """
            )

            return cursor.fetchall()
