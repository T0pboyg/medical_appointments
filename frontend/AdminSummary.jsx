import React, { useEffect, useState } from "react";

export default function AdminSummary({
    reloadKey,
    onUnauthorized,
}) {
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [refreshKey, setRefreshKey] = useState(0);

    useEffect(() => {
        const controller = new AbortController();

        setLoading(true);
        setError("");
        setSummary(null);

        async function load() {
            try {
                const response = await fetch(
                    "/api/appointments/summary",
                    {
                        signal: controller.signal,
                        cache: "no-store",
                    }
                );

                if (controller.signal.aborted) return;
                if (onUnauthorized(response)) return;

                if (!response.ok) {
                    throw new Error("Summary request failed");
                }

                const data = await response.json();

                if (!controller.signal.aborted) {
                    setSummary(data);
                }
            } catch {
                if (!controller.signal.aborted) {
                    setError("Δεν φορτώθηκε η σύνοψη της ημέρας.");
                }
            } finally {
                if (!controller.signal.aborted) {
                    setLoading(false);
                }
            }
        }

        load();
        return () => controller.abort();
    }, [reloadKey, refreshKey, onUnauthorized]);

    const dayLabel = summary
        ? new Date(`${summary.date}T12:00:00Z`).toLocaleDateString(
            "el-GR",
            {
                day: "2-digit",
                month: "2-digit",
                year: "numeric",
                timeZone: "UTC",
            }
        )
        : "";

    const nextTime = summary?.next_starts_at
        ? new Date(summary.next_starts_at).toLocaleTimeString(
            "el-GR",
            {
                timeZone: "Europe/Athens",
                hour: "2-digit",
                minute: "2-digit",
                hour12: false,
            }
        )
        : "Κανένα επόμενο σήμερα";

    return (
        <section
            className="card admin-summary"
            aria-labelledby="admin-summary-title"
            aria-busy={loading}
        >
            <div className="admin-summary-heading">
                <h2 id="admin-summary-title">Η ημέρα στο ιατρείο</h2>

                <button
                    type="button"
                    disabled={loading}
                    onClick={() => setRefreshKey(value => value + 1)}
                >
                    Ανανέωση σύνοψης
                </button>
            </div>

            <p className="admin-section-note">
                Σήμερα σε ώρα Ελλάδας
                {dayLabel ? ` — ${dayLabel}` : ""}.
                Η σύνοψη δεν επηρεάζεται από τα φίλτρα της λίστας.
            </p>

            {loading && (
                <p role="status">Φόρτωση σύνοψης…</p>
            )}

            {error && <p role="alert">{error}</p>}

            {summary && (
                <dl className="admin-summary-grid">
                    <div>
                        <dt>Ραντεβού σήμερα</dt>
                        <dd>{summary.appointments_count}</dd>
                        <small>Χωρίς τα ακυρωμένα</small>
                    </div>

                    <div>
                        <dt>Επόμενο ραντεβού</dt>
                        <dd>{nextTime}</dd>
                        <small>Σήμερα, σε ώρα Ελλάδας</small>
                    </div>

                    <div>
                        <dt>Διαθέσιμες ώρες</dt>
                        <dd>{summary.available_slots_count}</dd>
                        <small>Για νέα κράτηση σήμερα</small>
                    </div>

                    <div>
                        <dt>Δεν προσήλθαν</dt>
                        <dd>{summary.no_show_count}</dd>
                        <small>Καταχωρισμένες μη προσελεύσεις σήμερα</small>
                    </div>
                </dl>
            )}
        </section>
    );
}