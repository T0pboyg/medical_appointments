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

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO appointments (
                    patient_name, patient_phone, patient_amka, starts_at
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id, patient_name, patient_phone,
                          patient_amka AS "patient_AMKA", starts_at;
                """,
                (patient_name, patient_phone, patient_amka, starts_at),
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
                RETURNING id, cancelled_at;
                """,
                (appointment_id,),
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