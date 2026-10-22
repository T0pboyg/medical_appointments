CREATE TABLE public.availability_blocks (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    released_at TIMESTAMPTZ,
    CHECK (ends_at > starts_at),
    CHECK (char_length(btrim(reason)) BETWEEN 1 AND 200)
);

CREATE INDEX availability_blocks_active_interval_idx
ON public.availability_blocks (starts_at, ends_at)
WHERE released_at IS NULL;

ALTER TABLE public.audit_events
ALTER COLUMN appointment_id DROP NOT NULL;

ALTER TABLE public.audit_events
ADD COLUMN availability_block_id INTEGER;

ALTER TABLE public.audit_events
ADD CONSTRAINT audit_events_single_target_check
CHECK (
    (appointment_id IS NOT NULL AND availability_block_id IS NULL)
    OR
    (appointment_id IS NULL AND availability_block_id IS NOT NULL)
);

CREATE INDEX audit_events_availability_block_idx
ON public.audit_events (availability_block_id, occurred_at)
WHERE availability_block_id IS NOT NULL;