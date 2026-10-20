# Τοπικό backup και δοκιμή επαναφοράς

## Πεδίο κάλυψης

Το έγγραφο καλύπτει ξεχωριστά αντίγραφα της βάσης appointments
και του τοπικού volume Keycloak.

Το pg_dump της appointments δεν περιλαμβάνει χρήστες/ρόλους
PostgreSQL ούτε δεδομένα Keycloak.
Τα αρχεία .env δεν περιλαμβάνονται σε κανένα από αυτά τα αντίγραφα.

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

## Τοπικό backup Keycloak

Το Keycloak χρησιμοποιεί βάση H2 στο volume
`medical-appointments_keycloak_data`.

Παίρνουμε αντίγραφο μόνο με σταματημένο το Keycloak.
Το archive περιλαμβάνει ευαίσθητα δεδομένα ταυτοποίησης
και αποθηκεύεται στο backups/, εκτός Git.

### Δημιουργία αντιγράφου

Εκτελούμε από τη ρίζα του project, στο ίδιο PowerShell.
Επιβεβαιώνουμε πρώτα το όνομα του volume:

```powershell
$keycloakContainer = docker compose ps -q keycloak
docker inspect $keycloakContainer --format '{{range .Mounts}}{{println .Type .Name .Destination}}{{end}}'
```

Για το συγκεκριμένο τοπικό περιβάλλον:

```powershell
New-Item -ItemType Directory -Force .\backups
$keycloakBackupName = "keycloak-data-$(Get-Date -Format 'yyyyMMdd-HHmmss').tar.gz"

docker compose stop keycloak
```

Μόνο αφού επιβεβαιωθεί ότι σταμάτησε:

```powershell
docker run --rm --mount "type=volume,source=medical-appointments_keycloak_data,target=/source,readonly" --mount "type=bind,source=$((Get-Location).Path)\backups,target=/backup" alpine:3.22 tar -czf "/backup/$keycloakBackupName" -C /source .
$LASTEXITCODE
```

Αναμένουμε κωδικό 0. Ξεκινάμε ξανά το Keycloak ακόμη
και αν η δημιουργία backup αποτύχει:

```powershell
docker compose start keycloak
```

Ελέγχουμε το archive:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath ".\backups\$keycloakBackupName"
docker run --rm --mount "type=bind,source=$((Get-Location).Path)\backups,target=/backup,readonly" alpine:3.22 tar -tzf "/backup/$keycloakBackupName"
```

Η ανάγνωση του archive δεν αντικαθιστά τη δοκιμή επαναφοράς.

### Δοκιμή επαναφοράς

Χρησιμοποιούμε νέο volume και την ίδια έκδοση Keycloak.
Οι μεταβλητές πρέπει να δείχνουν στο επιλεγμένο backup.
Δεν επαναφέρουμε πάνω στο κανονικό volume.

```powershell
$keycloakRestoreVolume = "medical-keycloak-restore-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
docker volume create $keycloakRestoreVolume

docker run --rm --mount "type=volume,source=$keycloakRestoreVolume,target=/restore" --mount "type=bind,source=$((Get-Location).Path)\backups,target=/backup,readonly" alpine:3.22 tar -xzf "/backup/$keycloakBackupName" -C /restore
$LASTEXITCODE
```

Μόνο αν η αποσυμπίεση ολοκληρωθεί με κωδικό 0:

```powershell
docker run -d --name medical-keycloak-restore-test -p 127.0.0.1:8082:8080 --mount "type=volume,source=$keycloakRestoreVolume,target=/opt/keycloak/data" quay.io/keycloak/keycloak:26.8.1 start-dev --hostname=http://localhost:8082

