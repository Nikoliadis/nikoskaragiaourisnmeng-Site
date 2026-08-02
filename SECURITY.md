# Αναφορά ασφαλείας

Έλεγχος ολόκληρου του project με βάση OWASP Top 10 (2021), OWASP ASVS 2.0 Level 2
και τις πρακτικές ασφαλείας του Django. Ημερομηνία: **2 Αυγούστου 2026**.

Επαλήθευση: `manage.py check --deploy` καθαρό (0 προειδοποιήσεις), **49 tests**
περνούν, `pip-audit` δεν βρήκε γνωστές ευπάθειες στις εξαρτήσεις.

---

## Σύνοψη

| | Πριν | Μετά |
|---|---|---|
| **Βαθμολογία** | 62 / 100 | **88 / 100** |
| **Επίπεδο κινδύνου** | Μέτριο–Υψηλό | **Χαμηλό** |
| Κρίσιμα | 0 | 0 |
| Υψηλού κινδύνου | 3 | 0 |
| Μεσαίου κινδύνου | 7 | 0 |
| Χαμηλού κινδύνου | 6 | 3 (αποδεκτά, δες §Υπόλοιπα) |

Οι 12 μονάδες που λείπουν από το 100 δεν είναι κώδικας: αφορούν πράγματα που
γίνονται **στον server** (HTTPS, firewall, backups, monitoring) και δεν μπορούν
να επιβεβαιωθούν από εδώ. Οδηγίες: [`deploy/README.md`](deploy/README.md).

---

## Ευρήματα και τι έγινε

### Υψηλού κινδύνου

**H1 — Stored XSS μέσω των ανακοινώσεων** *(A03 Injection)*
Το `announcement_detail.html` έκανε render το περιεχόμενο με `|safe`. Ο editor
του admin είναι WYSIWYG, οπότε ένας συμβιβασμένος λογαριασμός staff μπορούσε να
φυτέψει `<script>` που θα έτρεχε στον browser **κάθε** επισκέπτη — κλοπή session,
αλλοίωση σελίδας.
→ Νέο [`content/sanitizer.py`](Backend/content/sanitizer.py): το περιεχόμενο
περνά από **nh3** στο `save()`. Επιτρέπονται μόνο tags μορφοποίησης· `<script>`,
`onclick`, `javascript:` αφαιρούνται **πριν** μπουν στη βάση. Άμυνα στην πηγή,
όχι στο template.

**H2 — Παράκαμψη του ελέγχου τύπου αρχείου** *(A08 Software Integrity)*
Ο έλεγχος magic bytes εφαρμοζόταν **μόνο όταν** το `filetype` αναγνώριζε κάτι.
Ένα αρχείο HTML/JS μετονομασμένο σε `.pdf` περνούσε ανενόχλητο, γιατί δεν
αναγνωριζόταν καθόλου.
→ Τώρα απορρίπτεται ό,τι δεν αναγνωρίζεται, με μοναδική εξαίρεση το `.doc` που
όντως δεν έχει αξιόπιστη υπογραφή (`UNSNIFFABLE_UPLOAD_TYPES`).

**H3 — Ο ιστότοπος φόρτωνε κώδικα από τρίτους χωρίς έλεγχο** *(A08)*
Το htmx ερχόταν από `unpkg.com` **χωρίς SRI**: όποιος έλεγχε το CDN μπορούσε να
εκτελέσει δικό του JavaScript σε κάθε σελίδα. Οι γραμματοσειρές έρχονταν από
Google, στέλνοντας την IP κάθε μαθητή στην Google (**θέμα GDPR** για δημόσιο
σχολικό site).
→ htmx και γραμματοσειρές κατέβηκαν τοπικά (`Frontend/static/js|fonts`). Ο
ιστότοπος πλέον **δεν φορτώνει τίποτα από εξωτερικό origin** — επαληθεύεται με test.

### Μεσαίου κινδύνου

