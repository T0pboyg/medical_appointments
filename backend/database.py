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
                       patient_amka AS "patient_AMKA"
                FROM appointments
                ORDER BY id;
                """
            )
            return cursor.fetchall()