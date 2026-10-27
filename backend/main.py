from fastapi import FastAPI, Depends
from datetime import date, datetime, timedelta
from pydantic import BaseModel
from fastapi import HTTPException
from database import get_appointments_from_db,create_appointment_in_db
from zoneinfo import ZoneInfo
from psycopg.errors import UniqueViolation, CheckViolation
from fastapi import Response
from database import cancel_appointment_in_db
from database import get_booked_times_for_date
from pydantic import StrictBool
from database import update_appointment_no_show
from login_session import LoginSessionMiddleware
from auth import router as auth_router
from auth import require_staff
from auth import require_staff_change
from typing import Annotated
from pydantic import StringConstraints
import re
from pydantic import field_validator
from pydantic import ConfigDict
from fastapi import Request
from rate_limits import require_booking_limit
from body_limit import RequestBodyLimitMiddleware
from uuid import uuid4
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from security_headers import SecurityHeadersMiddleware
from database import get_active_blocks_for_date
from availability_blocks import router as availability_blocks_router
from medical_assistant import router as medical_assistant_router
from availability_service import get_available_slots
from staff_assistant import router as staff_assistant_router
from fastapi import Query
from database import (
    get_appointments_page_from_db,
    get_appointment_details_from_db,
)
from database import reschedule_appointment_in_db
from database import get_appointment_counts_for_month
from fastapi import Path
from database import get_appointment_history_from_db

app = FastAPI()
app.add_middleware(LoginSessionMiddleware)
app.add_middleware(RequestBodyLimitMiddleware, max_bytes=16 * 1024)
app.add_middleware(SecurityHeadersMiddleware)
app.include_router(auth_router)
app.include_router(availability_blocks_router)
app.include_router(medical_assistant_router)
app.include_router(staff_assistant_router)

@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request,
    exc: RequestValidationError,
):
    errors = [
        {
            "type": error["type"],
            "loc": error["loc"],
            "msg": error["msg"],
        }
        for error in exc.errors()
    ]

    return JSONResponse(
        status_code=422,
        content={"detail": errors},
        headers={"Cache-Control": "no-store"},
    )

class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_name: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=100,
        ),
    ]
    patient_phone: str
    starts_at: datetime
    patient_AMKA: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=11,
            max_length=11,
            pattern=r"^[0-9]{11}$",
        ),
    ]
    @field_validator("patient_phone")
    @classmethod
    def validate_patient_phone(cls, value):
        if len(value) > 30:
            raise ValueError("Το τηλέφωνο είναι υπερβολικά μεγάλο.")

        normalized = re.sub(r"[ -]", "", value)

        if normalized.startswith("+30"):
            normalized = normalized[3:]

        if not re.fullmatch(r"(?:69[0-9]{8}|2[0-9]{9})", normalized):
            raise ValueError(
                "Δώσε ελληνικό κινητό ή σταθερό 10 ψηφίων, "
                "με προαιρετικό πρόθεμα +30."
            )

        return "+30" + normalized

class AppointmentAttendanceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    no_show: StrictBool

class AppointmentReschedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: datetime
    expected_starts_at: datetime

    @field_validator("starts_at", "expected_starts_at")
    @classmethod
    def require_timezone(cls, value):
        if value.utcoffset() is None:
            raise ValueError(
                "Η ημερομηνία πρέπει να περιλαμβάνει ζώνη ώρας."
            )
        return value

class AppointmentCreated(BaseModel):
    id: int
    starts_at: datetime


