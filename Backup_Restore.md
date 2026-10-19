# Τοπικό backup και δοκιμή επαναφοράς

## Πεδίο κάλυψης

Το backup περιλαμβάνει τη βάση appointments.
Δεν περιλαμβάνει χρήστες/ρόλους PostgreSQL, Keycloak ή αρχεία .env.

Τα backups αποθηκεύονται στο backups/, εκτός Git.
Περιέχουν προσωπικά δεδομένα και ενδεχομένως συνεδρίες.
Δεν ανεβαίνουν σε συνομιλίες ή repositories.

## Δημιουργία backup

Οι παρακάτω εντολές αντικαθιστούν τυχόν προηγούμενο αρχείο
με το ίδιο όνομα. Για διατήρηση ιστορικού χρησιμοποιούμε νέα ονόματα.

```powershell
docker compose exec -T db pg_dump -U appointments -d appointments -Fc -f /tmp/appointments-backup.dump
docker compose cp db:/tmp/appointments-backup.dump ./backups/appointments-backup.dump
```

## Έλεγχος αντιγράφου

```powershell
Get-FileHash -Algorithm SHA256 .\backups\appointments-backup.dump
docker compose exec -T db sha256sum /tmp/appointments-backup.dump
```

Τα hashes πρέπει να συμφωνούν.

## Επαναφορά σε νέα βάση δοκιμής

Αντιγράφουμε στο container το τοπικό αρχείο που θέλουμε να δοκιμάσουμε:

```powershell
docker compose cp ./backups/appointments-backup.dump db:/tmp/restore-input.dump
docker compose exec db createdb -U appointments appointments_restore_test
docker compose exec -T db pg_restore -U appointments -d appointments_restore_test --exit-on-error --single-transaction /tmp/restore-input.dump
```

Αν η βάση δοκιμής υπάρχει ήδη, σταματάμε και επιλέγουμε νέο όνομα.
Δεν διαγράφουμε ή αντικαθιστούμε την κανονική βάση.

Οι ρόλοι που αναφέρονται στο backup πρέπει να υπάρχουν στον προορισμό.
Δεν συνδέουμε εφαρμογή ή καθαριστή στη βάση δοκιμής.

## Ακύρωση παλιών συνεδριών μετά την επαναφορά

Στη βάση που επαναφέραμε εκτελούμε:

```sql
BEGIN;
DELETE FROM staff_sessions;
DELETE FROM booking_rate_limits;
COMMIT;
```

Έτσι δεν επανενεργοποιούνται παλιές συνεδρίες σύνδεσης.

## Έλεγχοι

Ελέγχουμε πλήθος και περιεχόμενο ραντεβού, constraints και δικαιώματα.
Η επιτυχία του pg_restore μόνη της δεν αρκεί.

## Εκκρεμότητες παραγωγής

Απαιτούνται κρυπτογράφηση, ανεξάρτητος προορισμός αποθήκευσης,
πολιτική διατήρησης, backup Keycloak και τακτικές δοκιμές επαναφοράς.