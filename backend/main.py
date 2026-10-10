from fastapi import FastAPI
from datetime import datetime
from pydantic import BaseModel
from fastapi import HTTPException
from database import get_appointments_from_db,create_appointment_in_db

app = FastAPI()

class AppointmentCreate(BaseModel):
    patient_name: str
    patient_phone: str
    starts_at: datetime
    patient_AMKA: str

appointments: list[dict] = []


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
    stored_appointments = get_appointments_from_db()

    for existing in stored_appointments:
        if existing["starts_at"] == appointment.starts_at:
            raise HTTPException(
                status_code=400,
                detail="Appointment already exists at this time."
            )

    return create_appointment_in_db(
        appointment.patient_name,
        appointment.patient_phone,
        appointment.patient_AMKA,
        appointment.starts_at,
    )


@app.delete("/appointments/{appointment_id}", status_code= 204)
def delete_appointment(appointment_id: int):
    global appointments
    appointments = [
        a for a in appointments 
        if a["id"] != appointment_id
    ]

    return {"message": f"Appointment with id {appointment_id} deleted successfully."}
