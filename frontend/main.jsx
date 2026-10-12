import React, { useState } from "react";
import { createRoot } from "react-dom/client";

function App() {
    const [calendarMonth, setCalendarMonth] = useState(
        () => new Date(new Date().getFullYear(), new Date().getMonth(), 1)
    );
    const [selectedDate, setSelectedDate] = useState(null);
    const [selectedTime, setSelectedTime] = useState("");

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

    const timeSlots = Array.from({ length: 16 }, (_, index) => {
        const totalMinutes = 9 * 60 + index * 30;
        const hours = String(Math.floor(totalMinutes / 60)).padStart(2, "0");
        const minutes = String(totalMinutes % 60).padStart(2, "0");

        return `${hours}:${minutes}`;
    });

    return (
        <div className="app-container">
            <header>
                <h1>Ιατρείο — Διαχείριση ραντεβού</h1>
            </header>

            <main>
                <section className="card" aria-labelledby="create-heading">
                    <h2 id="create-heading">Νέο ραντεβού</h2>

                    <form id="appointment-form">
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

                                        const weekday = new Date(year, month, day).getDay();
                                        const isWeekend = weekday === 0 || weekday === 6;

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
                                                className={`calendar-day ${isWeekend
                                                        ? "disabled"
                                                        : isSelected
                                                            ? "selected"
                                                            : "available"
                                                    }`}
                                                onClick={() => {
                                                    setSelectedDate(dateValue);
                                                    setSelectedTime("");
                                                }}
                                                aria-pressed={isSelected}
                                                disabled={isWeekend}
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
                                        required
                                        value={selectedTime}
                                        onChange={(event) => setSelectedTime(event.target.value)}
                                    >
                                        <option value="" disabled>
                                            Επιλέξτε ώρα
                                        </option>

                                        {timeSlots.map((time) => (
                                            <option key={time} value={time}>
                                                {time}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            )}
                        </div>
                    </form>
                </section>
            </main>
        </div>
    );
}

const rootElement = document.getElementById("root");

if (rootElement) {
    createRoot(rootElement).render(<App />);
}