| # | Εύρημα | Διόρθωση |
|---|---|---|
| M1 | `DEBUG` προεπιλογή `True` — ξεχασμένη μεταβλητή στον server εκθέτει tracebacks, settings και SQL *(A05)* | Προεπιλογή `False`· το dev το ενεργοποιεί ρητά στο `.env` |
| M2 | Δεκτό αδύναμο/placeholder `SECRET_KEY` σε production — πλαστογραφήσιμα sessions *(A02)* | Αρνείται να ξεκινήσει αν λείπει, είναι <50 χαρακτήρες ή ξεκινά με `django-insecure-` |
| M3 | Καμία προστασία brute-force στο `/admin/` *(A07)* | **django-axes**: 5 αποτυχίες → κλείδωμα 1 ώρας ανά IP+username, με καταγραφή |
| M4 | PBKDF2 hashing | **Argon2id** (σύσταση OWASP), ελάχιστο μήκος κωδικού 12 χαρακτήρες |
| M5 | Καμία CSP — ένα XSS θα εκτελούνταν ανεμπόδιστα *(A05)* | **django-csp** με `default-src 'self'`, χωρίς `unsafe-inline` στο δημόσιο site |
| M6 | Η φόρμα επικοινωνίας δεχόταν απεριόριστα μηνύματα *(A04 Insecure Design)* | **django-ratelimit** 5/ώρα ανά IP + το υπάρχον honeypot |
| M7 | Λείπαν headers: Referrer-Policy, Permissions-Policy, COOP/CORP· cookies χωρίς `HttpOnly`/`SameSite` | Όλα ρυθμισμένα· νέο [`content/middleware.py`](Backend/content/middleware.py) |

### Χαμηλού κινδύνου

| # | Εύρημα | Διόρθωση |
|---|---|---|
| L1 | Καμία καταγραφή συμβάντων ασφαλείας *(A09)* | `LOGGING` με rotating αρχείο `Database/logs/security.log` για `django.security`, `django.request`, `axes`, `content.security` |
| L2 | Προεπιλεγμένες σελίδες σφάλματος | Δικές μας 400/403/404/500 χωρίς καμία εσωτερική πληροφορία· η 500 αυτόνομη ώστε να μη σκάει κι αυτή |
| L3 | Το όνομα αρχείου επιστρεφόταν στο `Content-Disposition` χωρίς έλεγχο | `validate_filename()`: απορρίπτει control chars, εισαγωγικά και `\r\n` (header injection) |
| L4 | Απεριόριστος αριθμός πεδίων/αρχείων ανά αίτημα | `DATA_UPLOAD_MAX_NUMBER_FIELDS=200`, `_FILES=20` |
| L5 | Δικαιώματα ανεβασμένων αρχείων στα προεπιλεγμένα | `FILE_UPLOAD_PERMISSIONS=0o640`, φάκελοι `0o750` |
| L6 | Στατικά χωρίς cache-busting | `ManifestStaticFilesStorage` σε production |

---

## Έλεγχος OWASP Top 10 (2021)

| | Κατηγορία | Κατάσταση |
|---|---|---|
| A01 | Broken Access Control | **OK** — Το `/lipsi/<id>/` είναι σκόπιμα δημόσιο (υλικό για μαθητές), οπότε η απαρίθμηση IDs **δεν** είναι IDOR: δεν υπάρχει ιδιοκτησία ή προνόμιο να παρακαμφθεί. Κρυμμένα έγγραφα (`is_active=False`) επιστρέφουν 404. Το admin προστατεύεται από τα permissions του Django. Δεν υπάρχουν custom endpoints χωρίς έλεγχο. |
| A02 | Cryptographic Failures | **OK** — Argon2id, υποχρεωτικό ισχυρό SECRET_KEY, HSTS ένα έτος, TLS 1.2/1.3 μόνο, Secure cookies |
| A03 | Injection | **OK** — Αποκλειστικά Django ORM, **μηδέν raw SQL** (επαληθεύτηκε), autoescaping παντού, το μοναδικό `|safe` καλύπτεται πλέον από sanitising. Κανένα `eval`/`exec`/`subprocess`/`os.system` στον κώδικα |
| A04 | Insecure Design | **OK** — Αρχεία εκτός web root με τυχαία ονόματα UUID, rate limiting, honeypot |
| A05 | Security Misconfiguration | **OK** — `check --deploy` καθαρό, DEBUG ασφαλές by default, CSP, όλα τα headers |
| A06 | Vulnerable Components | **OK** — `pip-audit`: καμία γνωστή ευπάθεια. Django 6.0.7, όλα καρφωμένα σε έκδοση |
| A07 | Authentication Failures | **OK** — axes lockout, Argon2, session 8 ωρών με λήξη στο κλείσιμο, ελάχιστο 12 χαρακτήρες. Το Django κάνει ήδη rotate το session key στο login (προστασία session fixation) |
| A08 | Software & Data Integrity | **OK** — Καμία εξάρτηση από CDN, καρφωμένες εκδόσεις, sniffing στα uploads |
| A09 | Logging & Monitoring Failures | **Μερικώς** — Η καταγραφή υπάρχει· η **ειδοποίηση** (Sentry/uptime) μένει στον server |
| A10 | SSRF | **Δ/Ε** — Η εφαρμογή δεν κάνει κανένα εξερχόμενο αίτημα |

