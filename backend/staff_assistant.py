"""Staff-only assistant: scoped reads and signed, explicit cancellation previews."""
import base64
import hashlib
import hmac
import json
import os
import re
import threading
import time
from datetime import datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints
from psycopg import Error as DatabaseError
from starlette.concurrency import run_in_threadpool

from assistant_knowledge import normalize
from assistant_service import AssistantBusy, AssistantUnavailable
from auth import require_staff_change
from availability_service import CLINIC_TIMEZONE, get_available_slots
from database import find_staff_appointments, cancel_appointment_in_db
from staff_assistant_intent import extract_intent, resolve_day

router = APIRouter(prefix='/staff-assistant', tags=['staff-assistant'])
_attempts = {}
_rate_lock = threading.Lock()


class StaffMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=600)]


class Confirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    token: Annotated[str, StringConstraints(min_length=10, max_length=2048)]


def preview_key(session):
    binding = json.dumps([session['issuer'], session['subject'], session['csrf_token']], ensure_ascii=False).encode()
    return hmac.digest(os.environ['API_PROXY_SECRET'].encode(), b'staff-assistant-preview-v1:' + binding, 'sha256')


def make_preview(appointment, session, *, timestamp=None):
    payload = {'id': appointment['id'], 'starts_at': appointment['starts_at'].isoformat(),
               'patient_name': appointment['patient_name'], 'expires': int(time.time() if timestamp is None else timestamp) + 300}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()).decode()
    return encoded + '.' + hmac.new(preview_key(session), encoded.encode(), hashlib.sha256).hexdigest()


