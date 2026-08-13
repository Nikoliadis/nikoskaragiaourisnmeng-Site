"""Import the links from ΙΣΤΟΣΕΛΙΔΑ.xlsx into the menu categories.

The workbook is the teacher's own map of the site: one sheet per section, a
column of subcategory headings, and the links that belong under each. Reading
it directly means he keeps editing the spreadsheet he already maintains and we
re-run this, rather than anyone retyping forty links into the admin.

    python manage.py import_links                 # add and update
    python manage.py import_links --prune         # also drop links no longer listed
    python manage.py import_links --file other.xlsx
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from content.models import Category, Link, Section

# Sheet name -> the Section it fills.
SHEETS = {
    "ΠΑΝΕΛΛΑΔΙΚΕΣ ΕΞΕΤΑΣΕΙΣ": Section.PANELLINIES,
    "ΒΙΒΛΙΑ ΕΠΑΛ": Section.EBOOKS,
    "ΕΠΑΓΓΕΛΜΑΤΙΚΑ ΛΥΚΕΙΑ": Section.ASKISEIS,
    "ΣΧΟΛΕΣ ΕΠΑΓΓΕΛΜ. ΚΑΤΑΡΤΙΣΗΣ": Section.XRISIMA,
    "ΤΡΙΤΟΒΑΘΜΙΑ ΕΚΠΑΙΔΕΥΣΗ": Section.TRITOVATHMIA,
}

# The workbook's headings do not always match the category names in the menu.
HEADING_TO_CATEGORY = {
    "ΘΕΜΑΤΑ ΚΑΙ ΑΠΑΝΤΗΣΕΙΣ": "ΘΕΜΑΤΑ - ΑΠΑΝΤΗΣΕΙΣ",
    "ΚΑΤΑΛΟΓΟΣ ΕΡΩΤΗΣΕΩΝ ΠΙΣΤΟΠΟΙΗΣΗΣ": "ΚΑΤΑΛΟΓΟΣ ΕΡΩΤΗΣΕΩΝ ΠΙΣΤΟΠΟΙΗΣΗΣ",
}


def clean(value) -> str:
    return " ".join(str(value).split()) if value else ""


def tidy_title(title: str, url: str) -> str:
    """Make the spreadsheet's labels read like titles rather than search results."""
    for tail in (" -Panellinies.net", " – Isalos.net", " | Τράπεζα Θεμάτων"):
        title = title.replace(tail, "")
    title = title.replace("Επαγγελματικό Λύκειο | Γ' ΤΑΞΗ | ", "")
    title = title.strip(" -–|")
    # A bare URL as the label helps nobody; fall back to the file name.
    if not title or title.startswith(("http", "ebooks.edu.gr", "e_j")):
        tail = [part for part in url.rstrip("/").split("/") if part]
        title = tail[-1].replace("_", " ").replace("-", " ") if tail else url
    return title[:250]


class Command(BaseCommand):
    help = "Import the links from ΙΣΤΟΣΕΛΙΔΑ.xlsx into the menu categories."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=None, help="Path to the workbook.")
        parser.add_argument(
            "--prune", action="store_true",
            help="Remove links that are no longer in the workbook.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without touching the database.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            import openpyxl
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise CommandError("openpyxl is required: pip install openpyxl") from exc

        path = Path(options["file"] or Path(__file__).resolve().parents[4] / "ΙΣΤΟΣΕΛΙΔΑ.xlsx")
        if not path.exists():
            raise CommandError(f"Workbook not found: {path}")

        workbook = openpyxl.load_workbook(path, data_only=True)
        kept, created, updated, skipped = set(), 0, 0, []

        for sheet_name, section in SHEETS.items():
            if sheet_name not in workbook.sheetnames:
                skipped.append(f"sheet «{sheet_name}» missing")
                continue

            sheet = workbook[sheet_name]
            category = None
            for row in sheet.iter_rows():
                heading = clean(row[1].value) if len(row) > 1 else ""
                if heading:
                    category = self._find_category(section, heading)
                    if category is None:
                        skipped.append(f"{sheet_name}: no category for «{heading}»")

                if len(row) < 3 or category is None:
                    continue
                cell = row[2]
                url = cell.hyperlink.target if cell.hyperlink else ""
                if not url or not url.startswith("http"):
                    continue  # a plain-text row, not a link

                title = tidy_title(clean(cell.value), url)
                link, was_created = Link.objects.get_or_create(
                    category=category, url=url,
                    defaults={"title": title, "order": cell.row},
                )
                kept.add(link.pk)
                if was_created:
                    created += 1
                    self.stdout.write(f"  + [{category.name}] {title}")
                elif link.title != title or not link.is_active:
                    link.title, link.is_active = title, True
                    link.save(update_fields=["title", "is_active"])
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n{created} new, {updated} updated, {len(kept)} links in total."
        ))
        for note in skipped:
            self.stdout.write(self.style.WARNING(f"  ! {note}"))

        if options["prune"]:
            gone = Link.objects.exclude(pk__in=kept)
            self.stdout.write(f"Removing {gone.count()} links no longer in the workbook.")
            gone.delete()

        if options["dry_run"]:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING("Dry run — nothing was saved."))

    def _find_category(self, section, heading):
        """Match a workbook heading to a menu category, tolerating case."""
        name = HEADING_TO_CATEGORY.get(heading, heading)
        return (
            Category.objects.filter(section=section, name__iexact=name).first()
            or Category.objects.filter(section=section, name__icontains=name).first()
        )
