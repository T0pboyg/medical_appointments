import os
import psycopg
from psycopg.rows import dict_row


def check_connection():
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            return cursor.fetchone()[0]

def get_appointments_from_db():
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, patient_name, patient_phone, starts_at
                FROM appointments
                ORDER BY id;
                """
            )
            return cursor.fetchall()