def read_preview(token, session, *, timestamp=None):
    try:
        encoded, signature = token.split('.')
        expected = hmac.new(preview_key(session), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError('Invalid signature')
        payload = json.loads(base64.urlsafe_b64decode(encoded))
        now = time.time() if timestamp is None else timestamp
        if not now < payload['expires'] <= now + 300:
            raise ValueError('Expired preview')
        if type(payload['id']) is not int or payload['id'] < 1 or not isinstance(payload['patient_name'], str):
            raise ValueError('Invalid target')
        if datetime.fromisoformat(payload['starts_at']).tzinfo is None:
            raise ValueError('Missing timezone')
        return payload
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise HTTPException(409, 'Η προεπισκόπηση έληξε ή δεν είναι έγκυρη. Ζήτησε ξανά το ραντεβού.') from None


def prepare_response(message, intent, session, *, now=None):
    query = normalize(message)
    action = intent['action']
    help_text = ('Μπορώ να δείξω ραντεβού ή ελεύθερες ώρες μιας ημέρας και να ετοιμάσω ακύρωση ενός ραντεβού. '
                 'Δοκίμασε «Δείξε τα ραντεβού αύριο» ή «Ακύρωσε το ραντεβού στις 07/01/2030 του ΟΝΟΜΑ». '
                 'Κάθε ακύρωση χρειάζεται ξεχωριστή επιβεβαίωση.')
    reply = lambda text: {'answer': text, 'appointments': []}
    bulk = any(word.startswith(('ολα', 'ολεσ', 'ολουσ', 'μαζικ')) for word in re.findall(r'\w+', query))
    if action not in ('list', 'availability', 'cancel') or (action == 'cancel' and bulk):
        return reply(help_text)
    without_dates = re.sub(r'\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b', '', query)
    if (re.search(r'\b\d{1,2}:\d{2}\b|\b(?:πρωι|απογευ|μεσημερ|βραδ|πριν|μετα)\w*\b', without_dates)
            or re.search(r'\b(?:στις|ωρα)\s+(?:\d+|δεκα|εντεκα|δωδεκα|εννια|εννεα|μια|δυο|τρεισ|τεσσερισ|πεντε|εξι|επτα|οκτω)\b', without_dates)):
        return reply('Δεν υποστηρίζω ακόμη περιορισμούς ώρας σε εντολές. Ζήτησε όλη την ημέρα και διάλεξε το σωστό ραντεβού από την ακριβή ημερομηνία/ώρα που εμφανίζεται, ή χρησιμοποίησε #ID χωρίς επιπλέον περιορισμό ώρας.')
    name = intent.get('patient_name')
    appointment_id = intent.get('appointment_id')
    if name and normalize(name) not in query:
        return reply('Δεν μπόρεσα να αναγνωρίσω με βεβαιότητα το όνομα. Γράψε την ημερομηνία και το όνομα όπως εμφανίζεται στο admin.')
    if appointment_id and not re.search(rf'(?:#\s*|ραντεβου\s+){appointment_id}\b', query):
        return reply('Χρειάζομαι σαφή αριθμό ραντεβού, όπως #42, ή πλήρη ημερομηνία και όνομα.')
    day = resolve_day(message, now=now)
    date_hint = bool(re.search(r'\d[/\-]\d|\b(?:σημερα|αυριο|μεθαυριο|χθεσ|δευτερ\w*|τριτη\w*|τεταρτ\w*|πεμπτ\w*|παρασκευ\w*|σαββατ\w*|κυριακ\w*|εβδομαδ\w*)\b', query))
    without_id = re.sub(rf'(?:#\s*|ραντεβου\s+){appointment_id}\b', '', query) if appointment_id else query
    date_hint = date_hint or bool(re.search(r'\d', without_id)) or any(term in query for term in (
        'ιανουαρ', 'φεβρουαρ', 'μαρτι', 'απριλ', 'μαιου', 'ιουνι', 'ιουλι', 'αυγουστ', 'σεπτεμβρ', 'οκτωβρ', 'νοεμβρ', 'δεκεμβρ', 'ημερεσ', 'μερεσ',
    ))
    if day is None and not (action == 'cancel' and appointment_id and not date_hint):
        return reply('Ποια ακριβώς ημέρα εννοείς; Γράψε πλήρη ημερομηνία π.χ. 07/01/2030, «αύριο» ή μία συγκεκριμένη ημέρα της εβδομάδας. Δεν έγινε καμία αλλαγή.')
    if action == 'cancel' and (not any(word.startswith('ακυρ') for word in query.split()) or not (name or appointment_id)):
        return reply('Για ακύρωση χρειάζομαι συγκεκριμένο όνομα και ημέρα ή αριθμό ραντεβού (#ID). Δεν κάνω μαζικές ακυρώσεις.')
    if action == 'availability':
        slots = get_available_slots(day, now=now)
        text = ', '.join(slots) if slots else 'Δεν υπάρχουν διαθέσιμες ώρες.'
        return reply(f'Ελεύθερες ώρες για {day.strftime("%d/%m/%Y")} (ώρα Ελλάδας): {text} Δεν έχουν δεσμευτεί.')
    rows = find_staff_appointments(day=day, appointment_id=appointment_id, future_only=action == 'cancel')
    if len(rows) > 200:
        return reply('Η αναζήτηση ξεπερνά το όριο αποτελεσμάτων. Χρησιμοποίησε συγκεκριμένο αριθμό ραντεβού (#ID).')
    if name:
        rows = [row for row in rows if normalize(name) in normalize(row['patient_name'])]
    if len(rows) > 20:
        return reply('Βρέθηκαν πολλά ραντεβού. Δώσε πιο συγκεκριμένο όνομα ή αριθμό ραντεβού για να περιορίσουμε την αναζήτηση.')
    records = [{'id': row['id'], 'patient_name': row['patient_name'], 'starts_at': row['starts_at'].isoformat(),
                **({'confirmation_token': make_preview(row, session)} if action == 'cancel' else {})} for row in rows]
    label = day.strftime('%d/%m/%Y') if day else f'#{appointment_id}'
    if not rows:
        return reply(f'Δεν βρήκα ενεργό ραντεβού για {label} με αυτά τα στοιχεία. Δοκίμασε το όνομα όπως είναι καταχωρισμένο ή τον αριθμό ραντεβού.')
    return {'answer': f'Βρήκα {len(rows)} ραντεβού για {label} (ώρα Ελλάδας). ' + (
        'Έλεγξε όνομα, ημερομηνία και ώρα και επίλεξε το σωστό για ακύρωση. Δεν έχει γίνει καμία αλλαγή.'
        if action == 'cancel' else 'Αυτά είναι τα ενεργά ραντεβού της αναζήτησης.'), 'appointments': records}


@router.post('/chat')
async def chat(body: StaffMessage, session: dict = Depends(require_staff_change)):
    key = hashlib.sha256(session['csrf_token'].encode()).hexdigest()
    now = time.monotonic()
    with _rate_lock:
        for old in [key for key, (start, _) in _attempts.items() if now - start >= 60]:
            del _attempts[old]
        start, count = _attempts.get(key, (now, 0))
        if count >= 6 or (key not in _attempts and len(_attempts) >= 1024):
            raise HTTPException(429, 'Πολλά αιτήματα. Δοκίμασε σε ένα λεπτό.', headers={'Retry-After': '60', 'Cache-Control': 'no-store'})
        _attempts[key] = (start, count + 1)
    try:
        intent = await extract_intent(body.message)
        answer = await run_in_threadpool(prepare_response, body.message, intent, session)
    except AssistantBusy:
        raise HTTPException(429, 'Το τοπικό μοντέλο είναι απασχολημένο. Δοκίμασε σε λίγο.', headers={'Cache-Control': 'no-store'}) from None
    except (AssistantUnavailable, DatabaseError):
        raise HTTPException(503, 'Δεν μπόρεσα να ελέγξω την εντολή ή το ημερολόγιο. Δεν έγινε αλλαγή.', headers={'Cache-Control': 'no-store'}) from None
    return JSONResponse(answer, headers={'Cache-Control': 'no-store'})


@router.post('/confirm')
def confirm(body: Confirmation, session: dict = Depends(require_staff_change)):
    target = read_preview(body.token, session)
    try:
        cancelled = cancel_appointment_in_db(
            target['id'], session['issuer'], session['subject'], uuid4(),
            expected_starts_at=datetime.fromisoformat(target['starts_at']), expected_patient_name=target['patient_name'],
        )
    except DatabaseError:
        raise HTTPException(503, 'Η ακύρωση δεν ολοκληρώθηκε. Έλεγξε το ημερολόγιο πριν δοκιμάσεις ξανά.', headers={'Cache-Control': 'no-store'}) from None
    if cancelled is None:
        raise HTTPException(409, 'Το ραντεβού άλλαξε, έχει ήδη ακυρωθεί ή δεν είναι πια μελλοντικό. Κάνε νέα αναζήτηση.', headers={'Cache-Control': 'no-store'})
    return JSONResponse({'answer': f"Το ραντεβού #{cancelled['id']} ακυρώθηκε και η ώρα ελευθερώθηκε.",
                         'cancelled': {'id': cancelled['id'], 'cancelled_at': cancelled['cancelled_at'].isoformat()}}, headers={'Cache-Control': 'no-store'})
