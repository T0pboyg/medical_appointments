# Τοπικό στατικό frontend με Caddy

Η στατική έκδοση χρησιμοποιεί το ίδιο `http://localhost:5173` και το ίδιο backend.
Δεν είναι δημόσια φιλοξενία: παραμένουν ενεργές οι τοπικές ρυθμίσεις HTTP και Keycloak.

## Εκκίνηση / μετάβαση από Vite

Από τη ρίζα του project, με το υπάρχον `.env`:

```powershell
docker compose -f compose.yaml -f compose.static.yaml config --quiet
docker compose -f compose.yaml -f compose.static.yaml up -d --build --no-deps frontend
```

Η εντολή αντικαθιστά μόνο το frontend container. Το backend πρέπει ήδη να τρέχει.
Αν ξεκινάτε από σταματημένη εφαρμογή, ξεκινήστε πρώτα τα υπάρχοντα services:

```powershell
docker compose up -d db keycloak backend cleanup
docker compose -f compose.yaml -f compose.static.yaml up -d --build --no-deps frontend
```

Ανοίξτε `http://localhost:5173/` και `http://localhost:5173/admin`.
Ελέγξτε και την πραγματική σύνδεση προσωπικού μέσω Keycloak, τις λεπτομέρειες
και τους assistants. Μην δημιουργείτε πραγματικές κρατήσεις μόνο για δοκιμή.

## Μετά από αλλαγές στον κώδικα

Το Caddy σερβίρει τα αρχεία που ενσωματώθηκαν στο image, χωρίς live reload:

```powershell
docker compose -f compose.yaml -f compose.static.yaml up -d --build --no-deps frontend
```

## Επιστροφή στην ανάπτυξη με Vite

```powershell
docker compose -f compose.yaml up -d --no-deps --force-recreate frontend
```

Μόνο ένας από τους δύο τρόπους λειτουργεί κάθε φορά στη θύρα 5173.
Χρησιμοποιείτε και τα δύο `-f` στις εντολές της στατικής έκδοσης.
Δεν χρειάζεται `down`, διαγραφή volumes ή εφαρμογή των παλιών stashes.

## Έλεγχοι χωρίς προσωπικά δεδομένα

```powershell
docker compose -p medical-appointments-e2e -f compose.e2e.yaml -f compose.e2e.static.yaml up --build --abort-on-container-exit --exit-code-from runner
docker compose -p medical-appointments-e2e -f compose.e2e.yaml -f compose.e2e.static.yaml down --remove-orphans
```

Χρησιμοποιείται ξεχωριστή προσωρινή βάση, χωρίς τις κανονικές συνεδρίες ή κρατήσεις.
Τα browser tests ελέγχουν τη ροή κράτησης/ακύρωσης και τις στατικές σελίδες,
cache headers, API errors και αντικατάσταση πλαστών proxy headers.
Η σύνδεση των tests είναι συνθετική, δεν ελέγχει την πραγματική οθόνη Keycloak.

## Ρυθμίσεις και όρια

- Το `API_PROXY_SECRET` περνά στο runtime container, ποτέ ως build argument ή `VITE_*` μεταβλητή.
- Το build context επιτρέπει μόνο τα απαραίτητα αρχεία frontend.
- Το `/api` προωθείται στο backend, με αφαίρεση του prefix και αντικατάσταση
  του proxy secret και της IP επισκέπτη. Δεν ενεργοποιούνται access logs στο Caddy.
- Το HTML επανελέγχεται (`no-cache`), ενώ τα fingerprinted assets αποθηκεύονται
  στην cache. Άγνωστα assets επιστρέφουν 404 και άγνωστα API paths παραμένουν JSON errors.
- Τα security headers και το CSP μεταφέρθηκαν από τον Vite, χωρίς το development WebSocket.
- Το backend και το Keycloak παραμένουν σε τοπικό development mode. Για δημόσια
  φιλοξενία απαιτείται ξεχωριστή ρύθμιση domain, HTTPS, cookies και OIDC.

Αναφορά: [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
