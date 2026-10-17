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

ALTER TABLE appointments
ADD COLUMN IF NOT EXISTS no_show BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS staff_sessions (
    session_hash TEXT PRIMARY KEY,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS staff_sessions_expires_at_idx
ON staff_sessions (expires_at);