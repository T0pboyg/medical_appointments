# Τοπική ρύθμιση Keycloak

Οι ρυθμίσεις Keycloak αποθηκεύονται στο Docker volume.
Το git pull δεν μεταφέρει χρήστες, κωδικούς ή ρυθμίσεις MFA.

## Realm

Όνομα: medical-appointments
Χωρίς κενά στην αρχή ή στο τέλος.

## Client εφαρμογής

- Client ID: medical-appointments-backend
- Protocol: OpenID Connect
- Client authentication: On
- Standard flow: On
- Direct access grants: Off
- Root URL: http://localhost:5173
- Home URL: http://localhost:5173/admin
- Valid redirect URI: http://localhost:5173/api/auth/callback
- Valid post logout redirect URI: http://localhost:5173/
- Web origins: κενό

Το client secret κάθε εγκατάστασης μπαίνει στο τοπικό .env.
Δεν αποθηκεύεται στο Git.

## Ρόλος προσωπικού

Δημιουργούμε realm role με όνομα staff.
Τον αναθέτουμε μόνο σε λογαριασμούς προσωπικού.

## Mapper ρόλων

Στο dedicated scope του client δημιουργούμε mapper:

- Type: User Realm Role
- Name: staff-realm-roles
- Token Claim Name: realm_roles
- Claim JSON Type: String
- Multivalued: On
- Add to ID token: On
- Role prefix: κενό

## Υποχρεωτικό OTP

Αντιγράφουμε τη ροή browser ως medical-staff-browser.

Στο αντίγραφο:

- Sub-flow Conditional 2FA: Required
- Condition – user configured: Disabled
- Condition – credential: Disabled
- OTP Form: Required
- WebAuthn Authenticator: Disabled
- Recovery Authentication Code Form: Disabled

Στον client medical-appointments-backend:
Authentication flow overrides → Browser Flow → medical-staff-browser.

Δεν αλλάζουμε το γενικό Browser binding του realm.

## Έλεγχοι

- Χρήστης staff με OTP συνδέεται στο /admin.
- Λανθασμένος OTP απορρίπτεται.
- Νέος χρήστης staff χωρίς OTP υποχρεώνεται να το ρυθμίσει.
- Χρήστης χωρίς staff απορρίπτεται με 403.
- Χωρίς συνεδρία, η λίστα ραντεβού επιστρέφει 401.
- Μετά το logout, η λίστα επιστρέφει 401.

Κάθε χρήστης συνδέει το δικό του Authenticator.
Δεν μοιραζόμαστε OTP secrets, QR codes ή cookies.

Η τωρινή εγκατάσταση είναι περιβάλλον ανάπτυξης με HTTP.
Δεν αποτελεί έτοιμη παραγωγική εγκατάσταση.

## Service account ελέγχου πρόσβασης

Δημιουργούμε client medical-access-checker:

- Protocol: OpenID Connect
- Client authentication: On
- Service accounts roles: On
- Standard flow: Off
- Direct access grants: Off
- Οι υπόλοιπες προαιρετικές ροές: Off

Στο Service account roles αναθέτουμε:
realm-management → view-users

Δεν αναθέτουμε manage-users ή realm-admin.

Στο τοπικό .env προσθέτουμε:

KEYCLOAK_ACCESS_CLIENT_ID=medical-access-checker
KEYCLOAK_ACCESS_CLIENT_SECRET=το_secret_της_δικής_μας_εγκατάστασης

Το πραγματικό secret δεν αποθηκεύεται στο Git.

Το backend επανελέγχει την ενεργή κατάσταση και τον realm role staff
σε κάθε προστατευμένο αίτημα.

Αν αφαιρεθεί ο ρόλος ή απενεργοποιηθεί ο χρήστης:
- Το επόμενο προστατευμένο αίτημα απορρίπτεται με 401.
- Διαγράφονται όλες οι τοπικές συνεδρίες του χρήστη.
- Μετά την αποκατάσταση δικαιωμάτων απαιτείται νέο login.

Αν το Keycloak δεν είναι διαθέσιμο:
- Η προστατευμένη ενέργεια απορρίπτεται με 503.
- Η τοπική συνεδρία δεν διαγράφεται εξαιτίας της διακοπής.

## Ρυθμίσεις τοπικού περιβάλλοντος και proxy

Σε νέο υπολογιστή αντιγράφουμε το .env.example ως .env:

    Copy-Item .env.example .env

Συμπληρώνουμε όλες τις κενές τιμές πριν ξεκινήσουμε το Compose.
Τα client secrets προέρχονται από τους clients της δικής μας
εγκατάστασης Keycloak.

Για το API_PROXY_SECRET δημιουργούμε τυχαία τιμή. Αν το backend
δεν έχει ξεκινήσει ακόμη, μπορούμε να χρησιμοποιήσουμε:

    docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(32))"

Αποθηκεύουμε την τιμή μόνο στο τοπικό .env.
Δεν την προσθέτουμε στο Git και δεν χρησιμοποιούμε πρόθεμα VITE_.

Το Compose παρέχει το ίδιο API_PROXY_SECRET στον Vite server
και στο backend. Το Vite αντικαθιστά τα headers προώθησης
πριν στείλει το αίτημα στο backend.

Οι δημόσιες κρατήσεις γίνονται μέσω:
http://localhost:5173/api/appointments

Το όριο είναι 5 προσπάθειες ανά IP ανά ημερολογιακό λεπτό.
Η έκτη απορρίπτεται με 429 και Retry-After.
Στο Docker Desktop πολλοί επισκέπτες μπορεί να εμφανίζονται
με την ίδια IP πύλης και να μοιράζονται το όριο.

Το Vite είναι server ανάπτυξης. Η παραγωγική εγκατάσταση
χρειάζεται ξεχωριστή ρύθμιση έμπιστου reverse proxy.