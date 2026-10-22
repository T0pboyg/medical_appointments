"""Small, versioned, local allowlist. Never fetch URLs supplied by a user."""
import json
import unicodedata
from pathlib import Path


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if unicodedata.category(c) != 'Mn')


def retrieve(question):
    query = normalize(question)
    if any(term in query for term in ('κοστι', 'κοστος', 'τιμη επισκεψ', 'ωραριο', 'τηλεφων', 'διευθυνση')):
        return []
    documents = json.loads((Path(__file__).parent / 'knowledge' / 'medical_information.json').read_text(encoding='utf-8'))
    ranked = []
    for doc in documents:
        score = sum(term in query for term in doc['keywords'])
        if score:
            ranked.append((score, doc))
    return [doc for _, doc in sorted(ranked, key=lambda item: -item[0])[:2]]
