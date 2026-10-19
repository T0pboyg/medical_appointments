import os

import psycopg
from psycopg.rows import dict_row
from fastapi import Depends, HTTPException

from trusted_proxy import get_proxy_client_ip


def consume_booking_attempt(client_ip):
    with psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO booking_rate_limits (
                    client_ip, window_start, request_count
                )
                VALUES (
                    %s,
                    date_trunc('minute', CURRENT_TIMESTAMP),
                    1
                )
                ON CONFLICT (client_ip, window_start)
                DO UPDATE SET request_count = LEAST(
                    booking_rate_limits.request_count + 1,
                    6
                )
                RETURNING
                    request_count,
                    CEIL(EXTRACT(EPOCH FROM (
                        window_start + INTERVAL '1 minute'
                        - CURRENT_TIMESTAMP
                    )))::integer AS retry_after;
                """,
                (client_ip,),
            )

            return cursor.fetchone()

def require_booking_limit(
    client_ip: str = Depends(get_proxy_client_ip),
):
    try:
        result = consume_booking_attempt(client_ip)
    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Η υπηρεσία κράτησης δεν είναι προσωρινά διαθέσιμη.",
            headers={"Cache-Control": "no-store"},
        ) from None

    if result["request_count"] > 5:
        raise HTTPException(
            status_code=429,
            detail="Πολλές προσπάθειες κράτησης. Δοκίμασε αργότερα.",
            headers={
                "Retry-After": str(max(1, result["retry_after"])),
                "Cache-Control": "no-store",
            },
        )