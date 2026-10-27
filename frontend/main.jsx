import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import Admin from "./Admin.jsx";
import MedicalAssistant from "./MedicalAssistant.jsx";
import BookingCalendar from "./BookingCalendar.jsx";
import { clinicSlotToIso } from "./appointmentFilters.js";

function App() {
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
            clinicSlotToIso(selectedDate, selectedTime)
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

                const fieldErrors = {
                    patient_name: "Ονοματεπώνυμο: συμπλήρωσε από 1 έως 100 χαρακτήρες.",
                    patient_phone: "Τηλέφωνο: δώσε ελληνικό κινητό (69…) ή σταθερό (2…) με 10 ψηφία. Επιτρέπεται το πρόθεμα +30.",
                    patient_AMKA: "ΑΜΚΑ: συμπλήρωσε ακριβώς 11 ψηφία.",
                    starts_at: "Ημέρα και ώρα: επίλεξε ξανά ένα διαθέσιμο ραντεβού.",
                };
                const details = Array.isArray(errorData.detail)
                    ? [...new Set(errorData.detail.map((error) =>
                        fieldErrors[error.loc?.[1]] || "Έλεγξε τα στοιχεία του ραντεβού."
                    ))].join(" ")
                    : "";

                setMessage(
                    typeof errorData.detail === "string"
                        ? errorData.detail
                        : details || "Η κράτηση απέτυχε. Έλεγξε τα στοιχεία του ραντεβού."
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
        <div className="app-container booking-app">
            <header className="site-header">
                <a className="brand" href="/" aria-label="Αρχική"><span className="brand-mark" aria-hidden="true">+</span><span>ιατρείο<span className="brand-dot">.</span></span></a>
                <span className="header-note"><span className="status-dot" /> Online ραντεβού</span>
            </header>
            <section className="booking-hero" aria-labelledby="booking-title">
                <h1 id="booking-title">Η φροντίδα σου ξεκινά<br /><em>με ένα ραντεβού.</em></h1>
                <p>Επίλεξε ημέρα και ώρα για την επίσκεψή σου.</p>
            </section>
            <div className="booking-layout">


            <main>
                <section className="card" aria-labelledby="create-heading">
                    <div className="card-heading"><span className="eyebrow">ΚΛΕΙΣΕ ΤΗΝ ΕΠΙΣΚΕΨΗ ΣΟΥ</span><h2 id="create-heading">Ας βρούμε την ώρα σου<span className="brand-dot">.</span></h2></div>
                    <ol className="booking-steps" aria-label="Πρόοδος κράτησης"><li className="active"><span>01</span> Στοιχεία</li><li className={selectedDate ? "active" : ""}><span>02</span> Ημέρα</li><li className={selectedTime ? "active" : ""}><span>03</span> Ώρα</li></ol>

                    <form id="appointment-form" onSubmit={handleSubmit}>
                        <div className="form-group">
                            <label htmlFor="patient-name">Ονοματεπώνυμο</label>
                            <input
                                type="text"
                                id="patient-name"
                                name="patient_name"
                                autoComplete="name"
                                maxLength={100}
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
                                maxLength={30}
                                pattern="(?:\+30)?[ \-]*(?:69[0-9]|2[0-9]{2})(?:[ \-]*[0-9]){7}"
                                title="Ελληνικό κινητό (69…) ή σταθερό (2…) με 10 ψηφία, προαιρετικά με +30."
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
                            <p className="section-label">Ημέρα &amp; ώρα <span>Δευτέρα – Παρασκευή</span></p>

                            <BookingCalendar
                                selectedDate={selectedDate}
                                disabled={isSubmitting}
                                onSelectDate={day => {
                                    setSelectedDate(day);
                                    setSelectedTime("");
                                    setMessage("");
                                }}
                            />
                            {selectedDate && (
                                <div className="time-wrapper" aria-busy={isLoadingTimes}>
                                    <p id="time-slots-heading">Ώρα ραντεβού</p>

                                    {!isLoadingTimes && !availabilityError && availableTimeSlots.length > 0 && (
                                        <div className="time-chips" role="group" aria-labelledby="time-slots-heading">
                                            {availableTimeSlots.map((time) => (
                                                <button type="button" key={time} aria-pressed={selectedTime === time} className={selectedTime === time ? "time-chip selected" : "time-chip"} onClick={() => { setSelectedTime(time); setMessage(""); }}>{time}</button>
                                            ))}
                                        </div>
                                    )}

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

                        <div className="appointment-summary" aria-live="polite">
                        <span className="eyebrow">Η ΕΠΙΛΟΓΗ ΣΟΥ</span>
                        <strong>{selectedDate ? new Date(`${selectedDate}T12:00:00`).toLocaleDateString("el-GR", { weekday: "long", day: "numeric", month: "long" }) : "Επίλεξε ημέρα"}</strong>
                        <span>{selectedTime ? `Ώρα επίσκεψης · ${selectedTime}` : selectedDate ? "Διάλεξε μία από τις διαθέσιμες ώρες." : "Επίλεξε ημέρα από το ημερολόγιο."}</span>
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
        </div>
    );
}

const rootElement = document.getElementById("root");

if (rootElement) {
    const page =
        window.location.pathname === "/admin" ? <Admin /> : <App />;

    createRoot(rootElement).render(<>{page}{window.location.pathname !== "/admin" && <MedicalAssistant />}</>);
}
