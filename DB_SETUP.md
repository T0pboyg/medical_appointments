# Αρχική εγκατάσταση βάσης

Οι οδηγίες αφορούν νέα εγκατάσταση.
Δεν διαγράφουμε υπάρχον Docker volume για να τις επαναλάβουμε.

## 1. Περιβάλλον

Αντιγράφουμε το .env.example ως .env και συμπληρώνουμε τις τιμές.

Διαφορετικοί λογαριασμοί:
- appointments: διαχείριση βάσης και migrations.
- appointments_app: εφαρμογή και καθαριστής.

Το MIGRATION_DATABASE_PASSWORD πρέπει να συμφωνεί με τον
πραγματικό κωδικό PostgreSQL του appointments.

Το APP_DATABASE_PASSWORD είναι ο κωδικός του appointments_app.
Η αλλαγή του .env δεν αλλάζει αποθηκευμένους κωδικούς PostgreSQL.

## 2. Εκκίνηση βάσης και migrations

```powershell
docker compose up -d db
docker compose run --rm migrate
```

Σε κενή βάση εφαρμόζεται η αρχική migration.
Σε ενημερωμένη βάση εμφανίζεται Applied: [].

Αν υπάρχουν πίνακες χωρίς ιστορικό, το πρόγραμμα σταματά.
Δεν καταχωρίζουμε αρχική migration χωρίς σύγκριση της δομής.

## 3. Δημιουργία χρήστη εφαρμογής

Μόνο αν δεν υπάρχει ήδη ο ρόλος:

```powershell
docker compose exec db psql -U appointments -d appointments
```

Μέσα στο psql:

```sql
CREATE ROLE appointments_app NOLOGIN NOSUPERUSER
NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
```

Ορίζουμε τον ίδιο κωδικό που βάλαμε στο APP_DATABASE_PASSWORD:

```text
\password appointments_app
\q
```

Εφαρμόζουμε τα δικαιώματα:

```powershell
Get-Content -Raw -Encoding UTF8 .\backend\app_permissions.sql | docker compose exec -T db psql -U appointments -d appointments -v ON_ERROR_STOP=1
```

Ενεργοποιούμε τη σύνδεση:

```powershell
docker compose exec db psql -U appointments -d appointments -c "ALTER ROLE appointments_app LOGIN;"
```

## 4. Εκκίνηση εφαρμογής

```powershell
docker compose up -d backend frontend cleanup
```

Το Keycloak χρειάζεται επιπλέον τη ρύθμιση του Keycloak_Setup.md.

## Επόμενες αλλαγές δομής

Προσθέτουμε νέο αριθμημένο SQL αρχείο στο backend/migrations.
Δεν τροποποιούμε ήδη εφαρμοσμένη migration.
Εκτελούμε migrations με τον διαχειριστικό λογαριασμό,
όχι με τον appointments_app.

Τα δικαιώματα νέων πινάκων εξετάζονται ξεχωριστά.

### Πρώτη εκκίνηση Keycloak

Πριν δημιουργηθούν οι clients, τα OIDC_CLIENT_SECRET και
KEYCLOAK_ACCESS_CLIENT_SECRET δεν είναι ακόμη διαθέσιμα.

Για την αρχική εκκίνηση μόνο, συμπληρώνουμε στο τοπικό .env
προσωρινές μη κενές τιμές για αυτά τα δύο πεδία.

Ξεκινάμε μόνο τη βάση και το Keycloak:

    docker compose up -d db keycloak

Ακολουθούμε το Keycloak_Setup.md για realm, clients, ρόλους και MFA.

Αντικαθιστούμε τις προσωρινές τιμές με τα πραγματικά client secrets
της συγκεκριμένης εγκατάστασης πριν ξεκινήσουμε το backend.

Τα KEYCLOAK_ADMIN_PASSWORD, MIGRATION_DATABASE_PASSWORD,
APP_DATABASE_PASSWORD και API_PROXY_SECRET πρέπει εξαρχής
να έχουν τις επιλεγμένες τιμές της τοπικής εγκατάστασης.

## Έλεγχος αρχικής εγκατάστασης

Δοκιμάστηκαν σε ξεχωριστό Compose project και νέο volume:
- Εφαρμογή της αρχικής migration.
- Δημιουργία περιορισμένου ρόλου και εφαρμογή δικαιωμάτων.
- Σύνδεση ως appointments_app και ανάγνωση κενού πίνακα ραντεβού.

Η δοκιμή δεν καλύπτει ακόμη πλήρη αρχική εγκατάσταση Keycloak
και ολόκληρης της εφαρμογής σε νέο υπολογιστή.