import React, { useCallback, useEffect, useState } from "react";
import AvailabilityBlocks from "./AvailabilityBlocks.jsx";
import StaffAssistant from "./StaffAssistant.jsx";
import "./Admin.css";
import { getClinicDate } from "./appointmentFilters.js";
import RescheduleAppointment from "./RescheduleAppointment.jsx";
import AdminCalendar from "./AdminCalendar.jsx";
import AppointmentHistory from "./AppointmentHistory.jsx";

function AppointmentDetails({ id, onUnauthorized }) {
    const [open, setOpen] = useState(false);
    const [details, setDetails] = useState(null);
    const [error, setError] = useState("");
    const [retry, setRetry] = useState(0);

    useEffect(() => {
        if (!open) return;
        const controller = new AbortController();
        setDetails(null);
        setError("");
        async function load() {
            try {
                const response = await fetch(`/api/appointments/${id}`, {
                    signal: controller.signal, cache: "no-store",
                });
                if (controller.signal.aborted || onUnauthorized(response)) return;
                if (!response.ok) throw new Error("Details request failed");
                const data = await response.json();
                if (!controller.signal.aborted) setDetails(data);
            } catch {
                if (!controller.signal.aborted) setError("Δεν ήταν δυνατή η φόρτωση των λεπτομερειών.");
            }
        }
        load();
        return () => controller.abort();
    }, [open, id, onUnauthorized, retry]);

    return <div className="admin-private-details">
        <button type="button" aria-expanded={open} aria-controls={`appointment-details-${id}`}
            onClick={() => { setOpen(value => !value); setDetails(null); setError(""); }}>
            {open ? "Κλείσιμο λεπτομερειών" : "Λεπτομέρειες"}
        </button>
        {open && <div id={`appointment-details-${id}`}>
            {error ? <><p role="alert">{error}</p><button type="button" onClick={() => setRetry(value => value + 1)}>Επανάληψη λεπτομερειών</button></>
                : details ? <dl><div><dt>Τηλέφωνο</dt><dd>{details.patient_phone || "—"}</dd></div>
                    <div><dt>ΑΜΚΑ</dt><dd>{details.patient_AMKA || "—"}</dd></div></dl>
                    : <p role="status">Φόρτωση λεπτομερειών…</p>}
            {details && (
                <AppointmentHistory
                    key={id}
                    appointmentId={id}
                    onUnauthorized={onUnauthorized}
                />
            )}
        </div>}
    </div>;
}

