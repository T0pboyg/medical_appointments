from fastapi import FastAPI
from datetime import datetime
from pydantic import BaseModel
from database import get_appointments_from_db

app = FastAPI()

class AppointmentCreate(BaseModel):
    patient_name: str
    patient_phone: str
    starts_at: datetime

appointments: list[dict] = []

counter = 1


@app.get("/")
def read_root():
    return {"message": "Το API ανανεώνεται αυτόματα"}


@app.get("/appointments")
def get_appointments(patient_phone: str | None = None):
    stored_appointments = get_appointments_from_db()

    if patient_phone:
        return [
            appointment for appointment in stored_appointments
            if appointment["patient_phone"] == patient_phone
        ]

    return stored_appointments


@app.post("/appointments", status_code=201)
def create_appointment(appointment: AppointmentCreate):
    global counter
    new_appointment = {
        "id": counter,
        "patient_name": appointment.patient_name,
        "patient_phone": appointment.patient_phone,
        "starts_at": appointment.starts_at
    }

    appointments.append(new_appointment)
    counter += 1

    return new_appointment
