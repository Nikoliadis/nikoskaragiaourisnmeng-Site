"""Tests for upload validation, protected downloads and slug generation.

Uploads are written to a throwaway PROTECTED_MEDIA_ROOT so a test run never
touches the real protected_media/ directory.
"""

import shutil
import tempfile
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Announcement, Category, Document, Section
from .validators import detect_content_type, validate_upload

# Minimal payloads whose magic bytes are what `filetype` sniffs.
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF_BYTES = b"%PDF-1.4\n" + b"0" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64
EXE_BYTES = b"MZ\x90\x00" + b"\x00" * 64

_TMP_MEDIA = tempfile.mkdtemp(prefix="test-protected-media-")


def upload(name, payload=PNG_BYTES, content_type="application/octet-stream"):
    return SimpleUploadedFile(name, payload, content_type=content_type)


@override_settings(PROTECTED_MEDIA_ROOT=_TMP_MEDIA)
class ProtectedMediaTestCase(TestCase):
    """Base case that isolates and cleans up uploaded files."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TMP_MEDIA, ignore_errors=True)

    def make_document(self, title="Δοκιμή", filename="άσκηση 1.png", **kwargs):
        category = kwargs.pop("category", None) or Category.objects.create(
            name=f"Κατηγορία {title}", section=Section.ASKISEIS
        )
        return Document.objects.create(
            title=title, category=category, file=upload(filename, **kwargs)
        )


class UploadValidatorTests(TestCase):
    def test_accepts_whitelisted_types(self):
        for name, payload in (
            ("themata.pdf", PDF_BYTES),
            ("askisi.png", PNG_BYTES),
            ("foto.jpg", JPEG_BYTES),
        ):
            with self.subTest(name=name):
                validate_upload(upload(name, payload))  # must not raise

    def test_rejects_extension_outside_whitelist(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_upload(upload("script.exe", EXE_BYTES))
        self.assertIn(".exe", str(ctx.exception))

    @override_settings(MAX_UPLOAD_SIZE=100)
    def test_rejects_file_over_size_limit(self):
        with self.assertRaises(ValidationError):
            validate_upload(upload("big.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 500))

    def test_rejects_extension_that_contradicts_magic_bytes(self):
        """An .exe renamed to .pdf must not get through."""
        with self.assertRaises(ValidationError):
            validate_upload(upload("malware.pdf", EXE_BYTES))

    def test_leaves_read_position_untouched(self):
        """Sniffing must not consume the stream Django is about to save."""
        uploaded = upload("themata.pdf", PDF_BYTES)
        validate_upload(uploaded)
        self.assertEqual(uploaded.tell(), 0)
        self.assertEqual(uploaded.read(), PDF_BYTES)

    def test_content_type_ignores_browser_supplied_value(self):
        uploaded = upload("themata.pdf", PDF_BYTES, content_type="text/html")
        self.assertEqual(detect_content_type(uploaded), "application/pdf")

    def test_docx_content_type_is_not_the_sniffed_zip_type(self):
        # filetype sniffs a .docx container as application/zip; the stored type
        # should still be the canonical Word type.
        uploaded = upload("ergasia.docx", b"PK\x03\x04" + b"\x00" * 64)
        self.assertEqual(
            detect_content_type(uploaded),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )


class DocumentSaveTests(ProtectedMediaTestCase):
    def test_upload_metadata_is_recorded(self):
        doc = self.make_document(filename="άσκηση 1.png", content_type="text/html")
        self.assertEqual(doc.original_filename, "άσκηση 1.png")
        self.assertEqual(doc.size, len(PNG_BYTES))
        self.assertEqual(doc.content_type, "image/png")  # not the browser's claim
        self.assertEqual(doc.extension, "png")

    def test_file_is_stored_under_a_random_name(self):
        doc = self.make_document(filename="άσκηση 1.png")
        stored = Path(doc.file.name).name
        self.assertNotIn("άσκηση", stored)
        self.assertRegex(stored, r"^[0-9a-f]{32}\.png$")

    def test_resave_without_new_upload_keeps_metadata(self):
        doc = self.make_document()
        original_name, size = doc.original_filename, doc.size

        doc.title = "Νέος τίτλος"
        doc.save()

        doc.refresh_from_db()
        self.assertEqual(doc.original_filename, original_name)
        self.assertEqual(doc.size, size)

    def test_resave_works_when_the_file_is_missing_from_disk(self):
        """Editing a record whose file vanished must not raise FileNotFoundError."""
        doc = self.make_document()
        Path(doc.file.path).unlink()

        doc.title = "Μετονομασμένο"
        doc.save()  # regression: used to blow up opening the missing file

        doc.refresh_from_db()
        self.assertEqual(doc.title, "Μετονομασμένο")


class DownloadViewTests(ProtectedMediaTestCase):
    def test_serves_the_file_under_its_real_name(self):
        doc = self.make_document(filename="άσκηση 1.png")
        response = self.client.get(doc.get_download_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), PNG_BYTES)
        self.assertEqual(response["Content-Type"], "image/png")
        disposition = response["Content-Disposition"]
        self.assertIn("attachment", disposition)
        # Non-ASCII names travel RFC 5987-encoded.
        self.assertIn("filename*=utf-8''", disposition)

    def test_hidden_document_is_not_downloadable(self):
        doc = self.make_document()
        Document.objects.filter(pk=doc.pk).update(is_active=False)
        self.assertEqual(self.client.get(doc.get_download_url()).status_code, 404)

    def test_missing_file_returns_404_not_a_server_error(self):
        doc = self.make_document()
        Path(doc.file.path).unlink()
        self.assertEqual(self.client.get(doc.get_download_url()).status_code, 404)

    def test_unknown_document_returns_404(self):
        url = reverse("content:download", args=[999])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_documents_have_no_public_media_url(self):
        """The only route to a file is the download view."""
        doc = self.make_document()
        stored = Path(doc.file.name).name
        self.assertEqual(Client().get(f"/media/{stored}").status_code, 404)


class SlugTests(TestCase):
    def test_same_category_name_in_two_sections(self):
        first = Category.objects.create(name="Θέματα 2024", section=Section.PANELLINIES)
        second = Category.objects.create(name="Θέματα 2024", section=Section.EBOOKS)

        self.assertEqual(first.slug, "θέματα-2024")
        self.assertEqual(second.slug, "θέματα-2024-2")
        self.assertNotEqual(first.get_absolute_url(), second.get_absolute_url())

    def test_third_collision_keeps_counting(self):
        for _ in range(3):
            Category.objects.create(name="Ασκήσεις", section=Section.ASKISEIS)
        self.assertEqual(
            sorted(Category.objects.values_list("slug", flat=True)),
            ["ασκήσεις", "ασκήσεις-2", "ασκήσεις-3"],
        )

    def test_name_without_slugable_characters_still_yields_a_url(self):
        category = Category.objects.create(name="???", section=Section.EBOOKS)

        self.assertTrue(category.slug)
        # Regression: an empty slug made reverse() raise on every page that
        # renders the navbar, not just this category's own page.
        self.assertEqual(category.get_absolute_url(), "/kateigoria/category/")
        self.assertEqual(self.client.get(category.get_absolute_url()).status_code, 200)

    def test_editing_a_category_keeps_its_slug(self):
        category = Category.objects.create(name="Θέματα 2024", section=Section.EBOOKS)
        category.name = "Θέματα 2025"
        category.save()
        self.assertEqual(category.slug, "θέματα-2024")

    def test_duplicate_announcement_titles(self):
        first = Announcement.objects.create(title="Ενημέρωση", content="α")
        second = Announcement.objects.create(title="Ενημέρωση", content="β")

        self.assertEqual(first.slug, "ενημέρωση")
        self.assertEqual(second.slug, "ενημέρωση-2")
        self.assertEqual(self.client.get(second.get_absolute_url()).status_code, 200)

    def test_long_name_stays_within_the_field_limit(self):
        max_length = Category._meta.get_field("slug").max_length
        for _ in range(2):
            Category.objects.create(name="Θ" * 300, section=Section.EBOOKS)

        for slug in Category.objects.values_list("slug", flat=True):
            self.assertLessEqual(len(slug), max_length)
        self.assertEqual(Category.objects.count(), 2)


class PageTests(TestCase):
    def test_every_section_has_a_home_page_card(self):
        response = self.client.get(reverse("content:home"))
        self.assertEqual(response.status_code, 200)

        cards = response.context["cards"]
        self.assertEqual([c["section"] for c in cards], list(Section.values))
        for value, label in Section.choices:
            with self.subTest(section=value):
                self.assertContains(response, label)

    def test_public_pages_render(self):
        Category.objects.create(name="Θέματα 2024", section=Section.PANELLINIES)
        urls = [
            reverse("content:home"),
            reverse("content:announcements"),
            reverse("content:contact"),
            *(reverse("content:section", args=[value]) for value in Section.values),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_unknown_section_is_404(self):
        self.assertEqual(self.client.get("/kati-allo/").status_code, 404)
