import hashlib
import os
import secrets
import psycopg
from psycopg.types.json import Jsonb
from psycopg.rows import dict_row


def create_session(data):
    session_id = secrets.token_urlsafe(32)
    session_hash = hashlib.sha256(session_id.encode("utf-8")).hexdigest()

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO staff_sessions (session_hash, data, expires_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '10 minutes');
                """,
                (session_hash, Jsonb(data)),
            )

    return session_id

def get_session(session_id):
    if not session_id:
        return None

    session_hash = hashlib.sha256(
        session_id.encode("utf-8")
    ).hexdigest()

    with psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT data
                FROM staff_sessions
                WHERE session_hash = %s
                  AND expires_at > CURRENT_TIMESTAMP;
                """,
                (session_hash,),
            )
            row = cursor.fetchone()

    return row["data"] if row else None

def delete_session(session_id):
    if not session_id:
        return

    session_hash = hashlib.sha256(
        session_id.encode("utf-8")
    ).hexdigest()

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM staff_sessions
                WHERE session_hash = %s;
                """,
                (session_hash,),
            )


def update_session(session_id, data):
    if not session_id:
        return False

    session_hash = hashlib.sha256(
        session_id.encode("utf-8")
    ).hexdigest()

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE staff_sessions
                SET data = %s
                WHERE session_hash = %s
                  AND expires_at > CURRENT_TIMESTAMP
                RETURNING session_hash;
                """,
                (Jsonb(data), session_hash),
            )
            return cursor.fetchone() is not None

def create_staff_session(issuer, subject):
    session_id = secrets.token_urlsafe(32)
    session_hash = hashlib.sha256(
        session_id.encode("utf-8")
    ).hexdigest()

    data = {
        "purpose": "staff",
        "issuer": issuer,
        "subject": subject,
        "csrf_token": secrets.token_urlsafe(32),
    }

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO staff_sessions (
                    session_hash, data, expires_at
                )
                VALUES (
                    %s, %s,
                    CURRENT_TIMESTAMP + INTERVAL '8 hours'
                );
                """,
                (session_hash, Jsonb(data)),
            )

    return session_id


def get_staff_session(session_id):
    if not session_id:
        return None

    session_hash = hashlib.sha256(
        session_id.encode("utf-8")
    ).hexdigest()

    with psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE staff_sessions
                SET last_seen_at = CURRENT_TIMESTAMP
                WHERE session_hash = %s
                  AND data->>'purpose' = 'staff'
                  AND expires_at > CURRENT_TIMESTAMP
                  AND last_seen_at >
                      CURRENT_TIMESTAMP - INTERVAL '15 minutes'
                RETURNING data;
                """,
                (session_hash,),
            )
            row = cursor.fetchone()

    return row["data"] if row else None