import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";

function App() {
    const [calendarMonth, setCalendarMonth] = useState(
        () => new Date(new Date().getFullYear(), new Date().getMonth(), 1)
    );
    const [selectedDate, setSelectedDate] = useState(null);
    const [selectedTime, setSelectedTime] = useState("");
    const [message, setMessage] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [serverTimeSlots, setServerTimeSlots] = useState([]);
    const [isLoadingTimes, setIsLoadingTimes] = useState(false);
    const [availabilityError, setAvailabilityError] = useState("");

    useEffect(() => {
        setServerTimeSlots([]);
        setAvailabilityError("");

        if (!selectedDate) {
            setIsLoadingTimes(false);
            return;
        }

        const controller = new AbortController();
        setIsLoadingTimes(true);

        async function fetchAvailability() {
            try {
                const response = await fetch(
                    `/api/availability?date=${selectedDate}`,
                    { signal: controller.signal }
                );

                if (!response.ok) {
                    throw new Error("Availability request failed");
                }

                const times = await response.json();

                if (!controller.signal.aborted) {
                    setServerTimeSlots(times);
                }
            } catch (error) {
                if (!controller.signal.aborted) {
                    setAvailabilityError(
                        "Δεν ήταν δυνατή η φόρτωση διαθέσιμων ωρών."
                    );
                }
            } finally {
                if (!controller.signal.aborted) {
                    setIsLoadingTimes(false);
                }
            }
        }

        fetchAvailability();

        return () => controller.abort();
    }, [selectedDate]);

    const monthTitle = calendarMonth.toLocaleDateString("el-GR", {
        month: "long",
        year: "numeric",
    });

    function changeMonth(offset) {
        setCalendarMonth(
            (currentMonth) =>
                new Date(
                    currentMonth.getFullYear(),
                    currentMonth.getMonth() + offset,
                    1
                )
        );
    }

    const year = calendarMonth.getFullYear();
    const month = calendarMonth.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const firstDayOffset = (new Date(year, month, 1).getDay() + 6) % 7;

    const calendarCells = [
        ...Array(firstDayOffset).fill(null),
        ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
    ];

    const availableTimeSlots = serverTimeSlots;

    async function handleSubmit(event) {
        event.preventDefault();

        if (isSubmitting) {
            return;
        }

        if (!selectedDate || !selectedTime) {
            setMessage("Επίλεξε ημέρα και ώρα για το ραντεβού.");
            return;
        }

        const selectedDateTime = new Date(
            `${selectedDate}T${selectedTime}:00`
        );

        if (selectedDateTime <= new Date()) {
            setMessage("Η ώρα που επέλεξες έχει περάσει. Επίλεξε επόμενη ώρα.");
            setSelectedTime("");
            return;
        }

        const form = event.currentTarget;
        const formData = new FormData(form);

        const appointmentData = {
            patient_name: formData.get("patient_name"),
            patient_phone: formData.get("patient_phone"),
            patient_AMKA: formData.get("patient_AMKA"),
            starts_at: selectedDateTime.toISOString(),
        };

        setMessage("Αποθήκευση ραντεβού…");
        setIsSubmitting(true);

        try {
            const response = await fetch("/api/appointments", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(appointmentData),
            });

            if (!response.ok) {
                const errorData = await response.json();

                setMessage(
                    typeof errorData.detail === "string"
                        ? errorData.detail
                        : "Η κράτηση απέτυχε. Έλεγξε τα στοιχεία του ραντεβού."
                );
                return;
            }

            setSelectedTime("");
            setSelectedDate(null);
            form.reset();
            setMessage("Το ραντεβού κλείστηκε επιτυχώς.");
        } catch {
            setMessage("Δεν ήταν δυνατή η επικοινωνία με τον server.");
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <div className="app-container">
            <header>
                <h1>Ιατρείο — Διαχείριση ραντεβού</h1>
            </header>

            <main>
                <section className="card" aria-labelledby="create-heading">
                    <h2 id="create-heading">Νέο ραντεβού</h2>

                    <form id="appointment-form" onSubmit={handleSubmit}>
                        <div className="form-group">
                            <label htmlFor="patient-name">Ονοματεπώνυμο</label>
                            <input
                                type="text"
                                id="patient-name"
                                name="patient_name"
                                autoComplete="name"
                                placeholder="π.χ. Μαρία Παπαδοπούλου"
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="patient-phone">Τηλέφωνο</label>
                            <input
                                type="tel"
                                id="patient-phone"
                                name="patient_phone"
                                autoComplete="tel"
                                placeholder="π.χ. 6912345678"
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="patient-amka">ΑΜΚΑ</label>
                            <input
                                type="text"
                                id="patient-amka"
                                name="patient_AMKA"
                                inputMode="numeric"
                                pattern="[0-9]{11}"
                                maxLength={11}
                                title="Συμπλήρωσε 11 ψηφία"
                                placeholder="11 ψηφία"
                                required
                            />
                        </div>

                        <div className="form-group">
                            <p>Επιλογή Ημέρας &amp; Ώρας</p>

                            <div id="custom-calendar" className="calendar-container">
                                <div className="calendar-header">
                                    <button
                                        type="button"
                                        id="prev-month"
                                        aria-label="Προηγούμενος μήνας"
                                        onClick={() => changeMonth(-1)}
                                    >
                                        &lt;
                                    </button>

                                    <span id="month-year-display">{monthTitle}</span>

                                    <button
                                        type="button"
                                        id="next-month"
                                        aria-label="Επόμενος μήνας"
                                        onClick={() => changeMonth(1)}
                                    >
                                        &gt;
                                    </button>
                                </div>

                                <div className="calendar-grid" id="calendar-days">
                                    {["Δε", "Τρ", "Τε", "Πε", "Πα", "Σα", "Κυ"].map((label) => (
                                        <span key={label}>{label}</span>
                                    ))}

                                    {calendarCells.map((day, index) => {
                                        if (day === null) {
                                            return <span key={`empty-${index}`} />;
                                        }

                                        const cellDate = new Date(year, month, day);
                                        const weekday = cellDate.getDay();
                                        const isWeekend = weekday === 0 || weekday === 6;

                                        const today = new Date();
                                        today.setHours(0, 0, 0, 0);

                                        const isPastDay = cellDate < today;
                                        const isDisabled = isWeekend || isPastDay;

                                        const dateValue = [
                                            year,
                                            String(month + 1).padStart(2, "0"),
                                            String(day).padStart(2, "0"),
                                        ].join("-");

                                        const isSelected = selectedDate === dateValue;

                                        return (
                                            <button
                                                key={day}
                                                type="button"
                                                className={`calendar-day ${isDisabled
                                                        ? "disabled"
                                                        : isSelected
                                                            ? "selected"
                                                            : "available"
                                                    }`}
                                                onClick={() => {
                                                    setSelectedDate(dateValue);
                                                    setSelectedTime("");
                                                    setMessage("");
                                                }}
                                                aria-pressed={isSelected}
                                                disabled={isDisabled}
                                                aria-label={`${day} ${monthTitle}`}
                                            >
                                                {day}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>

                            {selectedDate && (
                                <div className="time-wrapper">
                                    <label htmlFor="time-slot">Ώρα ραντεβού</label>

                                    <select
                                        id="time-slot"
                                        name="time_slot"
                                        value={selectedTime}
                                        disabled={
                                            isLoadingTimes ||
                                            Boolean(availabilityError) ||
                                            availableTimeSlots.length === 0
                                        }
                                        onChange={(event) => {
                                            setSelectedTime(event.target.value);
                                            setMessage("");
                                        }}
                                    >
                                        <option value="" disabled>
                                            Επιλέξτε ώρα
                                        </option>

                                        {availableTimeSlots.map((time) => (
                                            <option key={time} value={time}>
                                                {time}
                                            </option>
                                        ))}
                                    </select>

                                    {isLoadingTimes && (
                                        <p role="status">Φόρτωση διαθέσιμων ωρών…</p>
                                    )}

                                    {availabilityError && (
                                        <p role="status">{availabilityError}</p>
                                    )}

                                    {!isLoadingTimes &&
                                        !availabilityError &&
                                        availableTimeSlots.length === 0 && (
                                            <p role="status">
                                                Δεν υπάρχουν διαθέσιμες ώρες για αυτή την ημέρα.
                                            </p>
                                        )}
                                </div>
                            )}
                        </div>

                        <button
                            type="submit"
                            className="btn-submit"
                            disabled={isSubmitting}
                        >
                            {isSubmitting ? "Αποθήκευση…" : "Κλείσε Ραντεβού"}
                        </button>
                    </form>

                    <p id="message" role="status" aria-live="polite">
                        {message}
                    </p>
                </section>
            </main>
        </div>
    );
}

const rootElement = document.getElementById("root");

if (rootElement) {
    createRoot(rootElement).render(<App />);
}