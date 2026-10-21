ALTER TABLE public.appointments
ADD COLUMN cancelled_at TIMESTAMPTZ;

DROP INDEX public.appointments_starts_at_unique;

CREATE UNIQUE INDEX appointments_starts_at_unique
ON public.appointments (starts_at)
WHERE cancelled_at IS NULL;