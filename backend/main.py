from fastapi import FastAPI
from datetime import datetime
from pydantic import BaseModel

app = FastAPI()

class AppointmentCreate(BaseModel):
    patient_name: str
    starts_at: datetime
    appointments: list[AppointmentCreate] = []


@app.get("/")
def read_root():
    return {"message": "Το API ανανεώνεται αυτόματα"}


@app.get("/appointments")
def get_appointments():
    return appointments


@app.post("/appointments", status_code=201)
def create_appointment(appointment: AppointmentCreate):
    appointments.append(appointment)
    return appointment