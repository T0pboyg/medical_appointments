from fastapi import FastAPI
from datetime import date, datetime, time, timedelta
from pydantic import BaseModel
from fastapi import HTTPException
from database import get_appointments_from_db,create_appointment_in_db
from zoneinfo import ZoneInfo
from psycopg.errors import UniqueViolation
from fastapi import Response
from database import delete_appointment_from_db
from database import get_booked_times_for_date
from pydantic import StrictBool
from database import update_appointment_no_show
from login_session import LoginSessionMiddleware
from auth import router as auth_router

app = FastAPI()
app.add_middleware(LoginSessionMiddleware)
app.include_router(auth_router)

class AppointmentCreate(BaseModel):
    patient_name: str
    patient_phone: str
    starts_at: datetime
    patient_AMKA: str

appointments: list[dict] = []

class AppointmentAttendanceUpdate(BaseModel):
    no_show: StrictBool


@app.get("/")
def read_root():
    return {"message": "Το API ανανεώνεται αυτόματα"}


@app.get("/appointments")
def get_appointments(patient_AMKA: str | None = None):

    stored_appointments = get_appointments_from_db()
    if patient_AMKA:
        unique_appointments = [
            a for a in stored_appointments
            if a["patient_AMKA"] == patient_AMKA
            ]
        return unique_appointments
    return stored_appointments


@app.post("/appointments", status_code=201)
def create_appointment(appointment: AppointmentCreate):
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



@app.delete("/appointments/{appointment_id}", status_code=204)
def delete_appointment(appointment_id: int):
    deleted = delete_appointment_from_db(appointment_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Το ραντεβού δεν βρέθηκε."
        )

    return Response(status_code=204)

@app.get("/availability")
def get_availability(date: date):
    clinic_timezone = ZoneInfo("Europe/Athens")
    now = datetime.now(clinic_timezone)

    if date < now.date() or date.weekday() >= 5:
        return []

    booked_times = get_booked_times_for_date(date)
    opening = datetime.combine(date, time(9, 0), tzinfo=clinic_timezone)

    available_times = []

    for index in range(16):
        slot = opening + timedelta(minutes=index * 30)
        slot_label = slot.strftime("%H:%M")

        if slot > now and slot_label not in booked_times:
            available_times.append(slot_label)

    return available_times

@app.patch("/appointments/{appointment_id}/attendance")
def update_appointment_attendance(
    appointment_id: int,
    attendance: AppointmentAttendanceUpdate,
):
    updated = update_appointment_no_show(
        appointment_id,
        attendance.no_show,
    )

    if updated is None:
        raise HTTPException(
            status_code=404,
            detail="Το ραντεβού δεν βρέθηκε ή δεν έχει λήξει ακόμη."
        )

    return updated
