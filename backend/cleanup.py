import os

import psycopg


def cleanup_expired_data():
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM booking_rate_limits
                WHERE window_start <
                    CURRENT_TIMESTAMP - INTERVAL '1 day';
                """
            )
            deleted_limits = cursor.rowcount

            cursor.execute(
                """
                DELETE FROM staff_sessions
                WHERE expires_at <= CURRENT_TIMESTAMP
                   OR (
                       data->>'purpose' = 'staff'
                       AND last_seen_at <=
                           CURRENT_TIMESTAMP - INTERVAL '15 minutes'
                   );
                """
            )
            deleted_sessions = cursor.rowcount

    return {
        "deleted_rate_limits": deleted_limits,
        "deleted_sessions": deleted_sessions,
    }


if __name__ == "__main__":
    print(cleanup_expired_data())