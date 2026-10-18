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