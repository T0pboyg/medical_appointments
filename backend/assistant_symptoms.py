"""Bounded adult symptom education, not clinical triage or a diagnosis engine."""
import json
import re
from pathlib import Path

from assistant_knowledge import normalize


def symptom_information(question):
    query = ' '.join(re.findall(r'\w+', normalize(question)))
    words = query.split()
    throat_or_fever = any(word.startswith(('πυρετ', 'πονολαιμ')) for word in words)
    throat_or_fever = throat_or_fever or bool(re.search(r'πονο\w*\s+(?:στον?\s+)?λαιμο', query))
    headache = any(word.startswith('πονοκεφαλ') for word in words) or bool(re.search(r'πον\w*\s+(?:στο\s+)?κεφαλι', query))
    cough = any(word.startswith(('βηχ', 'βηξ')) for word in words)
    gastrointestinal = any(word.startswith(('διαρρο', 'εμετ', 'εμεσ')) for word in words)
    supported = throat_or_fever or headache or cough or gastrointestinal
    red_flags = (
        'δυσκολια στην αναπνοη', 'δυσκολευομαι να αναπνευσω',
        'δεν μπορω να καταπιω', 'δεν μπορει να καταπιει',
        'δεν μπορω να αναπνευσω', 'δεν μπορει να αναπνευσει',
        'δεν καταπινω', 'τρεχουν σαλια',
    )
    urgent = any(phrase in query for phrase in red_flags)
    if headache:
        sudden = any(word.startswith('ξαφν') for word in words)
        severe = any(word.startswith(('δυνατ', 'εντον', 'χειροτερ', 'εξαιρετικ')) for word in words)
        neurological = any(phrase in query for phrase in (
            'δυσκολια στην ομιλια', 'δεν μπορω να μιλησω', 'απωλεια ορασησ',
            'δυσκαμψια αυχενα', 'δυσκαμψια στον αυχενα',
        )) or any(word.startswith(('συγχυσ', 'σπασμ', 'μουδιασ', 'τραυματισ')) for word in words)
        urgent = urgent or (sudden and severe) or neurological
    if gastrointestinal:
        blood_vomit = any(word.startswith(('εμετ', 'εμεσ')) for word in words) and 'αιμα' in words
        green_vomit = any(word.startswith('πρασιν') for word in words) and any(word.startswith(('εμετ', 'εμεσ')) for word in words)
        severe_belly = 'κοιλια' in words and any(word.startswith('ξαφν') for word in words) and any(word.startswith(('εντον', 'δυνατ')) for word in words)
        urgent = urgent or blood_vomit or green_vomit or severe_belly or any(word.startswith(('δηλητηρ', 'συγχυσ')) for word in words)
    if not supported and not urgent:
        return None

    path = Path(__file__).parent / 'knowledge' / 'symptom_information.json'
    information = json.loads(path.read_text(encoding='utf-8'))
    profiles = json.loads((path.parent / 'common_symptom_information.json').read_text(encoding='utf-8'))
    selected = [profile for profile in profiles if (
        (profile['id'] == 'headache' and headache)
        or (profile['id'] == 'cough' and cough)
        or (profile['id'] == 'gastrointestinal' and gastrointestinal)
    )]
    sources = information['sources'] if throat_or_fever or not selected else []
    sources = sources + [profile['source'] for profile in selected]
    emergencies = ([information['emergency']] if throat_or_fever or not selected else []) + [p['emergency'] for p in selected]
    emergency_text = '\n\n'.join(emergencies)
    answer = {
        'status': 'symptom_information', 'sources': sources,
        'attribution': information['attribution'],
    }
    # Negation is deliberately not interpreted as an "all clear". This may
    # over-escalate; a rule list is not a validated emergency detector.
    if urgent:
        answer.update(status='urgent', answer=emergency_text + '\n\n' + information['scope'])
        return answer

    age = re.search(r'\b(\d{1,3})\s+(?:ετων|χρονων)\b', query)
    child_age = age is not None and int(age.group(1)) < 18
    special = child_age or any(word.startswith((
        'παιδ', 'μωρ', 'βρεφ', 'ανηλικ', 'εγκυ', 'κυησ', 'ανοσοκαταστ', 'χημειοθεραπ',
    )) for word in words)
    if special:
        answer.update(status='symptom_scope', answer=information['special_scope'] + '\n\n' + emergency_text)
        return answer

    paragraphs = [information['scope'], emergency_text]
    if throat_or_fever:
        paragraphs.extend((information['contact'], information['self_care']))
    for profile in selected:
        paragraphs.extend((profile['contact'], profile['self_care']))
    if selected:
        paragraphs.append('Δεν μπορώ να επιλέξω φάρμακο ή δοσολογία για εσάς. Για προσωπική θεραπεία ζητήστε οδηγίες γιατρού ή φαρμακοποιού.')
    answer['answer'] = '\n\n'.join(paragraphs)
    return answer
