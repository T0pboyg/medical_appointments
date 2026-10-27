GRANT CONNECT ON DATABASE appointments TO appointments_app;

GRANT USAGE ON SCHEMA public TO appointments_app;

GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE appointments, staff_sessions, booking_rate_limits
TO appointments_app;

GRANT USAGE
ON SEQUENCE appointments_id_seq
TO appointments_app;

GRANT INSERT
ON TABLE audit_events
TO appointments_app;

GRANT USAGE
ON SEQUENCE audit_events_id_seq
TO appointments_app;

GRANT SELECT, INSERT
ON TABLE availability_blocks
TO appointments_app;

GRANT UPDATE (released_at)
ON TABLE availability_blocks
TO appointments_app;

GRANT USAGE
ON SEQUENCE availability_blocks_id_seq
TO appointments_app;

GRANT SELECT (
    id,
    occurred_at,
    actor_issuer,
    actor_subject,
    action,
    appointment_id,
    previous_starts_at,
    new_starts_at
)
ON TABLE public.audit_events
TO appointments_app;