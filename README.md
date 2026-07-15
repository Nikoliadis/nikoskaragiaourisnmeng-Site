# Εκπαιδευτική Ιστοσελίδα — Νικόλαος Καραγκιαούρης (Μηχανολόγος ΠΕ82)

Django 6 + Tailwind CSS v4 + HTMX + django-unfold admin.

Οι μαθητές βλέπουν και κατεβάζουν υλικό (θέματα, ασκήσεις, e-books, ανακοινώσεις).
Ο καθηγητής διαχειρίζεται τα πάντα από το admin panel — **χωρίς κώδικα**.

---

## Τεχνολογίες

| Ρόλος | Εργαλείο |
|---|---|
| Web framework | Django 6 |
| Admin panel | django-unfold (στα Ελληνικά) |
| CSS | Tailwind CSS v4 (standalone binary μέσω `pytailwindcss` — **δεν χρειάζεται Node.js**) |
| Διαδραστικότητα | HTMX (φόρμα επικοινωνίας χωρίς reload) |
| Έλεγχος αρχείων | `filetype` (MIME sniffing, καθαρή Python) |

## Δομή project

```
config/            # settings, urls, wsgi
content/           # η εφαρμογή: models, views, admin, validators, storage
  management/…     # εντολή seed_demo
templates/         # base.html, navbar, σελίδες
static/src/        # input.css (Tailwind πηγή)
static/css/        # app.css (χτισμένο — μην το επεξεργάζεσαι με το χέρι)
protected_media/   # τα ανεβασμένα αρχεία (ΕΚΤΟΣ web root)
media/             # δημόσιες εικόνες ανακοινώσεων
```

---

## Setup βήμα-βήμα

**1. Virtual environment & εξαρτήσεις**
```bash
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

**2. Ρυθμίσεις περιβάλλοντος**
```bash
copy .env.example .env           # και άλλαξε το DJANGO_SECRET_KEY
```

**3. Βάση δεδομένων**
```bash
python manage.py migrate
python manage.py createsuperuser
```

**4. Χτίσιμο του CSS** (μία φορά, ή με `--watch` κατά την ανάπτυξη)
```bash
tailwindcss -i static/src/input.css -o static/css/app.css --minify
# κατά την ανάπτυξη:
tailwindcss -i static/src/input.css -o static/css/app.css --watch
```

**5. (Προαιρετικό) Δείγμα δεδομένων**
```bash
python manage.py seed_demo
```

**6. Εκκίνηση**
```bash
python manage.py runserver
```
- Ιστοσελίδα: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/

---

## Πώς προσθέτει υλικό ο καθηγητής

1. Μπαίνει στο **/admin/** με τον λογαριασμό του.
2. **Κατηγορίες** → φτιάχνει π.χ. «Θέματα 2024» (επιλέγει Ενότητα: Πανελλαδικές). Για
   υποκατηγορία, ορίζει «Γονική κατηγορία».
3. **Έγγραφα / Υλικό** → «Προσθήκη»: τίτλος, κατηγορία, ανέβασμα αρχείου. Το όνομα, το
   μέγεθος και ο τύπος συμπληρώνονται αυτόματα.
4. **Ανακοινώσεις** → κείμενο με μορφοποίηση (rich text) + προαιρετική εικόνα.
5. **Μηνύματα επικοινωνίας** → διαβάζει όσα στέλνουν οι μαθητές.

Οι κατηγορίες εμφανίζονται **αυτόματα** στα dropdown του menu.

---

## Ασφάλεια αρχείων

- Τα αρχεία αποθηκεύονται στο `protected_media/` με **τυχαίο όνομα UUID**· το πραγματικό
  όνομα κρατιέται στη βάση.
- Δεν υπάρχει δημόσιο URL· η λήψη γίνεται **μόνο** μέσω του `content.views.download`
  (`/lipsi/<id>/`), που σερβίρει το αρχείο με το σωστό όνομα.
- Κάθε ανέβασμα ελέγχεται (`content/validators.py`):
  - **Whitelist επεκτάσεων:** pdf, doc, docx, jpg, jpeg, png
  - **Όριο μεγέθους:** 25 MB (ρυθμίζεται με `MAX_UPLOAD_SIZE`)
  - **MIME sniffing:** τα magic bytes πρέπει να ταιριάζουν με την επέκταση
    (μπλοκάρει π.χ. `.exe` μετονομασμένο σε `.pdf`).

---

## Παραγωγή (production) — σημειώσεις

- Βάλε `DJANGO_DEBUG=False` και σωστό `DJANGO_ALLOWED_HOSTS` στο `.env`.
- Όρισε το `PROTECTED_MEDIA_ROOT` σε φάκελο **εκτός** του document root του web server.
- `python manage.py collectstatic` και σέρβιρε το `staticfiles/` από τον web server.
- Για μεγάλα αρχεία, χρησιμοποίησε `X-Sendfile`/`X-Accel-Redirect` αντί για streaming
  μέσω Django (η τρέχουσα υλοποίηση με `FileResponse` δουλεύει, αλλά περνά από τη Python).
- Λογαριασμός καθηγητή: φτιάξε του χρήστη **staff** με δικαιώματα μόνο στα models που
  χρειάζεται (ή άφησέ τον superuser αν είναι ο μόνος διαχειριστής).
