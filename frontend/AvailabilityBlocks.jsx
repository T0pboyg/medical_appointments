import React, { useEffect, useState } from "react";

function formatDate(value) {
    return new Date(value).toLocaleString("el-GR", {
        timeZone: "Europe/Athens",
        dateStyle: "short",
        timeStyle: "short",
    });
}

export default function AvailabilityBlocks({
    csrfToken,
    onUnauthorized,
}) {
    const [blocks, setBlocks] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [releasingId, setReleasingId] = useState(null);
    const [localDate, setLocalDate] = useState("");
    const [allDay, setAllDay] = useState(false);
    const [startTime, setStartTime] = useState("09:00");
    const [endTime, setEndTime] = useState("17:00");
    const [reason, setReason] = useState("");
    const [creating, setCreating] = useState(false);
    const [success, setSuccess] = useState("");

    useEffect(() => {
        const controller = new AbortController();

        async function loadBlocks() {
            try {
                const response = await fetch("/api/availability-blocks", {
                    signal: controller.signal,
                    cache: "no-store",
                });

                if (controller.signal.aborted) {
                    return;
                }

                if (onUnauthorized(response)) {
                    return;
                }

                if (!response.ok) {
                    throw new Error("Blocks request failed");
                }

                const data = await response.json();

                if (!controller.signal.aborted) {
                    setBlocks(data);
                }
            } catch {
                if (!controller.signal.aborted) {
                    setError("Δεν ήταν δυνατή η φόρτωση των αποκλεισμών.");
                }
            } finally {
                if (!controller.signal.aborted) {
                    setLoading(false);
                }
            }
        }

        loadBlocks();

        return () => controller.abort();
    }, [onUnauthorized]);

    async function handleCreate(event) {
        event.preventDefault();

        if (creating || releasingId !== null || !csrfToken) {
            return;
        }

        setCreating(true);
        setError("");
        setSuccess("");

        try {
            const response = await fetch(
                "/api/availability-blocks/local",
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": csrfToken,
                    },
                    body: JSON.stringify({
                        local_date: localDate,
                        all_day: allDay,
                        start_time: allDay ? null : startTime,
                        end_time: allDay ? null : endTime,
                        reason: reason.trim(),
                    }),
                }
            );

            if (onUnauthorized(response)) {
                return;
            }

            const data = await response.json();

            if (!response.ok) {
                let message = "Δεν ήταν δυνατή η δημιουργία αποκλεισμού.";

                if (typeof data.detail === "string") {
                    message = data.detail;
                } else if (Array.isArray(data.detail)) {
                    message = data.detail
                        .map((item) => item.msg)
                        .join(" ");
                }

                setError(message);
                return;
            }

            setBlocks((previous) =>
                [...previous, data].sort(
                    (a, b) =>
                        new Date(a.starts_at).getTime() -
                        new Date(b.starts_at).getTime()
                )
            );
            setReason("");
            setSuccess("Ο αποκλεισμός δημιουργήθηκε.");
        } catch {
            setError(
                "Δεν ήταν δυνατή η επικοινωνία. Ανανέωσε τη σελίδα για να ελέγξεις αν αποθηκεύτηκε ο αποκλεισμός."
            );
        } finally {
            setCreating(false);
        }
    }

    async function handleRelease(block) {
        if (creating || releasingId !== null || !csrfToken) {
            return;
        }

        if (!window.confirm(
            `Να αρθεί ο αποκλεισμός από ${formatDate(block.starts_at)} έως ${formatDate(block.ends_at)};`
        )) {
            return;
        }

        setSuccess("");
        setReleasingId(block.id);
        setError("");

        try {
            const response = await fetch(
                `/api/availability-blocks/${block.id}/release`,
                {
                    method: "POST",
                    headers: {
                        "X-CSRF-Token": csrfToken,
                    },
                }
            );

            if (onUnauthorized(response)) {
                return;
            }

            if (!response.ok) {
                setError(
                    "Η άρση απέτυχε. Ανανέωσε τη σελίδα και δοκίμασε ξανά."
                );
                return;
            }

            setBlocks((previous) =>
                previous.filter((item) => item.id !== block.id)
            );
        } catch {
            setError("Δεν ήταν δυνατή η επικοινωνία με τον server.");
        } finally {
            setReleasingId(null);
        }
    }

    return (
        <section className="card">
            <h2>Αποκλεισμοί διαθεσιμότητας</h2>
            <p>Οι ημερομηνίες και ώρες εμφανίζονται στην ώρα Ελλάδας.</p>

            <form onSubmit={handleCreate}>
                <fieldset
                    disabled={
                        loading ||
                        creating ||
                        releasingId !== null ||
                        !csrfToken
                    }
                >
                    <legend>Νέος αποκλεισμός</legend>

                    <div className="form-group">
                        <label htmlFor="block-date">Ημερομηνία</label>
                        <input
                            id="block-date"
                            type="date"
                            required
                            value={localDate}
                            onChange={(event) =>
                                setLocalDate(event.target.value)
                            }
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="block-all-day">
                            <input
                                id="block-all-day"
                                type="checkbox"
                                checked={allDay}
                                onChange={(event) =>
                                    setAllDay(event.target.checked)
                                }
                            />
                            Ολόκληρη ημέρα
                        </label>
                    </div>

                    {!allDay && (
                        <>
                            <div className="form-group">
                                <label htmlFor="block-start">Από</label>
                                <input
                                    id="block-start"
                                    type="time"
                                    required
                                    value={startTime}
                                    onChange={(event) =>
                                        setStartTime(event.target.value)
                                    }
                                />
                            </div>

                            <div className="form-group">
                                <label htmlFor="block-end">Έως</label>
                                <input
                                    id="block-end"
                                    type="time"
                                    required
                                    value={endTime}
                                    onChange={(event) =>
                                        setEndTime(event.target.value)
                                    }
                                />
                            </div>
                        </>
                    )}

                    <div className="form-group">
                        <label htmlFor="block-reason">
                            Αιτιολογία — μόνο για το προσωπικό
                        </label>
                        <input
                            id="block-reason"
                            type="text"
                            required
                            maxLength={200}
                            value={reason}
                            onChange={(event) =>
                                setReason(event.target.value)
                            }
                        />
                    </div>

                    <button type="submit">
                        {creating ? "Αποθήκευση…" : "Δημιουργία αποκλεισμού"}
                    </button>
                </fieldset>
            </form>

            {success && <p role="status">{success}</p>}

            {loading && <p role="status">Φόρτωση…</p>}
            {error && <p role="alert">{error}</p>}

            {!loading && !error && blocks.length === 0 && (
                <p>Δεν υπάρχουν ενεργοί αποκλεισμοί.</p>
            )}

            {!loading && !error && blocks.length > 0 && (
                <div className="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th scope="col">Από</th>
                                <th scope="col">Έως</th>
                                <th scope="col">Αιτιολογία</th>
                                <th scope="col">Ενέργεια</th>
                            </tr>
                        </thead>
                        <tbody>
                            {blocks.map((block) => (
                                <tr key={block.id}>
                                    <td>{formatDate(block.starts_at)}</td>
                                    <td>{formatDate(block.ends_at)}</td>
                                    <td>{block.reason}</td>
                                    <td>
                                        <button
                                            type="button"
                                            disabled={
                                                creating ||
                                                releasingId !== null ||
                                                !csrfToken
                                            }
                                            onClick={() => handleRelease(block)}
                                        >
                                            {releasingId === block.id ? "Άρση…" : "Άρση"}
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </section>
    );
}