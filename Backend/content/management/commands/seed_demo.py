"""Create demo categories + announcements so the site isn't empty.

Usage: python manage.py seed_demo
Idempotent — safe to run more than once.
"""

from django.core.management.base import BaseCommand

from content.models import Announcement, Category, Section


class Command(BaseCommand):
    help = "Seed demo categories and announcements."

    def handle(self, *args, **options):
        structure = {
            Section.PANELLINIES: [
                ("Θέματα 2024", ["Στοιχεία Μηχανών", "Στοιχεία Σχεδιασμού"]),
                ("Θέματα 2023", []),
                ("Θέματα 2022", []),
            ],
            Section.ASKISEIS: [
                ("Ασκήσεις Αντοχής Υλικών", []),
                ("Εργασίες Θερμοδυναμικής", []),
            ],
            Section.EBOOKS: [
                ("Σχολικά βιβλία", []),
                ("Βοηθήματα", []),
            ],
            Section.XRISIMA: [
                ("Πίνακες & Τύποι", []),
                ("Χρήσιμοι σύνδεσμοι", []),
            ],
            Section.TRITOVATHMIA: [
                ("Πανεπιστήμια", []),
                ("Μηχανογραφικό & Βάσεις", []),
            ],
        }

        for section, roots in structure.items():
            for order, (name, children) in enumerate(roots):
                parent, _ = Category.objects.get_or_create(
                    name=name, section=section, parent=None, defaults={"order": order}
                )
                for c_order, child_name in enumerate(children):
                    Category.objects.get_or_create(
                        name=child_name, section=section, parent=parent,
                        defaults={"order": c_order},
                    )

        Announcement.objects.get_or_create(
            title="Καλωσορίσατε στη νέα ιστοσελίδα!",
            defaults={
                "content": "<p>Εδώ θα βρίσκετε παλιά θέματα, ασκήσεις, e-books και "
                "ανακοινώσεις. Καλή μελέτη!</p>",
                "published": True,
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo data created."))
