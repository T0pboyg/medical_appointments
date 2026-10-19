# Εξαρτήσεις και έλεγχοι

## Backend

Το `backend/requirements.txt` δηλώνει τις άμεσες εξαρτήσεις.
Το `backend/requirements.lock` περιέχει ακριβείς εκδόσεις και hashes.
Το Docker εγκαθιστά από το lockfile με `--require-hashes`.

Δεν επεξεργαζόμαστε χειροκίνητα το lockfile.

Για ανανέωση, χρησιμοποιούμε προσωρινό περιβάλλον Python 3.12:

```powershell
docker compose exec backend python -m venv /tmp/pip-tools-env
docker compose exec backend /tmp/pip-tools-env/bin/python -m pip install pip-tools
docker compose exec backend /tmp/pip-tools-env/bin/pip-compile --upgrade --generate-hashes --output-file=/app/requirements.lock /app/requirements.txt
```

Το `--upgrade` ανανεώνει όλες τις επιτρεπόμενες εξαρτήσεις.
Για στοχευμένη αναβάθμιση χρησιμοποιούμε `--upgrade-package ΟΝΟΜΑ`
αντί για `--upgrade`. Ελέγχουμε το diff πριν συνεχίσουμε.

Μετά την ανανέωση:
1. Ελέγχουμε το lockfile με `pip-audit`.
2. Κάνουμε build των backend, cleanup και migrate.
3. Τρέχουμε `pip check` και όλα τα tests σε δοκιμαστική βάση.
4. Ελέγχουμε σύνδεση και φόρτωση του admin.

## Frontend

Το `frontend/package-lock.json` παρακολουθείται από το Git.
Η εγκατάσταση γίνεται με `npm ci`.

Οι αναβαθμίσεις γίνονται σκόπιμα, με έλεγχο των αλλαγών στα
`package.json` και `package-lock.json`, `npm audit` και δοκιμή
της δημόσιας φόρμας και του admin.

Δεν χρησιμοποιούμε αυτόματα `npm audit fix --force`.

## GitHub Actions

Το `.github/workflows/security.yml` εκτελεί:
- Backend tests με προσωρινή PostgreSQL.
- Έλεγχο του backend lockfile με `pip-audit`.
- Εγκατάσταση frontend με `npm ci` και έλεγχο με `npm audit`.

Οι δοκιμαστικές ρυθμίσεις του workflow δεν είναι πραγματικά μυστικά.
Μηδενικά ευρήματα σημαίνουν ότι δεν εντοπίστηκαν γνωστές ευπάθειες
τη στιγμή του ελέγχου, όχι ότι εγγυάται η συνολική ασφάλεια.