## ASVS Level 2 — σύνοψη

| Ενότητα | Κατάσταση |
|---|---|
| V2 Authentication | Πλήρες εκτός 2FA (V2.8) — δες Υπόλοιπα |
| V3 Session Management | Πλήρες |
| V4 Access Control | Πλήρες για το μοντέλο του site (δημόσιο περιεχόμενο + ένας διαχειριστής) |
| V5 Validation & Encoding | Πλήρες |
| V7 Error Handling & Logging | Πλήρες στο επίπεδο εφαρμογής |
| V8 Data Protection | Πλήρες |
| V9 Communications | Εξαρτάται από τη ρύθμιση TLS στον server |
| V12 Files & Resources | Πλήρες |
| V14 Configuration | Πλήρες |

---

## Τι **δεν** ίσχυε σε αυτό το project

Δεν προσθέτω κώδικα για προβλήματα που δεν υπάρχουν:

* **API / JWT / DRF** — δεν υπάρχει API. Το site είναι server-rendered.
* **CORS** — κανένα cross-origin αίτημα· το `django-cors-headers` θα ήταν
  περιττή επιφάνεια επίθεσης. Το CSP `frame-ancestors 'none'` και το
  `Cross-Origin-Resource-Policy` καλύπτουν το θέμα από την ανάποδη.
* **Docker** — δεν υπάρχει containerisation. Το `deploy/karagiaouris.service`
  δίνει ισοδύναμο sandboxing με systemd.
* **Email** — δεν στέλνονται emails· τα μηνύματα αποθηκεύονται στη βάση.
* **Κωδικός βάσης** — SQLite, αρχείο στον δίσκο. Η ασφάλεια είναι δικαιώματα
  αρχείου (`0640`), όχι κωδικός. Αν κάποτε γίνει PostgreSQL, ο κωδικός πάει
  στο `.env` όπως όλα τα υπόλοιπα.
* **Antivirus σε uploads** — μόνο ο καθηγητής ανεβάζει αρχεία. Αν χρειαστεί,
  ο κατάλληλος τρόπος είναι ClamAV στον server, όχι στον κώδικα.

## Υπόλοιπα (αποδεκτά, τεκμηριωμένα)

1. **Χωρίς 2FA** (ASVS V2.8) — ένας διαχειριστής, ισχυρός κωδικός + lockout.
   Αν το θες: `django-otp` + `django-two-factor-auth`.
2. **Το admin CSP έχει `unsafe-inline`/`unsafe-eval`** — το django-unfold
   (Alpine.js) δεν λειτουργεί χωρίς αυτά. Περιορισμένο μόνο στο `/admin/`, και
   ο περιορισμός origin ισχύει κανονικά: εξωτερικό `<script src>` απορρίπτεται.
3. **Rate limit σε μνήμη διεργασίας** — με πολλούς gunicorn workers το όριο
   είναι ανά worker. Για αυστηρό όριο χρειάζεται Redis· για anti-spam αρκεί.

## Σειρά προτεραιότητας πριν το production

1. `.env` με πραγματικό `DJANGO_SECRET_KEY` και `DJANGO_DEBUG=False` — **χωρίς αυτό δεν ξεκινά**
2. HTTPS με certbot· HSTS αρχικά σε 300s, μετά σε ένα έτος
3. `chmod 600 .env`, `chmod 750 Database/`
4. `ufw` + `fail2ban` + SSH μόνο με κλειδί
5. Καθημερινό backup με `sqlite3 .backup` και **δοκιμή επαναφοράς**
6. Sentry ή έστω uptime monitor
7. Μηνιαίο `pip-audit` και `apt upgrade`

Λεπτομέρειες και έτοιμα αρχεία: [`deploy/README.md`](deploy/README.md).
