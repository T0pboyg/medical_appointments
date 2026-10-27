import React, { useEffect, useState } from "react";
import { getClinicDate } from "./appointmentFilters.js";

function monthOf(day) {
    const [year, month] = day.split("-").map(Number);
    return { year, month };
}

export default function AdminCalendar({
    selectedDate,
    reloadKey,
    onSelectDate,
    onUnauthorized,
}) {
    const [visibleMonth, setVisibleMonth] = useState(() =>
        monthOf(selectedDate || getClinicDate())
    );
    const [counts, setCounts] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [retry, setRetry] = useState(0);

    const { year, month } = visibleMonth;

    // Follow a single day selected through the date filters.
    useEffect(() => {
        if (selectedDate) {
            setVisibleMonth(monthOf(selectedDate));
        }
    }, [selectedDate]);

    useEffect(() => {
        const controller = new AbortController();
        setCounts(null);
        setLoading(true);
        setError("");

        async function load() {
            try {
                const parameters = new URLSearchParams({
                    year: String(year),
                    month: String(month),
                });

                const response = await fetch(
                    `/api/appointments/calendar?${parameters}`,
                    {
                        signal: controller.signal,
                        cache: "no-store",
                    }
                );

                if (controller.signal.aborted) return;
                if (onUnauthorized(response)) return;
                if (!response.ok) {
                    throw new Error("Calendar request failed");
                }

                const data = await response.json();

                if (!controller.signal.aborted) {
                    setCounts(
                        Object.fromEntries(
                            data.days.map(item => [
                                item.date,
                                item.count,
                            ])
                        )
                    );
                }
            } catch {
                if (!controller.signal.aborted) {
                    setError("Δεν φορτώθηκαν τα πλήθη των ραντεβού.");
                }
            } finally {
                if (!controller.signal.aborted) {
                    setLoading(false);
                }
            }
        }

        load();
        return () => controller.abort();
    }, [year, month, reloadKey, retry, onUnauthorized]);

    function changeMonth(direction) {
        setVisibleMonth(current => {
            let nextYear = current.year;
            let nextMonth = current.month + direction;

            if (nextMonth === 0) {
                nextYear -= 1;
                nextMonth = 12;
            } else if (nextMonth === 13) {
                nextYear += 1;
                nextMonth = 1;
            }

            if (nextYear < 1 || nextYear > 9998) return current;
            return { year: nextYear, month: nextMonth };
        });
    }

    // UTC is used only to build the calendar grid.
    // Appointment counts are calculated in Athens by the backend.
    const firstDay = new Date(0);
    firstDay.setUTCFullYear(year, month - 1, 1);

    const lastDay = new Date(0);
    lastDay.setUTCFullYear(year, month, 0);

    const emptyCells = (firstDay.getUTCDay() + 6) % 7;
    const daysInMonth = lastDay.getUTCDate();
    const monthTitle = firstDay.toLocaleDateString("el-GR", {
        month: "long",
        year: "numeric",
        timeZone: "UTC",
    });

    return (
        <section
            className="admin-calendar"
            aria-label="Ημερολόγιο ραντεβού"
        >
            <h3>Ημερολόγιο ραντεβού</h3>
            <p>
                Τα πλήθη αφορούν όλα τα μη ακυρωμένα ραντεβού,
                ανεξάρτητα από το φίλτρο ΑΜΚΑ.
                Επίλεξε ημέρα για να εμφανιστεί στη λίστα.
            </p>

            <div className="calendar-container">
                <div className="calendar-header">
                    <button
                        type="button"
                        aria-label="Προηγούμενος μήνας ημερολογίου admin"
                        disabled={year === 1 && month === 1}
                        onClick={() => changeMonth(-1)}
                    >
                        ‹
                    </button>

                    <strong aria-live="polite">{monthTitle}</strong>

                    <button
                        type="button"
                        aria-label="Επόμενος μήνας ημερολογίου admin"
                        disabled={year === 9998 && month === 12}
                        onClick={() => changeMonth(1)}
                    >
                        ›
                    </button>
                </div>

                {loading && (
                    <p role="status">Φόρτωση ημερολογίου…</p>
                )}

                {error && (
                    <>
                        <p role="alert">{error}</p>
                        <button
                            type="button"
                            onClick={() => setRetry(value => value + 1)}
                        >
                            Επανάληψη ημερολογίου
                        </button>
                    </>
                )}

                <div className="calendar-grid">
                    {["Δε", "Τρ", "Τε", "Πε", "Πα", "Σα", "Κυ"].map(
                        label => <span key={label}>{label}</span>
                    )}

                    {Array.from({ length: emptyCells }, (_, index) => (
                        <span key={`empty-${index}`} aria-hidden="true" />
                    ))}

                    {Array.from({ length: daysInMonth }, (_, index) => {
                        const day = index + 1;
                        const date = [
                            String(year).padStart(4, "0"),
                            String(month).padStart(2, "0"),
                            String(day).padStart(2, "0"),
                        ].join("-");

                        const count = counts === null
                            ? null
                            : counts[date] || 0;
                        const selected = selectedDate === date;

                        return (
                            <button
                                key={date}
                                type="button"
                                className={
                                    `calendar-day ${selected ? "selected" : "available"
                                    }`
                                }
                                aria-pressed={selected}
                                aria-label={
                                    `${date}: ` +
                                    (count === null
                                        ? "το πλήθος δεν είναι διαθέσιμο"
                                        : `${count} μη ακυρωμένα ραντεβού`)
                                }
                                onClick={() => onSelectDate(date)}
                            >
                                <span>{day}</span>
                                <small>{count === null ? "—" : count}</small>
                            </button>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}