import React, { useEffect, useState } from "react";

export default function Admin() {
    const [appointments, setAppointments] = useState([]);
    const [loadError, setLoadError] = useState("");
    const [searchAmka, setSearchAmka] = useState("");
    const [updatingId, setUpdatingId] = useState(null);

    useEffect(() => {
        const controller = new AbortController();

        async function fetchAppointments() {
            try {
                const response = await fetch("/api/appointments", {
                    signal: controller.signal,
                });

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
    }, []);

    const filteredAppointments = appointments.filter(
        (appointment) =>
            searchAmka === "" || appointment.patient_AMKA === searchAmka
    );

    function getAppointmentStatus(appointment) {
        if (appointment.no_show) {
            return "Δεν προσήλθε";
        }

        const endsAt = new Date(appointment.starts_at).getTime() + 30 * 60 * 1000;

        return Date.now() >= endsAt ? "Ολοκληρωμένο" : "Προγραμματισμένο";
    }

    async function handleAttendanceChange(appointment) {
        if (updatingId !== null) {
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
                    },
                    body: JSON.stringify({
                        no_show: !appointment.no_show,
                    }),
                }
            );

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

    return (
        <div className="app-container">
            <header>
                <h1>Διαχείριση ιατρείου</h1>
            </header>

            <main>
                <section className="card">
                    <h2>Ραντεβού</h2>
                    <div className="form-group">
                        <label htmlFor="admin-search-amka">Αναζήτηση με AMKA</label>
                        <input
                            id="admin-search-amka"
                            type="text"
                            inputMode="numeric"
                            maxLength={11}
                            placeholder="AMKA 11 ψηφίων"
                            value={searchAmka}
                            onChange={(event) => setSearchAmka(event.target.value)}
                        />
                    </div>
                    {loadError && <p role="alert">{loadError}</p>}
                    <div className="table-wrapper">
                        <table>
                            <thead>
                                <tr>
                                    <th scope="col">Αριθμός</th>
                                    <th scope="col">Ασθενής</th>
                                    <th scope="col">Ημερομηνία και ώρα</th>
                                    <th scope="col">Κατάσταση</th>
                                    <th scope="col">Ενέργεια</th>
                                </tr>
                            </thead>

                            <tbody>
                                {filteredAppointments.map((appointment) => (
                                    <tr key={appointment.id}>
                                        <td>{appointment.id}</td>
                                        <td>{appointment.patient_name}</td>
                                        <td>
                                            {new Date(appointment.starts_at).toLocaleString("el-GR", {
                                                timeZone: "Europe/Athens",
                                                dateStyle: "short",
                                                timeStyle: "short",
                                            })}
                                        </td>
                                        <td>{getAppointmentStatus(appointment)}</td>
                                        <td>
                                            {Date.now() >=
                                                new Date(appointment.starts_at).getTime() + 30 * 60 * 1000 && (
                                                    <button
                                                        type="button"
                                                        disabled={updatingId !== null}
                                                        onClick={() => handleAttendanceChange(appointment)}
                                                    >
                                                        {updatingId === appointment.id
                                                            ? "Αποθήκευση…"
                                                            : appointment.no_show
                                                                ? "Επαναφορά σε ολοκληρωμένο"
                                                                : "Δεν προσήλθε"}
                                                    </button>
                                                )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
            </main>
        </div>
    );
}