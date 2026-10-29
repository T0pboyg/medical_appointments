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
        <button className="medical-assistant-launcher chat-launcher" type="button" ref={launcher}
            aria-haspopup="dialog" aria-expanded={open} aria-controls="medical-assistant-dialog"
            onClick={() => setOpen(true)} aria-label="AI Assistant">
            <span className="chat-launcher-icon" aria-hidden="true">✦</span>
            <span className="assistant-label-desktop" aria-hidden="true">Βοηθός ιατρείου</span>
            <span className="assistant-label-mobile" aria-hidden="true">Βοηθός</span>
        </button>
        <dialog id="medical-assistant-dialog" ref={dialog} className="medical-assistant-dialog chat-panel"
            aria-labelledby="medical-assistant-title" onCancel={event => {event.preventDefault();close();}}>
            <header className="chat-header">
                <div className="chat-avatar" aria-hidden="true">✦</div>
                <div className="chat-header-text"><h2 id="medical-assistant-title">Βοηθός ιατρείου</h2><p>AI βοηθός · Δοκιμαστική έκδοση</p></div>
                <button type="button" className="chat-icon-button" onClick={close} aria-label="Κλείσιμο συνομιλίας">×</button>
            </header>
            <div className="chat-notice">
                Γενική ενημέρωση, όχι διάγνωση. Μην γράφεις προσωπικά στοιχεία. Σε άμεσο κίνδυνο κάλεσε <a href="tel:112">112</a>.
                <details open={!consent}><summary>Πληροφορίες χρήσης και απορρήτου</summary>
                    <p>Μπορώ να σε βοηθήσω με διαθέσιμες ώρες ραντεβού, προετοιμασία για τον γιατρό, εξετάσεις, συνήθειες ύπνου και γενικές πληροφορίες για ορισμένα συχνά συμπτώματα σε ενήλικες. Δεν παρέχω διάγνωση, προσωπική αξιολόγηση ή θεραπεία και δεν αναγνωρίζω κάθε επείγον. Σε άμεσο κίνδυνο κάλεσε <a href="tel:112">112</a>· μην περιμένεις απάντηση εδώ.</p>
<p>Το κείμενο επεξεργάζεται στο τοπικό μοντέλο του υπολογιστή που φιλοξενεί την εφαρμογή. Δεν αποθηκεύουμε τη συνομιλία στη βάση ή στα logs. Παραμένει στη μνήμη της σελίδας μέχρι το κλείσιμο ή τον καθαρισμό. Μην γράφετε ονόματα, ΑΜΚΑ, τηλέφωνα ή προσωπικά αποτελέσματα εξετάσεων. Οι ελληνικές συνόψεις χρειάζονται κλινικό έλεγχο πριν από χρήση με ασθενείς.</p>
                </details>
            </div>
            <div ref={messageList} className="chat-messages" role="log" aria-live="polite" aria-relevant="additions" aria-label="Συνομιλία">
                <article className="chat-message assistant"><span className="chat-author">Βοηθός ιατρείου</span><div className="chat-bubble"><p>Γεια σου! 👋<br/>Μπορώ να σε βοηθήσω με διαθέσιμες ώρες, προετοιμασία επίσκεψης και γενικές πληροφορίες.</p><p>Τι θα ήθελες να δούμε;</p></div></article>
                {!consent && <div className="chat-consent"><p>Διάβασε τις πληροφορίες χρήσης πριν ξεκινήσεις. Θέλεις να συνεχίσεις με αυτούς τους περιορισμούς;</p><button type="button" onClick={() => setConsent(true)}>Κατάλαβα — συνέχεια</button></div>}
                {consent && messages.length === 0 && <div className="chat-suggestions">{[
                    ["Διαθέσιμες ώρες", "Ποιες ώρες είναι διαθέσιμες για ραντεβού;"],
                    ["Θέλω ραντεβού", "Πώς μπορώ να κλείσω ραντεβού;"],
                    ["Προετοιμασία επίσκεψης", "Πώς να προετοιμαστώ για την επίσκεψή μου;"],
                ].map(([label, text]) => <button key={label} type="button" disabled={busy} onClick={() => {setQuestion(text);document.getElementById("medical-assistant-question")?.focus();}}>{label}<span aria-hidden="true">↗</span></button>)}</div>}
                {messages.map((message, index) => <article key={index} className={`chat-message ${message.role}`}>
                    <span className="chat-author">{message.role === "user" ? "Εσύ" : "Βοηθός ιατρείου"}</span>
                    <div className="chat-bubble"><p>{message.text}</p>
                                            {message.attribution && <p className="medical-assistant-attribution">
                            <small>{message.attribution} <a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/" target="_blank" rel="noopener noreferrer">Όροι άδειας OGL v3.0</a></small>
                        </p>}
                        {message.actions?.some(action => action.type === "booking_form") && (
                            <a className="chat-booking-link" href="/#appointment-form" onClick={goToBooking}>
                                Μετάβαση στην κράτηση
                            </a>
                        )}
                        {message.sources?.length > 0 && <ul aria-label="Πηγές">
                            {message.sources.map(source => <li key={source.id}>
                                <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a>
                                <small> — {source.organization}{source.checked_on ? ` · Έλεγχος: ${source.checked_on}` : ""}</small>
                            </li>)}
                        </ul>}

                    </div>
                </article>)}
                {busy && <div className="chat-thinking" role="status"><span aria-hidden="true"/><span aria-hidden="true"/><span aria-hidden="true"/> Ελέγχω τις διαθέσιμες πληροφορίες…</div>}
            </div>
            <footer className="chat-footer">
                {error && <p role="alert" className="medical-assistant-error chat-error">{error}</p>}
                {messages.length >= 12 && <p className="chat-limit">Το όριο συμπληρώθηκε. Ξεκίνα νέα συνομιλία για να συνεχίσεις.</p>}
                <form onSubmit={send} className="medical-assistant-form chat-composer">
                    <label className="chat-sr-only" htmlFor="medical-assistant-question">Η ερώτησή σας</label>
                    <textarea id="medical-assistant-question" value={question} rows={1} minLength={3} maxLength={1200}
                        required placeholder="Γράψε το μήνυμά σου…" disabled={!consent || busy || messages.length >= 12}
                        onChange={event => setQuestion(event.target.value)}
                        onKeyDown={event => {if(event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing){event.preventDefault();send(event);}}} />
                    <button type="submit" aria-label="Αποστολή" disabled={!consent || busy || question.trim().length < 3 || messages.length >= 12}>↑</button>
                </form>
                <div className="chat-footer-meta"><span>Κάθε ερώτηση εξετάζεται ανεξάρτητα</span><button type="button" disabled={!consent} onClick={clear}>Νέα συνομιλία</button></div>
            </footer>
        </dialog>
    </>;
}