docker logs --tail 30 medical-keycloak-restore-test
```

Αν το όνομα container χρησιμοποιείται ήδη, σταματάμε
και επιλέγουμε διαφορετικό όνομα.

Στο http://localhost:8082/admin/ ελέγχουμε:
- Σύνδεση διαχειριστή.
- Realm medical-appointments.
- Χρήστες, clients και authentication flows.

Δεν δοκιμάζουμε σύνδεση στην κανονική εφαρμογή από
το αντίγραφο, επειδή περιέχει τις αρχικές διευθύνσεις redirect.

Μετά τον έλεγχο:

```powershell
docker stop medical-keycloak-restore-test
```

Η δοκιμή πραγματοποιήθηκε στις 19/10/2026 με Keycloak 26.8.1.
Επιβεβαιώθηκαν εκκίνηση, σύνδεση διαχειριστή και παρουσία
realm, χρηστών, clients και authentication flow.
Δεν δοκιμάστηκε πλήρης σύνδεση εφαρμογής μέσω του αντιγράφου.

## Κρυπτογράφηση τοπικών αντιγράφων

Χρησιμοποιούμε age με μυστική φράση:

```powershell
age -p -o .\backups\BACKUP.age .\backups\BACKUP
```

Αντικαθιστούμε το BACKUP με το πραγματικό όνομα αρχείου.
Επιλέγουμε νέο όνομα εξόδου αν υπάρχει ήδη.

Η φράση εισάγεται διαδραστικά και φυλάσσεται χωριστά
από τα backups. Δεν αποθηκεύεται σε .env, εντολές ή Git.
Χωρίς τη φράση δεν υπάρχει δυνατότητα ανάκτησης.

Ελέγχουμε την αποκρυπτογράφηση σε νέο προσωρινό αρχείο:

```powershell
age -d -o .\backups\decryption-test.bin .\backups\BACKUP.age
Get-FileHash -Algorithm SHA256 .\backups\BACKUP, .\backups\decryption-test.bin
```

Τα hashes πρέπει να συμφωνούν. Μετά διαγράφουμε μόνο
το προσωρινό αποκρυπτογραφημένο αρχείο.

Ελέγχθηκε επιτυχώς για το PostgreSQL dump και το archive
Keycloak στις 21/10/2026. Τα αρχικά μη κρυπτογραφημένα
αντίγραφα εξακολουθούν να υπάρχουν τοπικά.

## Συχνότητα και διατήρηση αντιγράφων

Για το τοπικό δοκιμαστικό περιβάλλον:

- Βάση appointments: backup στο τέλος κάθε ημέρας με αλλαγές.
- Keycloak: backup μετά από αλλαγές χρηστών, MFA, clients ή flows.
- Πριν από migrations ή αναβαθμίσεις: νέο backup των επηρεαζόμενων
  δεδομένων.
- Κάθε νέο backup κρυπτογραφείται και αντιγράφεται στο Drive.
- Χρησιμοποιούμε μοναδικά ονόματα με ημερομηνία και ώρα.

Κρατάμε τα 7 πιο πρόσφατα ημερήσια και 4 εβδομαδιαία
επαληθευμένα αντίγραφα κάθε τύπου.

Δεν διαγράφουμε παλιό αντίγραφο πριν επιβεβαιώσουμε ότι
το νεότερο έχει κρυπτογραφηθεί και μεταφερθεί επιτυχώς.

Κάθε μήνα και μετά από σημαντική αναβάθμιση κάνουμε δοκιμή:
λήψη από Drive, αποκρυπτογράφηση και επαναφορά σε απομονωμένο
περιβάλλον. Καταγράφουμε ημερομηνία και αποτέλεσμα.

Η διαδικασία παραμένει χειροκίνητη. Η πολιτική παραγωγής
θα καθοριστεί με βάση την αποδεκτή απώλεια δεδομένων,
τον χρόνο αποκατάστασης και τις απαιτήσεις διατήρησης.

## Εκκρεμότητες παραγωγής
Απαιτούνται συστηματική εφαρμογή κρυπτογράφησης, ανεξάρτητος προορισμός αποθήκευσης,
πολιτική διατήρησης και τακτική ενημέρωση και έλεγχο των αντιγράφων εκτός υπολογιστή.

Η διαδικασία Keycloak αφορά το συγκεκριμένο τοπικό περιβάλλον
H2/start-dev. Το περιβάλλον παραγωγής χρειάζεται ξεχωριστή
διαδικασία backup για τη βάση και τη διαμόρφωσή του.

## Αντίγραφο εκτός υπολογιστή

Αποθηκεύουμε μόνο τα κρυπτογραφημένα αρχεία .age σε ιδιωτικό
φάκελο Google Drive, με πρόσβαση «Περιορισμένη».

Δεν ανεβάζουμε μη κρυπτογραφημένα backups, αρχεία .env
ή τη μυστική φράση.

Μετά τη μεταφόρτωση κατεβάζουμε τα αρχεία σε ξεχωριστό
τοπικό υποφάκελο και συγκρίνουμε τα SHA256 hashes με
τα αρχικά κρυπτογραφημένα αρχεία.

Στις 21/10/2026 επιβεβαιώθηκαν ίδια hashes για τα δύο
αρχεία .age που κατέβηκαν από το Drive.

Η μυστική φράση φυλάσσεται χωριστά από τα backups.