export default function Admin() {
    const [appointments, setAppointments] = useState([]);
    const [loadError, setLoadError] = useState("");
    const [searchAmka, setSearchAmka] = useState("");
    const [dateFrom, setDateFrom] = useState(() => getClinicDate());
    const [dateTo, setDateTo] = useState(() => getClinicDate());

    const rangeDays = dateFrom && dateTo
        ? (
            Date.parse(`${dateTo}T00:00:00Z`) -
            Date.parse(`${dateFrom}T00:00:00Z`)
        ) / 86400000 + 1
        : NaN;

    const rangeError = !dateFrom || !dateTo
        ? "Συμπλήρωσε και τις δύο ημερομηνίες."
        : !Number.isFinite(rangeDays)
            ? "Συμπλήρωσε έγκυρες ημερομηνίες."
            : rangeDays < 1
                ? "Το «Έως» δεν μπορεί να προηγείται του «Από»."
                : rangeDays > 31
                    ? "Επίλεξε διάστημα έως 31 ημερών."
                    : "";

    const validFilters =
        !rangeError &&
        (!searchAmka || /^[0-9]{11}$/.test(searchAmka));
    const [isLoading, setIsLoading] = useState(false);
    const [reloadKey, setReloadKey] = useState(0);
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(false);
    const [updatingId, setUpdatingId] = useState(null);
    const [csrfToken, setCsrfToken] = useState("");
    const [needsLogin, setNeedsLogin] = useState(false);
    const [notice, setNotice] = useState("");

    const handleUnauthorized = useCallback((response) => {
        if (response.status !== 401) {
            return false;
        }

        setAppointments([]);
        setHasMore(false);
        setSearchAmka("");
        setDateFrom("");
        setDateTo("");
        setCsrfToken("");
        setNeedsLogin(true);
        setLoadError("Η σύνδεση δεν είναι πλέον ενεργή. Συνδέσου ξανά.");
        setNotice("");

        return true;
    }, []);

    useEffect(() => {
        if (needsLogin) {
            return;
        }

        const controller = new AbortController();

        setAppointments([]);
        setHasMore(false);
        setLoadError("");

        if (!validFilters) {
            setIsLoading(false);
            return () => controller.abort();
        }

        setIsLoading(true);

        async function fetchAppointments() {
            try {
                const csrfResponse = await fetch("/api/auth/csrf", {
                    signal: controller.signal,
                    cache: "no-store",
                });

                if (controller.signal.aborted) return;
                if (handleUnauthorized(csrfResponse)) return;

                if (!csrfResponse.ok) {
                    throw new Error("CSRF request failed");
                }

                const csrfData = await csrfResponse.json();
                if (controller.signal.aborted) return;

                setCsrfToken(csrfData.csrf_token);

                const parameters = new URLSearchParams({
                    date_from: dateFrom,
                    date_to: dateTo,
                    page: String(page),
                    page_size: "25",
                });

                if (searchAmka) {
                    parameters.set("patient_AMKA", searchAmka);
                }

                const response = await fetch(
                    `/api/appointments/page?${parameters.toString()}`,
                    {
                        signal: controller.signal,
                        cache: "no-store",
                    }
                );

                if (controller.signal.aborted) return;
                if (handleUnauthorized(response)) return;

                if (!response.ok) {
                    throw new Error("Appointments request failed");
                }

                const data = await response.json();

                if (!controller.signal.aborted) {
                    setAppointments(data.items);
                    setHasMore(data.has_more);
                }
            } catch {
                if (!controller.signal.aborted) {
                    setLoadError("Δεν ήταν δυνατή η φόρτωση των ραντεβού.");
                }
            } finally {
                if (!controller.signal.aborted) {
                    setIsLoading(false);
                }
            }
        }

        const timer = setTimeout(fetchAppointments, 300);

        return () => {
            clearTimeout(timer);
            controller.abort();
        };
    }, [
        handleUnauthorized,
        dateFrom,
        dateTo,
        validFilters,
        searchAmka,
        needsLogin,
        reloadKey,
        page,
    ]);

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

            await response.json();
            setReloadKey((value) => value + 1);
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

            await response.json();
            setReloadKey((value) => value + 1);
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
                {csrfToken && !needsLogin && <StaffAssistant csrfToken={csrfToken} onUnauthorized={handleUnauthorized}
                    onCancelled={() => setReloadKey((value) => value + 1)}
                    onRescheduled={() => setReloadKey((value) => value + 1)} />}
                <section className="card">
                    <h2>Ραντεβού</h2><p className="admin-section-note">Ημερομηνίες και ώρες Ελλάδας</p>
                    {csrfToken && !needsLogin && (
                        <AdminCalendar
                            selectedDate={dateFrom === dateTo ? dateFrom : ""}
                            reloadKey={reloadKey}
                            onUnauthorized={handleUnauthorized}
                            onSelectDate={day => {
                                setDateFrom(day);
                                setDateTo(day);
                                setPage(1);
                                setNotice("");
                                setReloadKey(value => value + 1);
                            }}
                        />
                    )}
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
                                onChange={(event) => { setSearchAmka(event.target.value); setPage(1); }
                                }
                            />
                        </div>
                        <div className="form-group">
                            <label htmlFor="admin-date-from">Από ημερομηνία</label>
                            <input
                                id="admin-date-from"
                                type="date"
                                value={dateFrom}
                                onChange={event => {
                                    setDateFrom(event.target.value);
                                    setPage(1);
                                    setNotice("");
                                }}
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="admin-date-to">Έως ημερομηνία</label>
                            <input
                                id="admin-date-to"
                                type="date"
                                value={dateTo}
                                onChange={event => {
                                    setDateTo(event.target.value);
                                    setPage(1);
                                    setNotice("");
                                }}
                            />
                        </div>

                        <button
                            className="admin-clear-filters"
                            type="button"
                            onClick={() => {
                                const today = getClinicDate();
                                setSearchAmka("");
                                setDateFrom(today);
                                setDateTo(today);
                                setPage(1);
                                setNotice("");
                            }}
                        >
                            Καθαρισμός φίλτρων
                        </button>
                    </div>
                    <p className="admin-filter-hint">Προεπιλογή: σήμερα, σε ώρα Ελλάδας. Επίλεξε διάστημα έως 31 ημερών και προαιρετικά πλήρες ΑΜΚΑ 11 ψηφίων.</p>
                    {notice && <p role="status">{notice}</p>}
                    {loadError && <p role="alert">{loadError}</p>}
                    {loadError && !needsLogin && (
                        <button type="button" disabled={isLoading}
                            onClick={() => setReloadKey((value) => value + 1)}>
                            Επανάληψη φόρτωσης
                        </button>
                    )}

                    {needsLogin && (
                        <a href="/api/auth/login">
                            Σύνδεση προσωπικού
                        </a>
                    )}

                    <div className="appointment-list" aria-label="Λίστα ραντεβού">
                        {appointments.map((appointment) => (
                            <article className="appointment-card" key={appointment.id} aria-label={`Ραντεβού ${appointment.id}`}>
                                <div className="appointment-card-heading"><span>Ραντεβού #{appointment.id}</span><span className="status-badge" data-status={getAppointmentStatus(appointment)}>{getAppointmentStatus(appointment)}</span></div>
                                <dl className="appointment-details">
                                    <div><dt>Ημερομηνία</dt><dd>{new Date(appointment.starts_at).toLocaleDateString("el-GR", { timeZone: "Europe/Athens", day: "2-digit", month: "2-digit", year: "numeric" })}</dd></div>
                                    <div><dt>Ώρα</dt><dd className="appointment-time">{new Date(appointment.starts_at).toLocaleTimeString("el-GR", { timeZone: "Europe/Athens", hour: "2-digit", minute: "2-digit" })}</dd></div>
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
                                <AppointmentDetails id={appointment.id} onUnauthorized={handleUnauthorized} />
                                {!appointment.cancelled_at &&
                                    new Date(appointment.starts_at).getTime() > Date.now() && (
                                        <RescheduleAppointment
                                            appointment={appointment}
                                            csrfToken={csrfToken}
                                            busy={updatingId !== null}
                                            onBusyChange={setUpdatingId}
                                            onUnauthorized={handleUnauthorized}
                                            onMoved={(id, day, slot) => {
                                                setNotice(
                                                    `Το ραντεβού #${id} μεταφέρθηκε στις ${day}, ` +
                                                    `${slot} ώρα Ελλάδας. Αν άλλαξε ημερομηνία, ` +
                                                    "επίλεξε τη νέα ημερομηνία στα φίλτρα."
                                                );
                                                setPage(1);
                                                setReloadKey(value => value + 1);
                                            }}
                                            onRefresh={() => {
                                                setNotice("");
                                                setReloadKey(value => value + 1);
                                            }}
                                        />
                                    )}
                            </article>
                        ))}
                        {!needsLogin && isLoading && (
                            <p role="status">Φόρτωση ραντεβού…</p>
                        )}

                        {!needsLogin && rangeError && (
                            <p role="status">{rangeError}</p>
                        )}

                        {!needsLogin && searchAmka && !/^[0-9]{11}$/.test(searchAmka) && (
                            <p role="status">Συμπλήρωσε ακριβώς 11 ψηφία ΑΜΚΑ.</p>
                        )}

                        {csrfToken && !needsLogin && !isLoading && !loadError &&
                            validFilters && appointments.length === 0 && (
                                <p className="admin-empty" role="status">
                                    Δεν βρέθηκαν ραντεβού με τα επιλεγμένα φίλτρα.
                                </p>
                            )}
                    </div>
                    {csrfToken && !needsLogin && validFilters && (
                        <nav className="admin-pagination" aria-label="Σελίδες ραντεβού">
                            <button type="button" disabled={isLoading || page === 1}
                                onClick={() => setPage(value => value - 1)}>Προηγούμενη σελίδα</button>
                            <span role="status">Σελίδα {page}</span>
                            <button type="button" disabled={isLoading || !hasMore || !!loadError}
                                onClick={() => setPage(value => value + 1)}>Επόμενη σελίδα</button>
                        </nav>
                    )}
                </section>
                {csrfToken && !needsLogin && (
                    <details className="admin-blocks-panel"><summary><span><strong>Μπλοκάρισμα ωρών</strong><span className="admin-blocks-hint">Διαχείριση άδειας ή μη διαθέσιμων διαστημάτων</span></span><span className="admin-expand-label">Άνοιγμα / κλείσιμο</span></summary><AvailabilityBlocks csrfToken={csrfToken} onUnauthorized={handleUnauthorized} /></details>
                )}
            </main>
        </div>
    );
}
