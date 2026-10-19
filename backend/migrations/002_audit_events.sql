CREATE TABLE public.audit_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actor_issuer TEXT NOT NULL,
    actor_subject TEXT NOT NULL,
    action TEXT NOT NULL,
    appointment_id INTEGER NOT NULL,
    correlation_id UUID NOT NULL
);

CREATE INDEX audit_events_appointment_idx
ON public.audit_events (appointment_id, occurred_at);