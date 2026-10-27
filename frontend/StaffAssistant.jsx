import React, { useEffect, useRef, useState } from "react";
import "./StaffAssistant.css";
import StaffAppointmentDetails from "./StaffAppointmentDetails.jsx";

export default function StaffAssistant({ csrfToken, onUnauthorized, onCancelled, onRescheduled, }) {
    const [open, setOpen] = useState(false);
    const [message, setMessage] = useState("");
    const [reply, setReply] = useState(null);
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
    const [selected, setSelected] = useState(null);
    const [detailsId, setDetailsId] = useState(null);
    const active = useRef(null);
    const input = useRef(null);
    const [moving, setMoving] = useState(false);
    useEffect(() => () => active.current?.abort(), []);
    useEffect(() => { if (open) input.current?.focus(); }, [open]);

    function close() {
        if (moving) return;
        active.current?.abort();
        active.current = null;
        setOpen(false);
        setMessage("");
        setReply(null);
        setSelected(null);
        setError("");
        setBusy(false);
        setDetailsId(null);
    }

    async function request(path, body) {
        if (busy || moving || active.current || !csrfToken) return;
        const controller = new AbortController();
        active.current = controller;
        setBusy(true);
        setError("");
        const timeout = setTimeout(() => controller.abort(), 50000);
        try {
            const response = await fetch(`/api/staff-assistant/${path}`, {
                method: "POST", cache: "no-store", signal: controller.signal,
                headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
                body: JSON.stringify(body),
            });
            if (active.current !== controller) return;
            if (onUnauthorized(response)) { close(); return; }
            const data = await response.json();
            if (active.current !== controller) return;
            if (!response.ok) {
                if (path === "confirm") { setSelected(null); setReply(null); }
                throw new Error(typeof data.detail === "string" ? data.detail : "Δεν μπόρεσα να ολοκληρώσω το αίτημα.");
            }
            setReply(data);
            setSelected(null);
            if (data.cancelled) onCancelled(data.cancelled);
        } catch (failure) {
            if (active.current === controller) {
                setError(failure.name === "AbortError"
                    ? "Η αναμονή έληξε. Αν επιβεβαίωσες ακύρωση, έλεγξε το ημερολόγιο πριν δοκιμάσεις ξανά."
                    : failure.message || "Δεν ήταν δυνατή η επικοινωνία.");
                // A failed/aborted confirmation may already have committed.
                if (path === "confirm") { setSelected(null); setReply(null); }
            }
        } finally {
            clearTimeout(timeout);
            if (active.current === controller) { active.current = null; setBusy(false); }
        }
    }

    function submit(event) {
        event.preventDefault();
        if (busy || moving) return;
        setDetailsId(null);
        if (message.trim().length < 3) return;
        setReply(null);
        setSelected(null);
        request("chat", { message: message.trim() });
    }

    const format = (value) => new Date(value).toLocaleString("el-GR", {
        timeZone: "Europe/Athens", dateStyle: "full", timeStyle: "short",
    });

    return <section className="card staff-assistant" aria-labelledby="staff-assistant-title">
        <div className="staff-assistant-heading">
            <h2 id="staff-assistant-title">Assistant προσωπικού</h2>
            <button type="button" disabled={moving || (busy && Boolean(selected))} aria-expanded={open} aria-controls="staff-assistant-panel"
                onClick={() => open ? close() : setOpen(true)}>{open ? "Κλείσιμο και καθαρισμός" : "Άνοιγμα Assistant"}</button>
        </div>
        {open && <div id="staff-assistant-panel">
            <p>Πες μου τι χρειάζεσαι: ραντεβού ημέρας ή εβδομάδας, ελεύθερες ώρες ή ακύρωση συγκεκριμένου ραντεβού. Θα ζητήσω επιβεβαίωση πριν αλλάξει κάτι.</p>
            <p className="staff-assistant-hint">Παραδείγματα: «Δείξε όλα τα ραντεβού της επόμενης εβδομάδας», «Ποιες ώρες είναι ελεύθερες την Τρίτη της επόμενης εβδομάδας;», «Ακύρωσε το ραντεβού #42». Υπολογίζω τις ημερομηνίες με ώρα Ελλάδας και εμφανίζω το ακριβές διάστημα. Μην γράφεις ΑΜΚΑ, τηλέφωνα ή ιατρικό ιστορικό.</p>
            <form onSubmit={submit}>
                <label htmlFor="staff-assistant-message">Η εντολή σου</label>
                <textarea id="staff-assistant-message" ref={input} value={message} maxLength={600}
                    onChange={event => setMessage(event.target.value)} disabled={busy || moving} required minLength={3} rows={3} />
                <button type="submit" disabled={busy || moving || !csrfToken || message.trim().length < 3}>{busy ? "Έλεγχος…" : "Αποστολή"}</button>
            </form>
            {error && <p role="alert">{error}</p>}
            <div aria-live="polite" aria-busy={busy || moving}>
                {reply && <p className="staff-assistant-answer">{reply.answer}</p>}
                {reply?.appointments?.map(appointment => <article className="staff-assistant-result" key={appointment.id}>
                    <strong>#{appointment.id} — {appointment.patient_name}</strong>
                    <p>{format(appointment.starts_at)}</p>
                    <button
                        type="button"
                        disabled={busy || moving}
                        onClick={() => setDetailsId(appointment.id)}
                    >
                        Προβολή ραντεβού
                    </button>
                    {appointment.confirmation_token && <button type="button" disabled={busy || moving}
                        onClick={() => setSelected(appointment)}>Επιλογή για ακύρωση</button>}
                </article>)}
            </div>
            {selected && <div className="staff-assistant-confirm" role="group" aria-label="Επιβεβαίωση ακύρωσης">
                <h3>Να ακυρωθεί αυτό το ραντεβού;</h3>
                <p><strong>#{selected.id} — {selected.patient_name}</strong><br />{format(selected.starts_at)}</p>
                <p>Η ώρα θα ελευθερωθεί. Η ενέργεια καταγράφεται με τον λογαριασμό σου.</p>
                {busy && <p role="status">Η ακύρωση εκτελείται. Περίμενε το αποτέλεσμα πριν κλείσεις το πλαίσιο.</p>}
                <button type="button" disabled={busy || moving} onClick={() => request("confirm", { token: selected.confirmation_token })}>Επιβεβαίωση ακύρωσης</button>
                <button type="button" disabled={busy || moving} onClick={() => setSelected(null)}>Όχι, επιστροφή</button>
            </div>}
        </div>}
        {open && detailsId !== null && (
            <StaffAppointmentDetails
                key={detailsId}
                appointmentId={detailsId}
                csrfToken={csrfToken}
                onUnauthorized={onUnauthorized}
                onMovingChange={setMoving}
                onClose={() => setDetailsId(null)}
                onMoved={(id, day, slot) => {
                    setDetailsId(null);
                    setSelected(null);
                    setMessage("");
                    setError("");
                    setReply({
                        answer: `Το ραντεβού #${id} μεταφέρθηκε στις ${day}, ${slot} ώρα Ελλάδας. ` +
                            "Κάνε νέα αναζήτηση για ενημερωμένα αποτελέσματα.",
                        appointments: [],
                    });
                    onRescheduled();
                }}
                onRefresh={() => {
                    setDetailsId(null);
                    setSelected(null);
                    setMessage("");
                    setError("");
                    setReply({
                        answer: "Η λίστα και το ημερολόγιο ανανεώνονται. " +
                            "Κάνε νέα αναζήτηση για να ελέγξεις την τωρινή ώρα του ραντεβού.",
                        appointments: [],
                    });
                    onRescheduled();
                }}
            />
        )}
    </section>;
}
