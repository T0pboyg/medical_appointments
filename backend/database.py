import os
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


def check_connection():
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            return cursor.fetchone()[0]

def create_appointment_in_db(
    patient_name, patient_phone, patient_amka, starts_at,
    *, actor_issuer=None, actor_subject=None, correlation_id=None,
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

            created = cursor.fetchone()
            if actor_issuer is not None:
                if not actor_subject or correlation_id is None:
                    raise ValueError("Staff audit identity is incomplete.")
                cursor.execute(
                    """
                    INSERT INTO audit_events (
                        actor_issuer, actor_subject, action,
                        appointment_id, correlation_id
                    ) VALUES (%s, %s, 'appointment.created', %s, %s);
                    """,
                    (actor_issuer, actor_subject, created["id"], correlation_id),
                )
            return created

def get_appointments_from_db(
    appointment_date=None,
    patient_amka=None,
):
    database_url = os.environ["DATABASE_URL"]
    conditions = []
    parameters = []

    if appointment_date is not None:
        clinic_timezone = ZoneInfo("Europe/Athens")

        start = datetime.combine(
            appointment_date,
            time.min,
            tzinfo=clinic_timezone,
        )
        end = datetime.combine(
            appointment_date + timedelta(days=1),
            time.min,
            tzinfo=clinic_timezone,
        )

        conditions.extend([
            "starts_at >= %s",
            "starts_at < %s",
        ])
        parameters.extend([start, end])

    if patient_amka is not None:
        conditions.append("patient_amka = %s")
        parameters.append(patient_amka)

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions
        else ""
    )

    with psycopg.connect(
        database_url,
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, patient_name, patient_phone, starts_at,
                       patient_amka AS "patient_AMKA", no_show,
                       cancelled_at
                FROM appointments
                {where_clause}
                ORDER BY starts_at, id;
                """,
                parameters,
            )
            return cursor.fetchall()


def get_appointments_page_from_db(
    *,
    appointment_date=None,
    date_from=None,
    date_to=None,
    patient_amka=None,
    page=1,
    page_size=25,
):
    using_range = date_from is not None or date_to is not None

    if using_range:
        if (
            appointment_date is not None
            or date_from is None
            or date_to is None
        ):
            raise ValueError(
                "Provide both range endpoints without appointment_date."
            )

        first_day = date_from
        last_day = date_to
    else:
        if appointment_date is None:
            raise ValueError("An appointment date is required.")

        first_day = appointment_date
        last_day = appointment_date

    if last_day < first_day:
        raise ValueError("The range end precedes its start.")

    if (last_day - first_day).days > 30:
        raise ValueError("The range cannot exceed 31 calendar days.")

    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("Invalid pagination.")

    try:
        following_day = last_day + timedelta(days=1)
    except OverflowError:
        raise ValueError("Unsupported end date.") from None

    clinic_timezone = ZoneInfo("Europe/Athens")

    start = datetime.combine(
        first_day,
        time.min,
        tzinfo=clinic_timezone,
    )
    end = datetime.combine(
        following_day,
        time.min,
        tzinfo=clinic_timezone,
    )

    offset = (page - 1) * page_size

    with psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, patient_name, starts_at,
                       no_show, cancelled_at
                FROM appointments
                WHERE starts_at >= %s
                  AND starts_at < %s
                  AND (
                      %s::text IS NULL
                      OR patient_amka = %s
                  )
                ORDER BY starts_at, id
                LIMIT %s OFFSET %s;
                """,
                (
                    start,
                    end,
                    patient_amka,
                    patient_amka,
                    page_size + 1,
                    offset,
                ),
            )
            rows = cursor.fetchall()

    return {
        "items": rows[:page_size],
        "page": page,
        "page_size": page_size,
        "has_more": len(rows) > page_size,
    }

