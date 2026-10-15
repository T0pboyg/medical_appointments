CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_name TEXT NOT NULL,
    patient_phone TEXT NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL
);

ALTER TABLE appointments
ADD COLUMN IF NOT EXISTS patient_amka TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS appointments_starts_at_unique
ON appointments (starts_at);