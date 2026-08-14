# Ανέβασμα σε production

Οδηγός για Ubuntu/Debian server με nginx + Gunicorn. Τα αρχεία δίπλα
(`nginx.conf`, `gunicorn.conf.py`, `karagiaouris.service`) είναι έτοιμα —
αντικατέστησε παντού το `karagiaouris.gr` με το δικό σου domain.

---

## 1. Χρήστης και φάκελοι

Η εφαρμογή **δεν** τρέχει ποτέ ως root.

```bash
sudo adduser --system --group --home /srv/karagiaouris karagiaouris
sudo mkdir -p /srv/karagiaouris /var/log/gunicorn /run/gunicorn
sudo chown -R karagiaouris:www-data /srv/karagiaouris /var/log/gunicorn /run/gunicorn
```

Ανέβασε τον κώδικα στο `/srv/karagiaouris/` και φτιάξε το venv:

```bash
sudo -u karagiaouris python3 -m venv /srv/karagiaouris/venv
sudo -u karagiaouris /srv/karagiaouris/venv/bin/pip install -r /srv/karagiaouris/Backend/requirements.txt
sudo -u karagiaouris /srv/karagiaouris/venv/bin/pip install gunicorn
```

## 2. Το `.env`

```bash
sudo -u karagiaouris nano /srv/karagiaouris/.env
sudo chmod 600 /srv/karagiaouris/.env      # μόνο ο ιδιοκτήτης το διαβάζει
```

```ini
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<50+ τυχαίοι χαρακτήρες>
DJANGO_ALLOWED_HOSTS=karagiaouris.gr,www.karagiaouris.gr
DJANGO_CSRF_TRUSTED_ORIGINS=https://karagiaouris.gr,https://www.karagiaouris.gr
DJANGO_PROXY_COUNT=1
PROTECTED_MEDIA_ROOT=/srv/karagiaouris/Database/protected_media
```

Το κλειδί:
```bash
/srv/karagiaouris/venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

> Το project **αρνείται να ξεκινήσει** με `DEBUG=False` αν το κλειδί λείπει, είναι
> κοντό ή ξεκινά με `django-insecure-`.

## 3. Δικαιώματα αρχείων

```bash
# Ο nginx (www-data) διαβάζει ΜΟΝΟ τα στατικά.
sudo chown -R karagiaouris:www-data /srv/karagiaouris/Frontend
sudo chmod -R g+rX /srv/karagiaouris/Frontend

# Η βάση και τα ανεβασμένα αρχεία μένουν στον χρήστη της εφαρμογής.
sudo chown -R karagiaouris:karagiaouris /srv/karagiaouris/Database
sudo chmod 750 /srv/karagiaouris/Database
sudo chmod 750 /srv/karagiaouris/Database/protected_media
sudo chmod 640 /srv/karagiaouris/Database/db.sqlite3
```

Ο nginx **δεν** πρέπει να έχει πρόσβαση στο `protected_media/` — τα αρχεία
φτάνουν στον χρήστη μόνο μέσω του Django. Γι' αυτό το `Database/` ανήκει στον
`karagiaouris` και **όχι** στο group `www-data`: το Django το γράφει ως
ιδιοκτήτης, ο nginx δεν το φτάνει καν αν κάποτε γραφτεί λάθος `location`.

Έλεγχος ότι όντως ισχύει:

```bash
sudo -u www-data test -r /srv/karagiaouris/Database/db.sqlite3 && echo ΠΡΟΒΛΗΜΑ || echo OK
sudo -u www-data test -r /srv/karagiaouris/Frontend/staticfiles && echo OK || echo ΠΡΟΒΛΗΜΑ
```

## 4. Βάση, στατικά, μενού

```bash
cd /srv/karagiaouris/Backend
sudo -u karagiaouris ../venv/bin/python manage.py migrate
sudo -u karagiaouris ../venv/bin/tailwindcss \
     -i ../Frontend/src/input.css -o ../Frontend/static/css/app.css --minify