@app.get(
    "/appointments/page",
    dependencies=[Depends(require_staff)],
)
def get_appointments_page(
    response: Response,
    appointment_date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    patient_AMKA: Annotated[
        str,
        StringConstraints(pattern=r"^[0-9]{11}$"),
    ] | None = None,
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=25, ge=1, le=100),
):
    response.headers["Cache-Control"] = "no-store"

    using_range = date_from is not None or date_to is not None

    if using_range:
        if (
            appointment_date is not None
            or date_from is None
            or date_to is None
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Συμπλήρωσε και τις δύο ημερομηνίες "
                    "χωρίς το φίλτρο μίας ημέρας."
                ),
                headers={"Cache-Control": "no-store"},
            )

        if date_to < date_from:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Η ημερομηνία λήξης δεν μπορεί "
                    "να προηγείται της έναρξης."
                ),
                headers={"Cache-Control": "no-store"},
            )

        if (date_to - date_from).days > 30:
            raise HTTPException(
                status_code=422,
                detail="Επίλεξε διάστημα έως 31 ημερών.",
                headers={"Cache-Control": "no-store"},
            )

        if date_to == date.max:
            raise HTTPException(
                status_code=422,
                detail="Η ημερομηνία είναι εκτός υποστηριζόμενου εύρους.",
                headers={"Cache-Control": "no-store"},
            )

        return get_appointments_page_from_db(
            appointment_date=None,
            date_from=date_from,
            date_to=date_to,
            patient_amka=patient_AMKA,
            page=page,
            page_size=page_size,
        )

    # Preserve the existing single-day API.
    selected_date = (
        appointment_date
        if appointment_date is not None
        else datetime.now(ZoneInfo("Europe/Athens")).date()
    )

    if selected_date == date.max:
        raise HTTPException(
            status_code=422,
            detail="Η ημερομηνία είναι εκτός υποστηριζόμενου εύρους.",
            headers={"Cache-Control": "no-store"},
        )

    return get_appointments_page_from_db(
        appointment_date=selected_date,
        patient_amka=patient_AMKA,
        page=page,
        page_size=page_size,
    )

@app.get(
    "/appointments",
    dependencies=[Depends(require_staff)],
)
def get_appointments(
    response: Response,
    appointment_date: date | None = None,
    patient_AMKA: Annotated[
        str,
        StringConstraints(pattern=r"^[0-9]{11}$"),
    ] | None = None,
):
    response.headers["Cache-Control"] = "no-store"
    selected_date = (
        appointment_date
        if appointment_date is not None
        else datetime.now(ZoneInfo("Europe/Athens")).date()
    )
    return get_appointments_from_db(
        appointment_date=selected_date,
        patient_amka=patient_AMKA,
    )

@app.get("/")
def read_root():
    return {"message": "Το API ανανεώνεται αυτόματα"}

@app.get(
    "/appointments/calendar",
    dependencies=[Depends(require_staff)],
)
def get_appointments_calendar(
    response: Response,
    year: int = Query(ge=1, le=9998),
    month: int = Query(ge=1, le=12),
):
    response.headers["Cache-Control"] = "no-store"

    return {
        "days": get_appointment_counts_for_month(
            year=year,
            month=month,
        )
    }


@app.get(
    "/appointments/{appointment_id}",
    dependencies=[Depends(require_staff)],
)
def get_appointment_details(
    response: Response,
    appointment_id: int,
):
    if appointment_id < 1:
        raise HTTPException(
            status_code=422,
            detail="Μη έγκυρος αριθμός ραντεβού.",
        )

    appointment = get_appointment_details_from_db(
        appointment_id
    )

    if appointment is None:
        raise HTTPException(
            status_code=404,
            detail="Το ραντεβού δεν βρέθηκε.",
            headers={"Cache-Control": "no-store"},
        )

    response.headers["Cache-Control"] = "no-store"
    return appointment

@app.post(
    "/appointments",
    status_code=201,
    response_model=AppointmentCreated,
    dependencies=[Depends(require_booking_limit)],
)
def create_appointment(
    appointment: AppointmentCreate,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    if appointment.starts_at.utcoffset() is None:
        raise HTTPException(
            status_code=400,
            detail="Η ημερομηνία πρέπει να περιλαμβάνει ζώνη ώρας."
        )

    local_start = appointment.starts_at.astimezone(ZoneInfo("Europe/Athens"))

    if not 9 <= local_start.hour < 17:
        raise HTTPException(
            status_code=400,
            detail="Το ωράριο ραντεβού είναι 09:00–17:00."
        )

    if (
        local_start.minute not in (0, 30)
        or local_start.second != 0
        or local_start.microsecond != 0
    ):
        raise HTTPException(
            status_code=400,
            detail="Οι ώρες έναρξης πρέπει να είναι ανά 30 λεπτά."
        )
    if local_start <= datetime.now(ZoneInfo("Europe/Athens")):
        raise HTTPException(
            status_code=400,
            detail="Το ραντεβού πρέπει να είναι σε μελλοντική ημερομηνία και ώρα."
        )

    if local_start.weekday() >= 5:
        raise HTTPException(
            status_code=400,
            detail="Δεν επιτρέπονται ραντεβού το Σαββατοκύριακο."
        )
    try:
        return create_appointment_in_db(
            appointment.patient_name,
            appointment.patient_phone,
            appointment.patient_AMKA,
            appointment.starts_at,
        )
    except UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="Η συγκεκριμένη ώρα έχει ήδη κρατηθεί."
        ) from None

    except CheckViolation:
        raise HTTPException(
            status_code=409,
            detail="Το επιλεγμένο διάστημα δεν είναι διαθέσιμο.",
        ) from None

