"""Read-only, bounded calendar lookup. No LLM or booking writes."""
import re
from datetime import date, datetime, timedelta
from psycopg import Error as DatabaseError

from assistant_knowledge import normalize
from availability_service import CLINIC_TIMEZONE, get_available_slots


def booking_response(question, *, now=None):
    query = ' '.join(re.findall(r'[\w:/-]+', normalize(question)))
    words = query.split()
    if not any(word.startswith('ραντεβου') for word in words):
        return None
    if any(term in query for term in ('κοστι', 'κοστοσ', 'ωραριο', 'τηλεφων', 'διευθυνση')):
        return None
    if not (any(word.startswith(('κλεισ', 'κλειν', 'κανονισ', 'κρατησ', 'διαθεσιμ')) for word in words)
            or re.search(r'\bθελω\s+(?:ενα\s+)?ραντεβου\b', query)):
        return None
    response = {
        'status': 'booking_help', 'sources': [],
        'actions': [{'type': 'booking_form', 'label': 'Μετάβαση στην κράτηση', 'href': '/#appointment-form'}],
    }
    footer = ('Για να κλείσεις, επίλεξε ημερομηνία και ώρα στη φόρμα κράτησης και περίμενε την επιβεβαίωση. '
              'Δεν έχει δημιουργηθεί ραντεβού από αυτή τη συνομιλία. '
              'Συμπλήρωσε τα προσωπικά σου στοιχεία μόνο στη φόρμα, όχι εδώ.')
    now = (now or datetime.now(CLINIC_TIMEZONE)).astimezone(CLINIC_TIMEZONE)
    today = now.date()
    days = []
    next_week = bool(re.search(r'\bεπομενη\s+εβδομαδα\b', query))
    # A weekday, time or other qualifier needs a precise follow-up rather than
    # silently showing a different day/time from the user's request.
    qualified = bool(re.search(r'\b(?:δευτερ\w*|τριτη\w*|τεταρτ\w*|πεμπτ\w*|παρασκευ\w*|σαββατ\w*|κυριακ\w*)\b|\d', query))
    qualified = qualified or any(word.startswith(('πρωι', 'απογευ', 'μεσημερ', 'βραδ', 'μετα', 'πριν', 'μονο')) for word in words)
    relative_count = sum(term in words for term in ('σημερα', 'αυριο', 'μεθαυριο')) + int(next_week)
    qualified = qualified or relative_count > 1
    if next_week and not qualified:
        first = today + timedelta(days=7 - today.weekday())
        days = [first + timedelta(days=i) for i in range(7)]
    elif not qualified and not next_week:
        if 'μεθαυριο' in words:
            days = [today + timedelta(days=2)]
        elif 'αυριο' in words:
            days = [today + timedelta(days=1)]
        elif 'σημερα' in words:
            days = [today]
    if not days:
        response['answer'] = ('Φυσικά, μπορώ να σε βοηθήσω. Για να ελέγξω διαθέσιμες ώρες, '
                              'πες μου «σήμερα», «αύριο», «μεθαύριο» ή «την επόμενη εβδομάδα», '
                              'χωρίς επιπλέον περιορισμό ημέρας ή ώρας προς το παρόν. '
                              'Για συγκεκριμένη ημερομηνία και ώρα χρησιμοποίησε τη φόρμα. ' + footer)
        return response
    label = days[0].strftime('%d/%m/%Y')
    if len(days) > 1:
        label += ' – ' + days[-1].strftime('%d/%m/%Y')
    examples = []
    total = 0
    try:
        for day in days:
            slots = get_available_slots(day, now=now)
            total += len(slots)
            remaining = 6 - sum(len(item['times']) for item in examples)
            if slots and remaining > 0:
                examples.append({'date': day.isoformat(), 'times': slots[:min(2, remaining)]})
    except DatabaseError:
        # Never translate a failed read into a claim that the clinic is full.
        response.update(status='booking_unavailable', answer=(
            'Δεν μπόρεσα να ελέγξω το ημερολόγιο αυτή τη στιγμή. Δοκίμασε ξανά σε λίγο '
            'ή δες τη διαθεσιμότητα στη φόρμα κράτησης. ' + footer))
        return response
    if examples:
        lines = [f"{date.fromisoformat(item['date']).strftime('%d/%m/%Y')}: {', '.join(item['times'])}" for item in examples]
        text = (f'Φυσικά! Έλεγξα τη διαθεσιμότητα για {label} (ώρα Ελλάδας). '
                f'Βρήκα {total} διαθέσιμες ώρες. Μερικές επιλογές είναι:\n' + '\n'.join(lines)
                + '\n\nΟι ώρες δεν έχουν δεσμευτεί και μπορεί να αλλάξουν. ')
    else:
        text = f'Έλεγξα για {label} (ώρα Ελλάδας). Δεν βρήκα διαθέσιμες ώρες σε αυτό το διάστημα. '
    response.update(status='booking_availability', answer=text + footer, availability=examples)
    return response
