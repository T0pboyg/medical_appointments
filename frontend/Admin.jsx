import React, { useCallback, useEffect, useState } from "react";
import AvailabilityBlocks from "./AvailabilityBlocks.jsx";
import "./Admin.css";
import { matchesAppointmentFilters } from "./appointmentFilters.js";

export default function Admin() {
    const [appointments, setAppointments] = useState([]);
    const [loadError, setLoadError] = useState("");
    const [searchAmka, setSearchAmka] = useState("");
    const [searchDate, setSearchDate] = useState("");
    const [updatingId, setUpdatingId] = useState(null);
    const [csrfToken, setCsrfToken] = useState("");
    const [needsLogin, setNeedsLogin] = useState(false);

    const handleUnauthorized = useCallback((response) => {
        if (response.status !== 401) {
            return false;
        }

        setAppointments([]);
        setSearchAmka("");
        setSearchDate("");
        setCsrfToken("");
        setNeedsLogin(true);
        setLoadError("Η σύνδεση δεν είναι πλέον ενεργή. Συνδέσου ξανά.");

        return true;
    }, []);

    useEffect(() => {
        const controller = new AbortController();

        async function fetchAppointments() {
            try {
                const csrfResponse = await fetch("/api/auth/csrf", {
                    signal: controller.signal,
                    cache: "no-store",
                });

                if (controller.signal.aborted) {
                    return;
                }

                if (handleUnauthorized(csrfResponse)) {
                    return;
                }

                if (!csrfResponse.ok) {
                    throw new Error("CSRF request failed");
                }

                const csrfData = await csrfResponse.json();

                if (controller.signal.aborted) {
                    return;
                }

                setCsrfToken(csrfData.csrf_token);

                const response = await fetch("/api/appointments", {
                    signal: controller.signal,
                    cache: "no-store",
                });

                if (controller.signal.aborted) {
                    return;
                }

                if (handleUnauthorized(response)) {
                    return;
                }

                if (!response.ok) {
                    throw new Error("Appointments request failed");
                }

                const data = await response.json();

                if (!controller.signal.aborted) {
                    setAppointments(data);
                }
            } catch {
                if (!controller.signal.aborted) {
                    setLoadError("Δεν ήταν δυνατή η φόρτωση των ραντεβού.");
                }
            }
        }

        fetchAppointments();

        return () => controller.abort();
    }, [handleUnauthorized]);

    const filteredAppointments = appointments.filter(
        (appointment) =>
            matchesAppointmentFilters(appointment, searchAmka, searchDate)
    );

    function getAppointmentStatus(appointment) {
        if (appointment.cancelled_at) {
            return "Ακυρωμένο";
        }

        if (appointment.no_show) {
            return "Δεν προσήλθε";
        }

        const endsAt =
            new Date(appointment.starts_at).getTime() + 30 * 60 * 1000;

        return Date.now() >= endsAt
            ? "Ολοκληρωμένο"
            : "Προγραμματισμένο";
    }

    async function handleAttendanceChange(appointment) {
        if (updatingId !== null) {
            return;
        }

        if (!csrfToken) {
            setLoadError("Χρειάζεται ανανέωση της σελίδας ή νέα σύνδεση.");
            return;
        }

        setUpdatingId(appointment.id);
        setLoadError("");

        try {
            const response = await fetch(
                `/api/appointments/${appointment.id}/attendance`,
                {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": csrfToken,
                    },
                    body: JSON.stringify({
                        no_show: !appointment.no_show,
                    }),
                }
            );

            if (handleUnauthorized(response)) {
                return;
            }

            if (!response.ok) {
                setLoadError("Δεν ήταν δυνατή η αλλαγή κατάστασης.");
                return;
            }

            const updated = await response.json();

            setAppointments((previous) =>
                previous.map((item) =>
                    item.id === updated.id
                        ? { ...item, no_show: updated.no_show }
                        : item
                )
            );
        } catch {
            setLoadError("Δεν ήταν δυνατή η επικοινωνία με τον server.");
        } finally {
            setUpdatingId(null);
        }
    }

    async function handleCancel(appointment) {
        if (updatingId !== null) {
            return;
        }

        if (!csrfToken) {
            setLoadError("Χρειάζεται ανανέωση της σελίδας ή νέα σύνδεση.");
            return;
        }

        if (
            !window.confirm(
                `Να ακυρωθεί το ραντεβού #${appointment.id}; Η ώρα θα ελευθερωθεί.`
            )
        ) {
            return;
        }

        setUpdatingId(appointment.id);
        setLoadError("");

        try {
            const response = await fetch(
                `/api/appointments/${appointment.id}/cancel`,
                {
                    method: "POST",
                    headers: {
                        "X-CSRF-Token": csrfToken,
                    },
                }
            );

            if (handleUnauthorized(response)) {
                return;
            }

            if (!response.ok) {
                setLoadError(
                    "Η ακύρωση απέτυχε. Ανανέωσε τη σελίδα και δοκίμασε ξανά."
                );
                return;
            }

            const cancelled = await response.json();

            setAppointments((previous) =>
                previous.map((item) =>
                    item.id === cancelled.id
                        ? {
                            ...item,
                            cancelled_at: cancelled.cancelled_at,
                        }
                        : item
                )
            );
        } catch {
            setLoadError("Δεν ήταν δυνατή η επικοινωνία με τον server.");
        } finally {
            setUpdatingId(null);
        }
    }

    async function handleLogout() {
        setLoadError("");

        try {
            const response = await fetch("/api/auth/logout", {
                method: "POST",
                headers: {
                    "X-CSRF-Token": csrfToken,
                },
            });

            if (handleUnauthorized(response)) {
                return;
            }

            if (!response.ok) {
                setLoadError("Η αποσύνδεση απέτυχε. Δοκίμασε ξανά.");
                return;
            }

            setAppointments([]);
            setCsrfToken("");
            window.location.assign("/");
        } catch {
            setLoadError("Δεν ήταν δυνατή η επικοινωνία με τον server.");
        }
    }

    return (
        <div className="app-container admin-app">
            <header className="admin-topbar">
                <a className="admin-brand" href="/admin"><span className="admin-brand-mark" aria-hidden="true">+</span> ιατρείο<span className="admin-brand-caption">ΠΕΡΙΒΑΛΛΟΝ ΠΡΟΣΩΠΙΚΟΥ</span></a>

                <button
                    type="button"
                    onClick={handleLogout}
                    disabled={needsLogin || !csrfToken}
                >
                    Αποσύνδεση
                </button>
            </header>

            <main><div className="admin-page-heading"><p className="admin-eyebrow">ΟΡΓΑΝΩΣΗ ΙΑΤΡΕΙΟΥ</p><h1>Τα ραντεβού σας</h1><p className="admin-subtitle">Όλες οι επισκέψεις σε μία καθαρή, συγκεντρωμένη προβολή.</p></div>
                <section className="card">
                    <h2>Ραντεβού</h2><p className="admin-section-note">Ημερομηνίες και ώρες Ελλάδας</p>

                    <div className="admin-filters" role="search" aria-label="Αναζήτηση ραντεβού">
                        <div className="form-group">
                        <label htmlFor="admin-search-amka">
                            Αναζήτηση με ΑΜΚΑ
                        </label>
                        <input
                            id="admin-search-amka"
                            type="text"
                            inputMode="numeric"
                            maxLength={11}
                            placeholder="Πληκτρολόγησε τα 11 ψηφία του ΑΜΚΑ"
                            value={searchAmka}
                            onChange={(event) =>
                                setSearchAmka(event.target.value)
                            }
                        />
                    </div>
                        <div className="form-group">
                            <label htmlFor="admin-search-date">Ημερομηνία ραντεβού</label>
                            <input id="admin-search-date" type="date" value={searchDate}
                                onChange={(event) => setSearchDate(event.target.value)} />
                        </div>
                        {(searchAmka || searchDate) && <button className="admin-clear-filters" type="button" onClick={() => {setSearchAmka("");setSearchDate("");}}>Καθαρισμός φίλτρων</button>}
                    </div>
                    <p className="admin-filter-hint">Αναζήτηση με ΑΜΚΑ, ημερομηνία ή και τα δύο μαζί.</p>

                    {loadError && <p role="alert">{loadError}</p>}

                    {needsLogin && (
                        <a href="/api/auth/login">
                            Σύνδεση προσωπικού
                        </a>
                    )}

                    <div className="appointment-list" aria-label="Λίστα ραντεβού">
                        {filteredAppointments.map((appointment) => (
                            <article className="appointment-card" key={appointment.id} aria-label={`Ραντεβού ${appointment.id}`}>
                                <div className="appointment-card-heading"><span>Ραντεβού #{appointment.id}</span><span className="status-badge" data-status={getAppointmentStatus(appointment)}>{getAppointmentStatus(appointment)}</span></div>
                                <dl className="appointment-details">
                                    <div><dt>Ημερομηνία</dt><dd>{new Date(appointment.starts_at).toLocaleDateString("el-GR", {timeZone: "Europe/Athens", day: "2-digit", month: "2-digit", year: "numeric"})}</dd></div>
                                    <div><dt>Ώρα</dt><dd className="appointment-time">{new Date(appointment.starts_at).toLocaleTimeString("el-GR", {timeZone: "Europe/Athens", hour: "2-digit", minute: "2-digit"})}</dd></div>
                                    <div className="appointment-patient"><dt>Ασθενής</dt><dd>{appointment.patient_name}</dd><span className="appointment-reference">Ραντεβού #{appointment.id}</span></div>
                                </dl>
                                <div className="appointment-actions">
                                            {!appointment.cancelled_at &&
                                                Date.now() >=
                                                new Date(
                                                    appointment.starts_at
                                                ).getTime() +
                                                30 * 60 * 1000 && (
                                                    <button
                                                        type="button"
                                                        disabled={
                                                            updatingId !== null ||
                                                            !csrfToken
                                                        }
                                                        onClick={() =>
                                                            handleAttendanceChange(
                                                                appointment
                                                            )
                                                        }
                                                    >
                                                        {updatingId ===
                                                            appointment.id
                                                            ? "Αποθήκευση…"
                                                            : appointment.no_show
                                                                ? "Επαναφορά σε ολοκληρωμένο"
                                                                : "Δεν προσήλθε"}
                                                    </button>
                                                )}

                                            {!appointment.cancelled_at &&
                                                new Date(
                                                    appointment.starts_at
                                                ).getTime() > Date.now() && (
                                                    <button
                                                        type="button"
                                                        disabled={
                                                            updatingId !== null ||
                                                            !csrfToken
                                                        }
                                                        onClick={() =>
                                                            handleCancel(
                                                                appointment
                                                            )
                                                        }
                                                    >
                                                        {updatingId ===
                                                            appointment.id
                                                            ? "Ακύρωση…"
                                                            : "Ακύρωση ραντεβού"}
                                                    </button>
                                                )}

                                </div>
                            </article>
                        ))}
                        {csrfToken && !loadError && filteredAppointments.length === 0 && <p className="admin-empty" role="status">{searchAmka || searchDate ? "Δεν βρέθηκαν ραντεβού με τα επιλεγμένα φίλτρα." : "Δεν υπάρχουν καταχωρισμένα ραντεβού."}</p>}
                    </div>
                </section>
                {csrfToken && !needsLogin && (
                    <details className="admin-blocks-panel"><summary><span><strong>Μπλοκάρισμα ωρών</strong><span className="admin-blocks-hint">Διαχείριση άδειας ή μη διαθέσιμων διαστημάτων</span></span><span className="admin-expand-label">Άνοιγμα / κλείσιμο</span></summary><AvailabilityBlocks csrfToken={csrfToken} onUnauthorized={handleUnauthorized} /></details>
                )}
            </main>
        </div>
    );
}