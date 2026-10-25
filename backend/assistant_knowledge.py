"""Small, versioned, local allowlist. Never fetch URLs supplied by a user."""
import json
import re
import unicodedata
from pathlib import Path


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if unicodedata.category(c) != 'Mn')


def _has_prefix(words, *prefixes):
    """Match only the start of a word; no fuzzy medical spelling correction."""
    return any(word.startswith(prefixes) for word in words)


def _topic_scores(query):
    words = query.split()
    visit = _has_prefix(words, 'επισκεψ', 'ραντεβου', 'γιατρ')
    lab = _has_prefix(words, 'εξετασ', 'αιμα', 'αιμοληψ', 'εργαστηρ')
    preparation = _has_prefix(words, 'προετοιμα', 'ετοιμα', 'φερ', 'φερω')
    discussion = _has_prefix(words, 'συζητ', 'ρωτησ', 'καταγραψ', 'αναφερ', 'ενημερωσ')
    medication = _has_prefix(words, 'φαρμακ', 'βιταμιν', 'συμπληρωμ')
    bringing = bool(re.search(r'\b(?:παρω|παρετε|παιρνω)\s+μαζι\b', query))
    fasting = _has_prefix(words, 'νηστ', 'φαω', 'φαγητ', 'νερο')
    meaning = _has_prefix(words, 'σημαιν', 'ερμην', 'καταλαβ', 'κατανο')
    results = _has_prefix(words, 'αποτελεσμ')
    reference_range = bool(re.search(r'\bτιμ\w*\s+αναφορ\w*\b', query))
    normal_range = bool(re.search(r'\bφυσιολογικ\w*\s+(?:ευροσ|ορι\w*|τιμ\w*)\b', query))

    scores = {}
    describing = _has_prefix(words, 'εξηγησ', 'περιγραψ', 'περιγραφ')
    recording = _has_prefix(words, 'σημειωσ', 'γραψ')
    if visit and (describing or recording):
        scores['visit-communication'] = 18
    if _has_prefix(words, 'υπνο', 'αυπν', 'κοιμα', 'κοιμηθ') or (
        _has_prefix(words, 'ξυπνα') and _has_prefix(words, 'νυχτ', 'βραδ')
    ):
        scores['healthy-sleep'] = 16
    if _has_prefix(words, 'αντιβιω', 'αντιβιοτ') and (
        re.search(r'\bτι\s+ειναι\b', query)
        or (_has_prefix(words, 'ιου', 'ιοσ', 'ιωσ') and _has_prefix(words, 'δρ', 'δρασ', 'λειτουργ', 'βοηθ', 'πιαν'))
    ):
        scores['antibiotics-general'] = 16
    if visit and (preparation or bringing or discussion):
        scores['visit-preparation'] = 12 + 3 * bringing
    if lab and (preparation or fasting or medication):
        scores['lab-preparation'] = 10 + 4 * fasting
    if reference_range or (normal_range and lab) or (results and meaning):
        scores['lab-results'] = 18
    return scores


def _focused_document(doc, query):
    """Return complete curated sections, never arbitrary truncated sentences."""
    words = query.split()
    wanted = set()
    if doc['id'] == 'visit-preparation':
        if _has_prefix(words, 'φερ', 'φερουμε', 'χαρτι') or re.search(r'\b(?:παρω|παρετε|παιρνω)\s+μαζι\b', query):
            wanted.add('visit-bring')
        if _has_prefix(words, 'συζητ', 'ρωτησ', 'ερωτησ', 'καταγραψ'):
            wanted.add('visit-discuss')
        if _has_prefix(words, 'αναφερ', 'ενημερωσ', 'παθησ', 'επεμβασ', 'ιστορικ'):
            wanted.add('visit-history')
    elif doc['id'] == 'lab-preparation':
        if _has_prefix(words, 'νηστ', 'φαω', 'φαγητ', 'νερο'):
            wanted.update(('lab-instructions', 'lab-fasting'))
        if _has_prefix(words, 'φαρμακ', 'βιταμιν', 'συμπληρωμ'):
            wanted.update(('lab-instructions', 'lab-medications'))
    sections = [s for s in doc.get('sections', []) if s['id'] in wanted]
    if not sections:
        return doc
    return {**doc, 'text': ' '.join(s['text'] for s in sections),
            'section_ids': [s['id'] for s in sections]}


def retrieve(question):
    """Conservative intent-aware retrieval for explicitly supported topics.

    Topic plus preparation/meaning intent is required. Generic words are not
    evidence of relevance. New corpus topics must get explicit rules and evals.
    The downstream LLM still decides whether the candidate actually answers.
    """
    query = ' '.join(re.findall(r'\w+', normalize(question)))
    if any(term in query for term in (
        'κοστι', 'κοστος', 'τιμη επισκεψ', 'ωραριο', 'τηλεφων', 'διευθυνση',
        'κλεισω ραντεβου', 'κλεισετε ραντεβου', 'διαθεσιμ',
    )):
        return []
    scores = _topic_scores(query)
    if not scores:
        return []
    path = Path(__file__).parent / 'knowledge' / 'medical_information.json'
    documents = json.loads(path.read_text(encoding='utf-8'))
    documents += json.loads((path.parent / 'wellbeing_information.json').read_text(encoding='utf-8'))
    ranked = [doc for doc in documents if doc['id'] in scores]
    ranked.sort(key=lambda doc: (-scores[doc['id']], doc['id']))
    return [_focused_document(doc, query) for doc in ranked[:2]]
