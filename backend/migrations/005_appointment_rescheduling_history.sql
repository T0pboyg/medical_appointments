ALTER TABLE public.audit_events
ADD COLUMN previous_starts_at TIMESTAMPTZ,
ADD COLUMN new_starts_at TIMESTAMPTZ;

ALTER TABLE public.audit_events
ADD CONSTRAINT audit_events_rescheduling_times_check
CHECK (
    (
        previous_starts_at IS NULL
        AND new_starts_at IS NULL
    )
    OR
    (
        action = 'appointment.rescheduled'
        AND appointment_id IS NOT NULL
        AND previous_starts_at IS NOT NULL
        AND new_starts_at IS NOT NULL
        AND previous_starts_at <> new_starts_at
    )
);