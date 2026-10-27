import React, { useEffect, useRef, useState } from "react";
import { clinicSlotToIso, getClinicDate } from "./appointmentFilters.js";

export default function RescheduleAppointment({
    appointment,
    csrfToken,
    busy,
    onBusyChange,
    onUnauthorized,
    onMoved,
    onRefresh,
}) {
    const [open, setOpen] = useState(false);
    const [day, setDay] = useState(() =>
        getClinicDate(new Date(appointment.starts_at))
    );
    const [slots, setSlots] = useState([]);
    const [slot, setSlot] = useState("");
    const [loading, setLoading] = useState(false);
    const [loadError, setLoadError] = useState("");
    const [error, setError] = useState("");
    const [retry, setRetry] = useState(0);
    const [mustRefresh, setMustRefresh] = useState(false);
    const submitting = useRef(false);

    useEffect(() => {
        if (!open || !day) return;

        const controller = new AbortController();
        setLoading(true);
        setLoadError("");
        setSlots([]);
        setSlot("");

        async function load() {
            try {
                const response = await fetch(
                    `/api/availability?date=${encodeURIComponent(day)}`,
                    {
                        signal: controller.signal,
                        cache: "no-store",
                    }
                );

                if (!response.ok) {
                    throw new Error("Availability request failed");
                }

                const data = await response.json();

                if (!controller.signal.aborted) {
                    setSlots(data);
                }
            } catch {
                if (!controller.signal.aborted) {
                    setLoadError("Δεν φορτώθηκαν οι διαθέσιμες ώρες.");
                }
            } finally {
                if (!controller.signal.aborted) {
                    setLoading(false);
                }
            }
        }

        load();
        return () => controller.abort();
    }, [open, day, retry]);

    async function submit(event) {
        event.preventDefault();

        if (
            submitting.current ||
            busy ||
            loading ||
            mustRefresh ||
            !csrfToken ||
            !slots.includes(slot)
        ) {
            return;
        }

        setError("");

        let startsAt;
        try {
            startsAt = clinicSlotToIso(day, slot);
        } catch {
            setError("Έλεγξε την ημερομηνία και την ώρα.");
            return;
        }

        const original = new Date(
            appointment.starts_at
        ).toLocaleString("el-GR", {
            timeZone: "Europe/Athens",
        });

        if (!window.confirm(
            `Μεταφορά του ραντεβού #${appointment.id} ` +
            `από ${original} σε ${day}, ${slot} ώρα Ελλάδας;`
        )) {
            return;
        }

        submitting.current = true;
        onBusyChange(appointment.id);

        try {
            const response = await fetch(
                `/api/appointments/${appointment.id}/reschedule`,
                {
                    method: "POST",
                    cache: "no-store",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": csrfToken,
                    },
                    body: JSON.stringify({
                        starts_at: startsAt,
                        expected_starts_at: appointment.starts_at,
                    }),
                }
            );

            if (onUnauthorized(response)) return;

            if (response.status === 409) {
                setError(
                    "Το ραντεβού έχει αλλάξει ή η ώρα δεν είναι πλέον " +
                    "διαθέσιμη. Ανανέωσε τη λίστα πριν συνεχίσεις."
                );
                setMustRefresh(true);
                return;
            }

            if (!response.ok) {
                setError(
                    response.status === 403
                        ? "Δεν επιτρέπεται η αλλαγή. Ανανέωσε τη σελίδα."
                        : "Η μεταφορά δεν ολοκληρώθηκε. Έλεγξε την ώρα και δοκίμασε ξανά."
                );
                return;
            }

            onMoved(appointment.id, day, slot);
        } catch {
            setError(
                "Δεν επιβεβαιώθηκε το αποτέλεσμα της μεταφοράς. " +
                "Ανανέωσε τη λίστα για να ελέγξεις την ώρα " +
                "πριν επαναλάβεις την ενέργεια."
            );
            setMustRefresh(true);
        } finally {
            submitting.current = false;
            onBusyChange(null);
        }
    }

    const prefix = `reschedule-${appointment.id}`;

    return (
        <div className="admin-reschedule">
            <button
                type="button"
                disabled={busy || !csrfToken}
                aria-expanded={open}
                aria-controls={`${prefix}-form`}
                onClick={() => {
                    setOpen(value => !value);
                    setSlots([]);
                    setSlot("");
                    setLoadError("");
                    setError("");
                }}
            >
                {open ? "Κλείσιμο μεταφοράς" : "Μεταφορά ραντεβού"}
            </button>

            {open && (
                <form id={`${prefix}-form`} onSubmit={submit}>
                    <p>Επίλεξε νέα ημερομηνία και ώρα Ελλάδας.</p>

                    <label htmlFor={`${prefix}-date`}>
                        Νέα ημερομηνία
                    </label>
                    <input
                        id={`${prefix}-date`}
                        type="date"
                        required
                        min={getClinicDate()}
                        value={day}
                        disabled={busy || mustRefresh}
                        onChange={event => {
                            setDay(event.target.value);
                            setSlot("");
                            setSlots([]);
                            setError("");
                        }}
                    />

                    {loading && (
                        <p role="status">Φόρτωση διαθέσιμων ωρών…</p>
                    )}

                    {loadError && (
                        <>
                            <p role="alert">{loadError}</p>
                            <button
                                type="button"
                                disabled={busy}
                                onClick={() => setRetry(value => value + 1)}
                            >
                                Επανάληψη διαθεσιμότητας
                            </button>
                        </>
                    )}

                    {!loading && !loadError && day && slots.length === 0 && (
                        <p role="status">
                            Δεν υπάρχουν διαθέσιμες ώρες για αυτή την ημερομηνία.
                        </p>
                    )}

                    <label htmlFor={`${prefix}-time`}>Νέα ώρα</label>
                    <select
                        id={`${prefix}-time`}
                        required
                        value={slot}
                        disabled={busy || loading || mustRefresh}
                        onChange={event => setSlot(event.target.value)}
                    >
                        <option value="">Επίλεξε ώρα</option>
                        {slots.map(value => (
                            <option key={value} value={value}>
                                {value}
                            </option>
                        ))}
                    </select>

                    {error && <p role="alert">{error}</p>}

                    {mustRefresh ? (
                        <button type="button" onClick={onRefresh}>
                            Ανανέωση λίστας ραντεβού
                        </button>
                    ) : (
                        <button
                            type="submit"
                            disabled={
                                busy ||
                                loading ||
                                !csrfToken ||
                                !slots.includes(slot)
                            }
                        >
                            {busy ? "Αποθήκευση…" : "Επιβεβαίωση μεταφοράς"}
                        </button>
                    )}
                </form>
            )}
        </div>
    );
}