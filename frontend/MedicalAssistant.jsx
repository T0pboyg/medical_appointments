import React, { useEffect, useRef, useState } from "react";
import "./MedicalAssistant.css";

export default function MedicalAssistant() {
    const dialog = useRef(null);
    const launcher = useRef(null);
    const activeRequest = useRef(null);
    const messageList = useRef(null);
    const [open, setOpen] = useState(false);
    const [consent, setConsent] = useState(false);
    const [messages, setMessages] = useState([]);
    const [question, setQuestion] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        if (open && !dialog.current.open) dialog.current.showModal();
        if (!open && dialog.current.open) dialog.current.close();
    }, [open]);

    useEffect(() => () => activeRequest.current?.abort(), []);
    useEffect(() => {
        messageList.current?.scrollTo({ top: messageList.current.scrollHeight });
    }, [messages, busy]);

    function clear() {
        activeRequest.current?.abort();
        activeRequest.current = null;
        setMessages([]);
        setQuestion("");
        setError("");
        setBusy(false);
    }

    function close() {
        dialog.current?.close();
        clear();
        setConsent(false);
        setOpen(false);
        launcher.current?.focus();
    }

    function goToBooking(event) {
        const form = document.getElementById("appointment-form");
        if (!form) {
            close();
            return;
        }
        event.preventDefault();
        close();
        form.scrollIntoView({ behavior: "auto", block: "start" });
        form.querySelector("input:not([disabled])")?.focus({ preventScroll: true });
    }

    async function send(event) {
        event.preventDefault();
        const text = question.trim();
        if (!consent || busy || text.length < 3 || messages.length >= 12) return;
        const controller = new AbortController();
        activeRequest.current = controller;
        setBusy(true);
        setError("");
        setQuestion("");
        setMessages(previous => [...previous, { role: "user", text }]);
        const timeout = setTimeout(() => controller.abort(), 50000);
        try {
            const response = await fetch("/api/assistant/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                cache: "no-store",
                signal: controller.signal,
                body: JSON.stringify({ message: text, consent: true }),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(typeof data.detail === "string" ? data.detail : "Ελέγξτε το μήνυμα και δοκιμάστε ξανά.");
            }
            if (activeRequest.current === controller) {
                setMessages(previous => [...previous, {
                    role: "assistant", text: data.answer, sources: data.sources, actions: data.actions,
                    attribution: data.attribution,
                }]);
            }
        } catch (failure) {
            if (activeRequest.current === controller) {
                setError(failure.name === "AbortError"
                    ? "Η αναμονή έληξε. Δοκιμάστε αργότερα."
                    : failure.message || "Δεν ήταν δυνατή η επικοινωνία.");
            }
        } finally {
            clearTimeout(timeout);
            if (activeRequest.current === controller) {
                activeRequest.current = null;
                setBusy(false);
            }
        }
    }

    return <>
        <button className="medical-assistant-launcher" type="button" ref={launcher}
            aria-haspopup="dialog" aria-expanded={open} aria-controls="medical-assistant-dialog"
            onClick={() => setOpen(true)}>AI Assistant</button>
        <dialog id="medical-assistant-dialog" ref={dialog} className="medical-assistant-dialog"
            aria-labelledby="medical-assistant-title"
            onCancel={event => { event.preventDefault(); close(); }}>
            <header className="medical-assistant-heading">
                <h2 id="medical-assistant-title">AI Assistant — δοκιμαστική έκδοση</h2>
                <button type="button" onClick={close} aria-label="Κλείσιμο συνομιλίας">Κλείσιμο</button>
            </header>
            <p className="medical-assistant-notice">Οδηγίες κράτησης και γενική ενημέρωση για επίσκεψη, εξετάσεις και ορισμένα συχνά συμπτώματα σε ενήλικες: πυρετό, πονόλαιμο, πονοκέφαλο, βήχα, διάρροια και εμετό. Δεν παρέχει διάγνωση, εξατομικευμένη αξιολόγηση ή θεραπεία και δεν αναγνωρίζει κάθε επείγον. Σε άμεσο κίνδυνο καλέστε <a href="tel:112">112</a>· μην περιμένετε απάντηση εδώ.</p>
            <p className="medical-assistant-notice">Το κείμενο επεξεργάζεται στο τοπικό μοντέλο του υπολογιστή που φιλοξενεί την εφαρμογή. Δεν αποθηκεύουμε τη συνομιλία στη βάση ή στα logs. Παραμένει στη μνήμη της σελίδας μέχρι το κλείσιμο ή τον καθαρισμό. Μην γράφετε ονόματα, ΑΜΚΑ, τηλέφωνα ή προσωπικά αποτελέσματα εξετάσεων. Οι ελληνικές συνόψεις χρειάζονται κλινικό έλεγχο πριν από χρήση με ασθενείς.</p>
            {!consent ? <div className="medical-assistant-consent">
                <p>Θέλετε να συνεχίσετε με αυτούς τους περιορισμούς;</p>
                <button type="button" onClick={() => setConsent(true)}>Κατάλαβα — συνέχεια</button>
            </div> : <>
                <div ref={messageList} className="medical-assistant-messages" role="log" aria-live="polite" aria-relevant="additions" aria-label="Συνομιλία">
                    {messages.length === 0 && <p>Δοκιμάστε: «Πώς να προετοιμαστώ για εργαστηριακές εξετάσεις;» Κάθε ερώτηση εξετάζεται ανεξάρτητα.</p>}
                    {messages.map((message, index) => <article key={index} className={`medical-assistant-message ${message.role}`}>
                        <strong>{message.role === "user" ? "Εσείς" : "Assistant"}</strong>
                        <p>{message.text}</p>
                        {message.attribution && <p className="medical-assistant-attribution">
                            <small>{message.attribution} <a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/" target="_blank" rel="noopener noreferrer">Όροι άδειας OGL v3.0</a></small>
                        </p>}
                        {message.actions?.some(action => action.type === "booking_form") && (
                            <a className="medical-assistant-booking" href="/#appointment-form" onClick={goToBooking}>
                                Μετάβαση στην κράτηση
                            </a>
                        )}
                        {message.sources?.length > 0 && <ul aria-label="Πηγές">
                            {message.sources.map(source => <li key={source.id}>
                                <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a>
                                <small> — {source.organization}{source.checked_on ? ` · Έλεγχος: ${source.checked_on}` : ""}</small>
                            </li>)}
                        </ul>}
                    </article>)}
                    {busy && <p role="status">Αναζήτηση στις πηγές…</p>}
                </div>
                {error && <p role="alert" className="medical-assistant-error">{error}</p>}
                {messages.length >= 12 && <p>Το όριο αυτής της συνομιλίας συμπληρώθηκε. Καθαρίστε τη για να συνεχίσετε.</p>}
                <form onSubmit={send} className="medical-assistant-form">
                    <label htmlFor="medical-assistant-question">Η ερώτησή σας</label>
                    <textarea id="medical-assistant-question" value={question} minLength={3} maxLength={1200}
                        required disabled={busy || messages.length >= 12}
                        onChange={event => setQuestion(event.target.value)} rows={2} />
                    <div className="medical-assistant-actions">
                        <button type="submit" disabled={busy || question.trim().length < 3 || messages.length >= 12}>Αποστολή</button>
                        <button type="button" onClick={clear}>Καθαρισμός συνομιλίας</button>
                    </div>
                </form>
            </>}
        </dialog>
    </>;
}
