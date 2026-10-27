import React, { useEffect, useRef, useState } from "react";
import RescheduleAppointment from "./RescheduleAppointment.jsx";
import AppointmentHistory from "./AppointmentHistory.jsx";

export default function StaffAppointmentDetails({
    appointmentId,
    onUnauthorized,
    onClose,
    csrfToken,
    onMoved,
    onRefresh,
    onMovingChange,
}) {
    const dialog = useRef(null);
    const [details, setDetails] = useState(null);
    const [error, setError] = useState("");
    const [retry, setRetry] = useState(0);
    const [moving, setMoving] = useState(false);
    const movingRef = useRef(false);

    useEffect(() => {
        dialog.current?.showModal();
    }, []);

    useEffect(() => {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        let active = true;

        setDetails(null);
        setError("");

        async function load() {
            try {
                const response = await fetch(
                    `/api/appointments/${appointmentId}`,
                    {
                        signal: controller.signal,
                        cache: "no-store",
                    }
                );

                if (!active) return;
                if (onUnauthorized(response)) return;

                if (response.status === 404) {
                    setError("Το ραντεβού δεν βρέθηκε.");
                    return;
                }

                if (!response.ok) {
                    throw new Error("Details request failed");
                }

                const data = await response.json();

                if (active) setDetails(data);
            } catch {
                if (active) {
                    setError(
                        "Δεν φορτώθηκαν οι πληροφορίες. Δοκίμασε ξανά."
                    );
                }
            } finally {
                clearTimeout(timeout);
            }
        }

        load();

        return () => {
            active = false;
            clearTimeout(timeout);
            controller.abort();
        };
    }, [appointmentId, onUnauthorized, retry]);

    const format = value => new Date(value).toLocaleString("el-GR", {
        timeZone: "Europe/Athens",
        dateStyle: "full",
        timeStyle: "short",
    });

    const status = details
        ? details.cancelled_at
            ? "Ακυρωμένο"
            : details.no_show
                ? "Δεν προσήλθε"
                : Date.now() >=
                    new Date(details.starts_at).getTime() + 30 * 60 * 1000
                    ? "Ολοκληρωμένο"
                    : "Προγραμματισμένο"
        : "";

    return (
        <dialog
            ref={dialog}
            className="staff-appointment-dialog"
            aria-labelledby="staff-appointment-details-title"
            onCancel={event => {
                event.preventDefault();
                if (!movingRef.current) onClose();
            }}
        >
            <div className="staff-appointment-dialog-heading">
                <h3 id="staff-appointment-details-title">
                    Ραντεβού #{appointmentId}
                </h3>
                <button
                    type="button"
                    autoFocus
                    onClick={onClose}
                    disabled={moving}
                >
                    Κλείσιμο πληροφοριών
                </button>
            </div>

            {!details && !error && (
                <p role="status">Φόρτωση πληροφοριών…</p>
            )}

            {error && (
                <>
                    <p role="alert">{error}</p>
                    <button
                        type="button"
                        onClick={() => setRetry(value => value + 1)}
                    >
                        Επανάληψη πληροφοριών
                    </button>
                </>
            )}

            {details && (
                <dl>
                    <dt>Ονοματεπώνυμο</dt>
                    <dd>{details.patient_name}</dd>

                    <dt>Ημερομηνία και ώρα Ελλάδας</dt>
                    <dd>{format(details.starts_at)}</dd>

                    <dt>Τηλέφωνο</dt>
                    <dd>{details.patient_phone || "—"}</dd>

                    <dt>ΑΜΚΑ</dt>
                    <dd>{details.patient_AMKA || "—"}</dd>

                    <dt>Κατάσταση</dt>
                    <dd>{status}</dd>
                </dl>
            )}
            {details &&
                !details.cancelled_at &&
                new Date(details.starts_at).getTime() > Date.now() && (
                    <RescheduleAppointment
                        idPrefix="staff-details-reschedule"
                        appointment={details}
                        csrfToken={csrfToken}
                        busy={moving}
                        onBusyChange={id => {
                            const active = id !== null;
                            movingRef.current = active;
                            setMoving(active);
                            onMovingChange(active);
                        }}
                        onUnauthorized={onUnauthorized}
                        onMoved={onMoved}
                        onRefresh={onRefresh}
                    />
                )}

            {moving && (
                <p role="status">
                    Η μεταφορά εκτελείται. Περίμενε το αποτέλεσμα
                    πριν κλείσεις το παράθυρο.
                </p>
            )}
            {details && !moving && (
                <AppointmentHistory
                    key={details.id}
                    appointmentId={details.id}
                    onUnauthorized={onUnauthorized}
                />
            )}
        </dialog>
    );
}