@app.post("/appointments/{appointment_id}/reschedule")
def reschedule_appointment(
    appointment_id: int,
    change: AppointmentReschedule,
    session: dict = Depends(require_staff_change),
):
    if appointment_id < 1:
        raise HTTPException(
            status_code=422,
            detail="Μη έγκυρος αριθμός ραντεβού.",
            headers={"Cache-Control": "no-store"},
        )

    try:
        updated = reschedule_appointment_in_db(
            appointment_id,
            change.starts_at,
            session["issuer"],
            session["subject"],
            uuid4(),
            expected_starts_at=change.expected_starts_at,
        )
    except (UniqueViolation, CheckViolation):
        raise HTTPException(
            status_code=409,
            detail=(
                "Η επιλεγμένη ώρα δεν είναι διαθέσιμη. "
                "Ανανέωσε τη διαθεσιμότητα και επίλεξε άλλη ώρα."
            ),
            headers={"Cache-Control": "no-store"},
        ) from None
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
            headers={"Cache-Control": "no-store"},
        ) from None

    if updated is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Το ραντεβού έχει αλλάξει ή δεν είναι πλέον "
                "ενεργό μελλοντικό ραντεβού. "
                "Ανανέωσε τη λίστα πριν συνεχίσεις."
            ),
            headers={"Cache-Control": "no-store"},
        )

    return JSONResponse(
        content={
            "id": updated["id"],
            "starts_at": updated["starts_at"].isoformat(),
        },
        headers={"Cache-Control": "no-store"},
    )

@app.post("/appointments/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: int,
    session: dict = Depends(require_staff_change),
):
    cancelled = cancel_appointment_in_db(
        appointment_id,
        session["issuer"],
        session["subject"],
        uuid4(),
    )

    if cancelled is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Δεν βρέθηκε ενεργό μελλοντικό ραντεβού "
                "για ακύρωση."
            ),
        )

    return JSONResponse(
        content={
            "id": cancelled["id"],
            "cancelled_at": cancelled["cancelled_at"].isoformat(),
        },
        headers={"Cache-Control": "no-store"},
    )


@app.get("/availability")
def get_availability(date: date):
    return get_available_slots(
        date,
        booked_reader=get_booked_times_for_date,
        blocks_reader=get_active_blocks_for_date,
    )

@app.patch("/appointments/{appointment_id}/attendance")
def update_appointment_attendance(
    appointment_id: int,
    attendance: AppointmentAttendanceUpdate,
    session: dict = Depends(require_staff_change),
):
    updated = update_appointment_no_show(
        appointment_id,
        attendance.no_show,
        session["issuer"],
        session["subject"],
        uuid4(),
    )

    if updated is None:
        raise HTTPException(
            status_code=404,
            detail="Το ραντεβού δεν βρέθηκε ή δεν έχει λήξει ακόμη.",
        )

    return updated


@app.get(
    "/appointments/{appointment_id}/history",
    dependencies=[Depends(require_staff)],
)
def get_appointment_history(
    response: Response,
    appointment_id: Annotated[int, Path(ge=1)],
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=25, ge=1, le=100),
):
    response.headers["Cache-Control"] = "no-store"

    history = get_appointment_history_from_db(
        appointment_id,
        page=page,
        page_size=page_size,
    )

    if history is None:
        raise HTTPException(
            status_code=404,
            detail="Το ραντεβού δεν βρέθηκε.",
            headers={"Cache-Control": "no-store"},
        )

    return history