def get_appointment_details_from_db(appointment_id):
    with psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, patient_name, patient_phone,
                       patient_amka AS "patient_AMKA",
                       starts_at, no_show, cancelled_at
                FROM appointments
                WHERE id = %s;
                """,
                (appointment_id,),
            )
            return cursor.fetchone()

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


def reschedule_appointment_in_db(
    appointment_id,
    new_starts_at,
    actor_issuer,
    actor_subject,
    correlation_id,
    *,
    expected_starts_at,
):
    clinic_timezone = ZoneInfo("Europe/Athens")

    if (
        new_starts_at.utcoffset() is None
        or expected_starts_at.utcoffset() is None
    ):
        raise ValueError("Οι ημερομηνίες χρειάζονται ζώνη ώρας.")

    local_start = new_starts_at.astimezone(clinic_timezone)

    if (
        local_start.weekday() >= 5
        or not 9 <= local_start.hour < 17
        or local_start.minute not in (0, 30)
        or local_start.second != 0
        or local_start.microsecond != 0
    ):
        raise ValueError("Η νέα ώρα είναι εκτός διαθέσιμου ωραρίου.")

    if new_starts_at == expected_starts_at:
        raise ValueError("Επίλεξε διαφορετική ώρα.")

    with psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            # Same lock as booking and availability-block creation.
            cursor.execute(
                "SELECT pg_advisory_xact_lock(742019002);"
            )

            cursor.execute(
                """
                SELECT id
                FROM appointments
                WHERE id = %s
                  AND cancelled_at IS NULL
                  AND starts_at > clock_timestamp()
                  AND starts_at = %s
                FOR UPDATE;
                """,
                (appointment_id, expected_starts_at),
            )

            if cursor.fetchone() is None:
                return None

            # Check after acquiring locks, in case we waited.
            if local_start <= datetime.now(clinic_timezone):
                raise ValueError("Η νέα ώρα πρέπει να είναι μελλοντική.")

            cursor.execute(
                """
                SELECT id
                FROM availability_blocks
                WHERE released_at IS NULL
                  AND starts_at < %s + INTERVAL '30 minutes'
                  AND ends_at > %s
                LIMIT 1;
                """,
                (new_starts_at, new_starts_at),
            )

            if cursor.fetchone() is not None:
                raise psycopg.errors.CheckViolation(
                    "Rescheduling overlaps an availability block."
                )

            # The active-slot unique index rejects an occupied time.
            cursor.execute(
                """
                UPDATE appointments
                SET starts_at = %s
                WHERE id = %s
                RETURNING id, starts_at;
                """,
                (new_starts_at, appointment_id),
            )
            updated = cursor.fetchone()

            cursor.execute(
                """
                INSERT INTO audit_events (
                    actor_issuer,
                    actor_subject,
                    action,
                    appointment_id,
                    correlation_id,
                    previous_starts_at,
                    new_starts_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    actor_issuer,
                    actor_subject,
                    "appointment.rescheduled",
                    appointment_id,
                    correlation_id,
                    expected_starts_at,
                    updated["starts_at"],
                ),
            )

    return updated


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

def get_appointment_counts_for_month(*, year, month):
    if not 1 <= year <= 9998 or not 1 <= month <= 12:
        raise ValueError("Invalid calendar month.")

    clinic_timezone = ZoneInfo("Europe/Athens")
    start = datetime(
        year, month, 1,
        tzinfo=clinic_timezone,
    )

    if month == 12:
        end = datetime(
            year + 1, 1, 1,
            tzinfo=clinic_timezone,
        )
    else:
        end = datetime(
            year, month + 1, 1,
            tzinfo=clinic_timezone,
        )

    with psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    (starts_at AT TIME ZONE 'Europe/Athens')::date
                        AS appointment_day,
                    COUNT(*) AS appointment_count
                FROM appointments
                WHERE starts_at >= %s
                  AND starts_at < %s
                  AND cancelled_at IS NULL
                GROUP BY
                    (starts_at AT TIME ZONE 'Europe/Athens')::date
                ORDER BY appointment_day;
                """,
                (start, end),
            )

            return [
                {
                    "date": row["appointment_day"].isoformat(),
                    "count": row["appointment_count"],
                }
                for row in cursor.fetchall()
            ]

def get_appointment_history_from_db(
    appointment_id,
    *,
    page=1,
    page_size=25,
):
    if appointment_id < 1:
        raise ValueError("Invalid appointment ID.")

    if not 1 <= page <= 10000 or not 1 <= page_size <= 100:
        raise ValueError("Invalid pagination.")

    offset = (page - 1) * page_size

    with psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM appointments
                WHERE id = %s;
                """,
                (appointment_id,),
            )

            if cursor.fetchone() is None:
                return None

            cursor.execute(
                """
                SELECT
                    id,
                    occurred_at,
                    actor_issuer,
                    actor_subject,
                    action,
                    previous_starts_at,
                    new_starts_at
                FROM audit_events
                WHERE appointment_id = %s
                ORDER BY occurred_at DESC, id DESC
                LIMIT %s OFFSET %s;
                """,
                (
                    appointment_id,
                    page_size + 1,
                    offset,
                ),
            )
            rows = cursor.fetchall()

    return {
        "events": rows[:page_size],
        "page": page,
        "page_size": page_size,
        "has_more": len(rows) > page_size,
    }


def get_appointment_summary_for_date(appointment_date, *, now):
    clinic_timezone = ZoneInfo("Europe/Athens")

    start = datetime.combine(
        appointment_date,
        time.min,
        tzinfo=clinic_timezone,
    )
    end = datetime.combine(
        appointment_date + timedelta(days=1),
        time.min,
        tzinfo=clinic_timezone,
    )

    with psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS appointments_count,
                    COUNT(*) FILTER (
                        WHERE no_show = TRUE
                    ) AS no_show_count,
                    MIN(starts_at) FILTER (
                        WHERE starts_at > %s
                          AND no_show = FALSE
                    ) AS next_starts_at
                FROM appointments
                WHERE starts_at >= %s
                  AND starts_at < %s
                  AND cancelled_at IS NULL;
                """,
                (now, start, end),
            )
            return cursor.fetchone()