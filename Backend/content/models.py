from pathlib import Path

from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .storage import protected_storage, uuid_upload_to
from .validators import validate_upload


class Section(models.TextChoices):
    """Top-level navbar sections a category can belong to."""

    PANELLINIES = "panellinies", _("ΠΑΝΕΛΛΑΔΙΚΕΣ ΕΞΕΤΑΣΕΙΣ")
    ASKISEIS = "askiseis", _("ΕΠΑΓΓΕΛΜΑΤΙΚΑ ΛΥΚΕΙΑ")
    EBOOKS = "ebooks", _("ΒΙΒΛΙΑ ΕΠΑΛ")
    XRISIMA = "xrisima", _("ΣΧΟΛΕΣ ΕΠΑΓΓΕΛΜΑΤΙΚΗΣ ΚΑΤΑΡΤΙΣΗΣ")
    TRITOVATHMIA = "tritovathmia", _("ΤΡΙΤΟΒΑΘΜΙΑ ΕΚΠΑΙΔΕΥΣΗ")


def greek_slugify(value: str) -> str:
    """Slug helper that keeps Greek text usable (allows unicode)."""
    return slugify(value, allow_unicode=True)


class Category(models.Model):
    name = models.CharField(_("Όνομα"), max_length=150)
    slug = models.SlugField(_("Slug"), max_length=170, unique=True, allow_unicode=True, blank=True)
    section = models.CharField(
        _("Ενότητα"),
        max_length=20,
        choices=Section.choices,
        help_text=_("Σε ποιο μενού της ιστοσελίδας ανήκει η κατηγορία."),
    )
    parent = models.ForeignKey(
        "self",
        verbose_name=_("Γονική κατηγορία"),
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
        help_text=_("Άφησέ το κενό για κατηγορία πρώτου επιπέδου."),
    )
    order = models.PositiveIntegerField(_("Σειρά"), default=0)
    is_active = models.BooleanField(_("Ενεργή"), default=True)

    class Meta:
        verbose_name = _("Κατηγορία")
        verbose_name_plural = _("Κατηγορίες")
        ordering = ["section", "order", "name"]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} › {self.name}"
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = greek_slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("content:category", args=[self.slug])


class Document(models.Model):
    title = models.CharField(_("Τίτλος"), max_length=200)
    description = models.TextField(_("Περιγραφή"), blank=True)
    category = models.ForeignKey(
        Category,
        verbose_name=_("Κατηγορία"),
        on_delete=models.PROTECT,
        related_name="documents",
    )
    file = models.FileField(
        _("Αρχείο"),
        storage=protected_storage,
        upload_to=uuid_upload_to,
        validators=[validate_upload],
        help_text=_("Επιτρεπτά: pdf, doc, docx, jpg, png. Μέγιστο 25 MB."),
    )
    # The real filename is kept here; on disk the file has a random UUID name.
    original_filename = models.CharField(_("Αρχικό όνομα"), max_length=255, blank=True)
    content_type = models.CharField(_("Τύπος MIME"), max_length=100, blank=True)
    size = models.PositiveBigIntegerField(_("Μέγεθος (bytes)"), default=0)
    uploaded_at = models.DateTimeField(_("Ημ/νία ανεβάσματος"), auto_now_add=True)
    is_active = models.BooleanField(_("Ορατό"), default=True)

    class Meta:
        verbose_name = _("Έγγραφο")
        verbose_name_plural = _("Έγγραφα / Υλικό")
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Capture the real filename and size from the freshly uploaded file.
        if self.file and hasattr(self.file, "file"):
            if not self.original_filename:
                self.original_filename = Path(self.file.name).name
            self.size = getattr(self.file, "size", self.size) or self.size
        super().save(*args, **kwargs)

    @property
    def extension(self) -> str:
        name = self.original_filename or self.file.name
        return Path(name).suffix.lower().lstrip(".")

    @property
    def size_display(self) -> str:
        size = float(self.size)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024

    def get_download_url(self):
        return reverse("content:download", args=[self.pk])


class Announcement(models.Model):
    title = models.CharField(_("Τίτλος"), max_length=200)
    slug = models.SlugField(_("Slug"), max_length=220, unique=True, allow_unicode=True, blank=True)
    content = models.TextField(_("Περιεχόμενο"))
    image = models.ImageField(
        _("Εικόνα"), upload_to="announcements/%Y/%m/", blank=True, null=True
    )
    published = models.BooleanField(_("Δημοσιευμένη"), default=True)
    created_at = models.DateTimeField(_("Ημ/νία δημιουργίας"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Ημ/νία ενημέρωσης"), auto_now=True)

    class Meta:
        verbose_name = _("Ανακοίνωση")
        verbose_name_plural = _("Ανακοινώσεις")
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = greek_slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("content:announcement", args=[self.slug])


class ContactMessage(models.Model):
    name = models.CharField(_("Όνομα"), max_length=120)
    email = models.EmailField(_("Email"))
    message = models.TextField(_("Μήνυμα"))
    created_at = models.DateTimeField(_("Ημ/νία"), auto_now_add=True)
    is_read = models.BooleanField(_("Αναγνωσμένο"), default=False)

    class Meta:
        verbose_name = _("Μήνυμα επικοινωνίας")
        verbose_name_plural = _("Μηνύματα επικοινωνίας")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — {self.created_at:%d/%m/%Y}"
