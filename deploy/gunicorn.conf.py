"""Gunicorn configuration.

Τρέξιμο:  gunicorn -c deploy/gunicorn.conf.py config.wsgi:application
(από τον φάκελο Backend/)
"""

import multiprocessing

# --- Δικτύωση --------------------------------------------------------------
# Unix socket, όχι TCP: κανείς δεν μπορεί να παρακάμψει τον nginx και να
# χτυπήσει απευθείας το Django (και άρα τα rate limits και το TLS).
bind = "unix:/run/gunicorn/karagiaouris.sock"
umask = 0o007  # ο socket προσβάσιμος μόνο από τον χρήστη και το group του nginx

# --- Workers ---------------------------------------------------------------
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
threads = 2

# Ανακύκλωση workers: περιορίζει τη ζημιά από διαρροή μνήμης ή από worker που
# έχει "μολυνθεί" με κακή κατάσταση. Το jitter αποτρέπει ταυτόχρονο restart.
max_requests = 1000
max_requests_jitter = 100

# --- Χρονικά όρια ----------------------------------------------------------
timeout = 60          # ο nginx έχει proxy_read_timeout 60s
graceful_timeout = 30
keepalive = 5

# --- Όρια αιτημάτων (άμυνα σε κακόβουλα headers) ---------------------------
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# --- Logging ---------------------------------------------------------------
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"
# Καταγράφουμε την πραγματική IP του επισκέπτη, όχι του nginx.
access_log_format = '%({X-Forwarded-For}i)s %(t)s "%(r)s" %(s)s %(b)s %(D)sus "%(a)s"'
# Ο κατάλογος με τα forwarded headers που εμπιστευόμαστε: μόνο ο τοπικός nginx.
forwarded_allow_ips = "127.0.0.1"

# --- Διεργασία -------------------------------------------------------------
proc_name = "karagiaouris"
preload_app = True    # μοιράζεται μνήμη μεταξύ workers, γρηγορότερη εκκίνηση
# Ο χρήστης/group ορίζονται από το systemd unit, όχι εδώ.