sudo -u karagiaouris ../venv/bin/python manage.py collectstatic --noinput
sudo -u karagiaouris ../venv/bin/python manage.py setup_menu
sudo -u karagiaouris ../venv/bin/python manage.py import_links
sudo -u karagiaouris ../venv/bin/python manage.py check --deploy
```

> Χτίσε το CSS **πριν** το `collectstatic`, αλλιώς μαζεύεται το παλιό.

**Μετά από κάθε `collectstatic` ξανατρέξε και τα δύο του βήματος 3:**

```bash
sudo chown -R karagiaouris:www-data /srv/karagiaouris/Frontend
sudo chmod -R g+rX /srv/karagiaouris/Frontend
```

Το `sudo` τρέχει με umask 027, οπότε τα νέα αρχεία βγαίνουν 640 **και με group
`karagiaouris`**. Σκέτο `chmod g+rX` δίνει τότε δικαιώματα σε λάθος group και ο
nginx συνεχίζει να επιστρέφει **403 σε όλα τα CSS/JS/εικόνες** — η σελίδα
φορτώνει σαν γυμνό HTML. Χρειάζονται **και** τα δύο, **και** με αυτή τη σειρά.

## 5. Gunicorn + nginx

```bash
sudo cp deploy/karagiaouris.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now karagiaouris

sudo cp deploy/nginx.conf /etc/nginx/sites-available/karagiaouris.gr
sudo ln -s /etc/nginx/sites-available/karagiaouris.gr /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Το snippet `django-proxy.conf` είναι στο τέλος του `nginx.conf` — φτιάξ' το στο
`/etc/nginx/snippets/`.

## 6. HTTPS

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d karagiaouris.gr -d www.karagiaouris.gr
```

Η ανανέωση γίνεται αυτόματα. **Άφησε το HSTS σε μικρή τιμή** (π.χ. 300) για μία
εβδομάδα· μόλις σιγουρευτείς ότι όλα δουλεύουν σε HTTPS, βάλε το στο έτος.

## 7. Firewall και fail2ban

```bash
sudo ufw default deny incoming && sudo ufw default allow outgoing
sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full'
sudo ufw enable

sudo apt install fail2ban
```

`/etc/fail2ban/jail.local`:
```ini
[sshd]
enabled = true
maxretry = 3
bantime = 1h

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
logpath = /var/log/nginx/karagiaouris.error.log
maxretry = 10
bantime = 1h
```

## 8. SSH hardening

`/etc/ssh/sshd_config`:
```
PermitRootLogin no
PasswordAuthentication no      # μόνο με κλειδί
KbdInteractiveAuthentication no
X11Forwarding no
MaxAuthTries 3
AllowUsers <ο χρήστης σου>
```
```bash
sudo systemctl restart ssh
```

## 9. Αυτόματες ενημερώσεις ασφαλείας

```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
sudo timedatectl set-ntp true
```

## 10. Backup

`/etc/cron.daily/karagiaouris-backup`:
```bash
#!/bin/sh
set -e
DEST=/var/backups/karagiaouris/$(date +%F)
mkdir -p "$DEST"
sqlite3 /srv/karagiaouris/Database/db.sqlite3 ".backup '$DEST/db.sqlite3'"
tar czf "$DEST/protected_media.tar.gz" -C /srv/karagiaouris/Database protected_media
cp /srv/karagiaouris/.env "$DEST/env.backup"
chmod -R 600 "$DEST"
find /var/backups/karagiaouris -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
```

Το `.backup` του sqlite3 παίρνει συνεπές αντίγραφο με τον server σε λειτουργία —
η απλή `cp` μπορεί να δώσει χαλασμένο αρχείο.

**Δοκίμασε την επαναφορά.** Backup που δεν έχει δοκιμαστεί δεν είναι backup.
Κράτα και ένα αντίγραφο εκτός του server.

---

## Χρήσιμα μετά την εγκατάσταση

| Τι | Εντολή |
|---|---|
| Λογαριασμός κλειδώθηκε από το axes | `python manage.py axes_reset` |
| Δες τις αποτυχημένες συνδέσεις | `python manage.py axes_list_attempts` |
| Log ασφαλείας | `tail -f Database/logs/security.log` |
| Έλεγχος ρυθμίσεων | `python manage.py check --deploy` |
| Ευπάθειες σε πακέτα | `pip install pip-audit && pip-audit -r Backend/requirements.txt` |
