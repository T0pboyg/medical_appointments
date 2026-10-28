import React, { useEffect, useRef, useState } from "react";
import BookingCalendar from "./BookingCalendar.jsx";
import { clinicSlotToIso, getClinicDate } from "./appointmentFilters.js";

export default function CreateAppointment({ csrfToken, onUnauthorized, onCreated, onClose, onRefresh }) {
    const dialog = useRef(null);
    const sending = useRef(false);
    const [day, setDay] = useState(getClinicDate);
    const [slots, setSlots] = useState([]);
    const [slot, setSlot] = useState("");
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const [loadError, setLoadError] = useState("");
    const [retry, setRetry] = useState(0);
    const [uncertain, setUncertain] = useState(false);
    const [name, setName] = useState("");
    const [phone, setPhone] = useState("");
    const [amka, setAmka] = useState("");
    useEffect(() => {
        const previous = document.activeElement;
        dialog.current.showModal();
        return () => previous?.focus();
    }, []);
    useEffect(() => {
        const controller = new AbortController();
        setLoading(true); setLoadError(""); setSlots([]); setSlot("");
        async function load() {
            try {
                const response = await fetch(`/api/availability?date=${encodeURIComponent(day)}`, { signal: controller.signal, cache: "no-store" });
                if (!response.ok) throw new Error();
                const times = await response.json();
                if (!controller.signal.aborted) setSlots(times);
            } catch {
                if (!controller.signal.aborted) setLoadError("Δεν φορτώθηκαν οι ώρες. Δοκίμασε ξανά.");
            } finally { if (!controller.signal.aborted) setLoading(false); }
        }
        load();
        return () => controller.abort();
    }, [day, retry]);
    function close() { if (!sending.current) onClose(); }
    async function submit(event) {
        event.preventDefault();
        if (sending.current || loading || uncertain || !slots.includes(slot) || !csrfToken) return;
        let startsAt;
        try { startsAt = clinicSlotToIso(day, slot); }
        catch { setError("Επίλεξε έγκυρη ημέρα και ώρα."); return; }
        sending.current = true; setBusy(true); setError("");
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 20000);
        try {
            const response = await fetch("/api/staff/appointments", {
                method: "POST", signal: controller.signal, cache: "no-store",
                headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
                body: JSON.stringify({ patient_name: name.trim(), patient_phone: phone, patient_AMKA: amka, starts_at: startsAt }),
            });
            if (onUnauthorized(response)) return;
            if (response.status === 409) {
                setError("Η ώρα δεν είναι πλέον διαθέσιμη. Επίλεξε άλλη ώρα.");
                setRetry(value => value + 1); return;
            }
            if (!response.ok) {
                if (response.status >= 500) throw new Error();
                const data = await response.json();
                setError(typeof data.detail === "string" ? data.detail : "Έλεγξε όνομα, ελληνικό τηλέφωνο και ΑΜΚΑ 11 ψηφίων.");
                return;
            }
            const created = await response.json();
            onCreated(created, day);
        } catch {
            setError("Δεν επιβεβαιώθηκε αν αποθηκεύτηκε. Κλείσε και έλεγξε τη λίστα πριν επιχειρήσεις νέα καταχώριση.");
            setUncertain(true);
        } finally { clearTimeout(timeout); sending.current = false; setBusy(false); }
    }
    return <dialog ref={dialog} className="admin-create-dialog" aria-labelledby="new-appointment-title" onCancel={event => {event.preventDefault();close();}}>
        <div className="admin-create-heading"><div><h2 id="new-appointment-title">Νέο ραντεβού</h2><p>Καταχώριση από το προσωπικό · Ώρα Ελλάδας</p></div><button type="button" disabled={busy} onClick={close} aria-label="Κλείσιμο νέου ραντεβού">Κλείσιμο</button></div>
        <form onSubmit={submit}>
            <fieldset disabled={busy || uncertain}>
                <legend>Στοιχεία ασθενούς και επίσκεψης</legend>
                <div className="form-group"><label htmlFor="staff-create-name">Ονοματεπώνυμο</label><input autoFocus id="staff-create-name" value={name} onChange={event => setName(event.target.value)} required maxLength={100} autoComplete="off" /></div>
                <div className="form-group"><label htmlFor="staff-create-phone">Τηλέφωνο</label><input id="staff-create-phone" type="tel" value={phone} onChange={event => setPhone(event.target.value)} required maxLength={30} autoComplete="off" placeholder="π.χ. 6912345678" /></div>
                <div className="form-group"><label htmlFor="staff-create-amka">ΑΜΚΑ</label><input id="staff-create-amka" value={amka} onChange={event => setAmka(event.target.value)} required inputMode="numeric" pattern="[0-9]{11}" maxLength={11} autoComplete="off" /></div>
                <BookingCalendar selectedDate={day} onSelectDate={setDay} disabled={busy} label="Ημερομηνία νέου ραντεβού" />
                {loading && <p role="status">Φόρτωση ωρών…</p>}
                {loadError && <div role="alert"><p>{loadError}</p><button type="button" onClick={() => setRetry(value => value + 1)}>Επανάληψη φόρτωσης ωρών</button></div>}
                {!loading && !loadError && <div className="form-group"><label htmlFor="staff-create-slot">Διαθέσιμη ώρα</label><select id="staff-create-slot" required value={slot} onChange={event => setSlot(event.target.value)}><option value="">Επίλεξε ώρα</option>{slots.map(time => <option key={time} value={time}>{time}</option>)}</select>{slots.length === 0 && <p>Δεν υπάρχουν διαθέσιμες ώρες. Επίλεξε άλλη ημέρα.</p>}</div>}
            </fieldset>
            {error && <p role="alert">{error}</p>}
            <div className="admin-create-actions">
                {uncertain ? <button type="button" onClick={() => {onRefresh(day);onClose();}}>Κλείσιμο και έλεγχος λίστας</button> : <button type="submit" disabled={busy || loading || !!loadError || !slot || !csrfToken}>{busy ? "Καταχώριση…" : "Καταχώριση ραντεβού"}</button>}
                <button type="button" disabled={busy} onClick={close}>Άκυρο</button>
            </div>
        </form>
    </dialog>;
}
