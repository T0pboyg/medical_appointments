import React, { useEffect, useState } from "react";

export default function AppointmentHistory({
    appointmentId,
    onUnauthorized,
}) {
    const [open, setOpen] = useState(false);
    const [page, setPage] = useState(1);
    const [events, setEvents] = useState([]);
    const [hasMore, setHasMore] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [retry, setRetry] = useState(0);

    useEffect(() => {
        if (!open) return;

        const controller = new AbortController();
        setLoading(true);
        setError("");
        setEvents([]);
        setHasMore(false);

        async function load() {
            try {
                const response = await fetch(
                    `/api/appointments/${appointmentId}/history` +
                    `?page=${page}&page_size=10`,
                    {
                        signal: controller.signal,
                        cache: "no-store",
                    }
                );

                if (controller.signal.aborted) return;
                if (onUnauthorized(response)) return;

                if (!response.ok) {
                    throw new Error("History request failed");
                }

                const data = await response.json();

                if (!controller.signal.aborted) {
                    setEvents(data.events);
                    setHasMore(data.has_more);
                }
            } catch {
                if (!controller.signal.aborted) {
                    setError("Δεν φορτώθηκε το ιστορικό αλλαγών.");
                }
            } finally {
                if (!controller.signal.aborted) {
                    setLoading(false);
                }
            }
        }

        load();
        return () => controller.abort();
    }, [open, appointmentId, page, retry, onUnauthorized]);

    const format = value => new Date(value).toLocaleString("el-GR", {
        timeZone: "Europe/Athens",
        dateStyle: "medium",
        timeStyle: "short",
    });

    const actionLabel = action => ({
        "appointment.rescheduled": "Μεταφορά ραντεβού",
        "appointment.cancelled": "Ακύρωση ραντεβού",
    }[action] || action);

    return (
        <section
            className="appointment-history"
            aria-label={`Ιστορικό ραντεβού ${appointmentId}`}
        >
            <button
                type="button"
                aria-expanded={open}
                onClick={() => {
                    setOpen(value => !value);
                    setPage(1);
                    setEvents([]);
                    setHasMore(false);
                    setError("");
                }}
            >
                {open ? "Κλείσιμο ιστορικού" : "Ιστορικό αλλαγών"}
            </button>

            {open && (
                <>
                    <p>Νεότερες ενέργειες πρώτα — ώρα Ελλάδας.</p>

                    {loading && (
                        <p role="status">Φόρτωση ιστορικού…</p>
                    )}

                    {error && (
                        <>
                            <p role="alert">{error}</p>
                            <button
                                type="button"
                                onClick={() => setRetry(value => value + 1)}
                            >
                                Επανάληψη ιστορικού
                            </button>
                        </>
                    )}

                    {!loading && !error && events.length === 0 && (
                        <p role="status">
                            Δεν υπάρχουν καταγεγραμμένες ενέργειες
                            σε αυτή τη σελίδα.
                        </p>
                    )}

                    <ol>
                        {events.map(event => (
                            <li key={event.id}>
                                <strong>{actionLabel(event.action)}</strong>
                                <p>{format(event.occurred_at)}</p>
                                <p>
                                    Αναγνωριστικό προσωπικού:{" "}
                                    {event.actor_subject}
                                </p>
                                <p className="history-issuer">
                                    Προέλευση λογαριασμού:{" "}
                                    {event.actor_issuer}
                                </p>

                                {event.action === "appointment.rescheduled" && (
                                    event.previous_starts_at &&
                                        event.new_starts_at ? (
                                        <p>
                                            Από: {format(event.previous_starts_at)}
                                            <br />
                                            Σε: {format(event.new_starts_at)}
                                        </p>
                                    ) : (
                                        <p>
                                            Οι ώρες δεν είχαν καταγραφεί
                                            σε αυτή την παλαιότερη ενέργεια.
                                        </p>
                                    )
                                )}
                            </li>
                        ))}
                    </ol>

                    <nav aria-label="Σελίδες ιστορικού">
                        <button
                            type="button"
                            disabled={loading || page === 1}
                            onClick={() => setPage(value => value - 1)}
                        >
                            Προηγούμενη σελίδα ιστορικού
                        </button>

                        <span>Σελίδα {page}</span>

                        <button
                            type="button"
                            disabled={loading || !!error || !hasMore}
                            onClick={() => setPage(value => value + 1)}
                        >
                            Επόμενη σελίδα ιστορικού
                        </button>
                    </nav>
                </>
            )}
        </section>
    );
}