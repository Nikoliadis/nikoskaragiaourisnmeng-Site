"""Create the site's menu structure exactly as the teacher specified it.

Usage:
    python manage.py setup_menu            # create/update, touch nothing else
    python manage.py setup_menu --prune    # also remove categories not listed here

Idempotent — safe to run more than once. Existing categories are matched by
name within their section, so re-running never duplicates them and never
touches the documents filed under them.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import ProtectedError

from content.models import Category, Section

# section -> [(root category, [subcategories])] in menu order.
MENU = {
    Section.PANELLINIES: [
        ("ΘΕΜΑΤΑ - ΑΠΑΝΤΗΣΕΙΣ", []),
        ("ΑΝΑΚΟΙΝΩΣΕΙΣ", []),
    ],
    Section.EBOOKS: [
        ("ΝΑΥΤΙΚΟΥ ΤΟΜΕΑ", []),
        ("ΜΗΧΑΝΟΛΟΓΙΚΟΥ ΤΟΜΕΑ", []),
        ("ΗΛΕΚΤΡΟΛΟΓΙΚΟΥ ΤΟΜΕΑ", []),
        ("ΓΕΝΙΚΗΣ ΠΑΙΔΕΙΑΣ", []),
    ],
    Section.ASKISEIS: [
        ("ΠΡΟΓΡΑΜΜΑΤΑ ΣΠΟΥΔΩΝ", []),
        ("ΤΡΑΠΕΖΑ ΘΕΜΑΤΩΝ", []),
        ("ΜΑΘΗΜΑΤΑ ΕΝΔΟΣΧΟΛΙΚΩΝ ΕΞΕΤΑΣΕΩΝ", []),
    ],
    Section.XRISIMA: [
        ("ΕΟΠΠΕΠ", []),
        ("ΚΑΤΑΛΟΓΟΣ ΕΡΩΤΗΣΕΩΝ ΠΙΣΤΟΠΟΙΗΣΗΣ", []),
    ],
    Section.TRITOVATHMIA: [
        ("ΠΑΝΕΠΙΣΤΗΜΙΑ", ["ΠΡΟΠΤΥΧΙΑΚΑ", "ΜΕΤΑΠΤΥΧΙΑΚΑ"]),
        ("ΑΚΑΔΗΜΙΕΣ ΕΜΠΟΡΙΚΟΥ ΝΑΥΤΙΚΟΥ", []),
    ],
}


class Command(BaseCommand):
    help = "Create the menu categories and subcategories of the site."

    def add_arguments(self, parser):
        parser.add_argument(
            "--prune",
            action="store_true",
            help=(
                "Delete categories that are not part of the menu above. "
                "Categories holding documents are always kept."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        keep = set()

        for section, roots in MENU.items():
            for order, (name, children) in enumerate(roots):
                parent = self._upsert(name, section, None, order)
                keep.add(parent.pk)
                for child_order, child_name in enumerate(children):
                    child = self._upsert(child_name, section, parent, child_order)
                    keep.add(child.pk)

        self.stdout.write(self.style.SUCCESS(f"Menu ready — {len(keep)} categories."))

        if options["prune"]:
            self._prune(keep)
        else:
            extra = Category.objects.exclude(pk__in=keep).count()
            if extra:
                self.stdout.write(
                    f"{extra} categories are not part of the menu. "
                    f"Re-run with --prune to remove them."
                )

    def _upsert(self, name, section, parent, order):
        category, created = Category.objects.get_or_create(
            name=name,
            section=section,
            parent=parent,
            defaults={"order": order, "is_active": True},
        )
        if not created and (category.order != order or not category.is_active):
            category.order = order
            category.is_active = True
            category.save(update_fields=["order", "is_active"])
        self.stdout.write(f"  {'+' if created else '='} {category}")
        return category

    def _prune(self, keep):
        # Children first: deleting a parent cascades, and a cascade that reaches
        # a category with documents would roll back the whole delete.
        leftovers = sorted(
            Category.objects.exclude(pk__in=keep),
            key=lambda category: category.parent_id is None,
        )
        removed, kept = 0, []
        for category in leftovers:
            if not Category.objects.filter(pk=category.pk).exists():
                continue  # already removed by a parent's cascade
            try:
                with transaction.atomic():
                    category.delete()
            except ProtectedError:
                kept.append(category)
            else:
                removed += 1
                self.stdout.write(f"  - {category}")

        self.stdout.write(self.style.SUCCESS(f"Removed {removed} categories."))
        for category in kept:
            self.stdout.write(
                self.style.WARNING(
                    f"  ! kept «{category}» — it still holds documents. "
                    f"Move or delete them from the admin first."
                )
            )
