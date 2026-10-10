from fastapi import FastAPI
from datetime import datetime
from pydantic import BaseModel
from fastapi import HTTPExpection
from database import get_appointments_from_db

app = FastAPI()

class AppointmentCreate(BaseModel):
    patient_name: str
    patient_phone: str
    starts_at: datetime
    patirnt_AMKA: str

appointments: list[dict] = []
counter = 1 


@app.get("/")
def read_root():
    return {"message": "Το API ανανεώνεται αυτόματα"}


@app.get("/appointments")
def get_appointments(patient_AMKA: str | None = None):

    stored_appointments = get_appointments_from_db()
    if patient_AMKA:
        unique_appointments = [
            a for a in stored_appointments
            if a.patient_AMKA == patient_AMKA
            ]
        return unique_appointments
    return stored_appointments


@app.post("/appointments", status_code=201)
def create_appointment(appointment: AppointmentCreate):
    global counter
    for a in appointments:
         if a["starts_at"] == new_appointment["starts_at"]:
            raise HTTPExpection(
            status_code=400,
            detail="Appointment already exists at this time."
            )

    new_appointment = {
        "id": counter,
        "patient_name": appointment.patient_name,
        "patient_phone": appointment.patient_phone,
        "patient_AMKA": appointment.patient_AMKA,
        "starts_at": appointment.starts_at 
    }

    appointments.append(new_appointment)
    counter += 1 

    return new_appointment


@app.delete("/appointments/{appointment_id}", status_code= 204)
def delete_appointment(appointment_id: int):
    global appointments
    appointments = [
        a for a in appointments 
        if a["id"] != appointment_id
    ]

    return {"message": f"Appointment with id {appointment_id} deleted successfully."}
