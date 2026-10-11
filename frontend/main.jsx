import React, { useState } from "react";
import { createRoot } from "react-dom/client";

function App() {
    const [calendarMonth, setCalendarMonth] = useState(
        () => new Date(new Date().getFullYear(), new Date().getMonth(), 1)
    );

    const monthTitle = calendarMonth.toLocaleDateString("el-GR", {
        month: "long",
        year: "numeric",
    });

    function changeMonth(offset) {
        setCalendarMonth((currentMonth) =>
            new Date(
                currentMonth.getFullYear(),
                currentMonth.getMonth() + offset,
                1
            )
        );
    }
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

                                <div className="calendar-grid" id="calendar-days"></div>
                            </div>
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