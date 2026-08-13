"""Tests for upload validation, protected downloads and slug generation.

Uploads are written to a throwaway PROTECTED_MEDIA_ROOT so a test run never
touches the real protected_media/ directory.
"""

import re
import shutil
import tempfile
from io import StringIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .management.commands.setup_menu import MENU
from .models import Announcement, Category, ContactMessage, Document, Section
from .validators import detect_content_type, validate_filename, validate_upload

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


class SecurityHeaderTests(TestCase):
    def test_public_page_carries_a_strict_csp(self):
        csp = self.client.get(reverse("content:home"))["Content-Security-Policy"]

        self.assertIn("default-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("base-uri 'none'", csp)
        # No inline scripts and no external origin may execute anything.
        self.assertIn("script-src 'self'", csp)
        self.assertNotIn("unsafe-inline", csp.split("style-src")[0])
        self.assertNotIn("http://", csp.replace("upgrade-insecure-requests", ""))

    def test_admin_gets_its_own_policy_but_still_same_origin(self):
        csp = self.client.get("/admin/login/", follow=True)["Content-Security-Policy"]

        self.assertIn("'unsafe-inline'", csp)  # unfold needs it
        self.assertIn("default-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)

    def test_other_security_headers(self):
        response = self.client.get(reverse("content:home"))

        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin")
        self.assertEqual(response["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertIn("camera=()", response["Permissions-Policy"])
        self.assertIn("geolocation=()", response["Permissions-Policy"])

    def test_no_page_loads_anything_from_a_third_party_origin(self):
        html = self.client.get(reverse("content:home")).content.decode()

        for host in ("googleapis.com", "gstatic.com", "unpkg.com", "cdn."):
            with self.subTest(host=host):
                self.assertNotIn(host, html)

    def test_session_cookie_is_not_reachable_from_javascript(self):
        from django.conf import settings

        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Strict")

    def test_argon2_is_the_default_password_hasher(self):
        from django.contrib.auth.hashers import make_password

        self.assertTrue(make_password("a-long-enough-passphrase").startswith("argon2"))


class StaticAssetTests(TestCase):
    """Every asset a template asks for must actually exist.

    Regression: the js/ folder and favicon.ico went missing from disk. Nothing
    failed loudly — the pages still rendered, the browser just 404'd on the
    scripts, so the theme switch, the dropdowns and the slideshow all quietly
    stopped working. This turns that into a failing test instead.
    """

    def test_every_static_reference_resolves(self):
        import re

        from django.conf import settings
        from django.contrib.staticfiles import finders

        pattern = re.compile(r"{%\s*static\s*['\"]([^'\"]+)['\"]\s*%}")
        referenced = set()
        for template_dir in settings.TEMPLATES[0]["DIRS"]:
            for path in Path(template_dir).rglob("*.html"):
                referenced.update(pattern.findall(path.read_text(encoding="utf-8")))

        self.assertTrue(referenced, "no {% static %} references found — bad glob?")
        missing = [name for name in sorted(referenced) if finders.find(name) is None]
        self.assertEqual(missing, [], f"static files referenced but not on disk: {missing}")

    def test_the_scripts_the_pages_depend_on_are_present(self):
        from django.contrib.staticfiles import finders

        for name in ("js/theme.js", "js/site.js", "js/hero.js", "js/htmx.min.js"):
            with self.subTest(name=name):
                self.assertIsNotNone(finders.find(name), f"{name} is missing")


class InteractionTests(ProtectedMediaTestCase):
    """Markup the front-end behaviour depends on."""

    def make_documents(self, how_many=3):
        category = Category.objects.create(name="Θέματα", section=Section.PANELLINIES)
        for index in range(how_many):
            Document.objects.create(
                title=f"Αρχείο {index}", category=category,
                file=upload(f"a{index}.pdf", PDF_BYTES),
            )
        return category

    def test_download_links_opt_out_of_boosted_navigation(self):
        """A boosted link fetches into JS — the visitor would get no file."""
        category = self.make_documents(1)
        html = self.client.get(category.get_absolute_url()).content.decode()

        for match in re.finditer(r"<a\b[^>]*/lipsi/\d+/[^>]*>", html):
            with self.subTest(tag=match.group()):
                self.assertIn('hx-boost="false"', match.group())

    def test_material_pages_carry_the_filter_markup(self):
        category = self.make_documents(3)
        for url in (category.get_absolute_url(),
                    reverse("content:section", args=[Section.PANELLINIES])):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, "data-filter-input")
                self.assertContains(response, "data-filter-list")
                self.assertContains(response, "data-filter-item")

    def test_the_filter_box_is_hidden_until_javascript_reveals_it(self):
        category = self.make_documents(1)
        html = self.client.get(category.get_absolute_url()).content.decode()

        match = re.search(r'<div data-filter class="([^"]*)"', html)
        self.assertIsNotNone(match, "filter wrapper not found")
        self.assertIn("hidden", match.group(1))

    def test_a_category_without_documents_offers_no_filter(self):
        empty = Category.objects.create(name="Άδεια", section=Section.EBOOKS)
        self.assertNotContains(self.client.get(empty.get_absolute_url()), "data-filter-input")

    def test_pages_are_boosted_and_carry_the_progress_bar(self):
        html = self.client.get(reverse("content:home")).content.decode()

        self.assertIn('hx-boost="true"', html)
        self.assertIn('id="page-progress"', html)
        self.assertIn('id="back-to-top"', html)

    def test_recently_added_material_appears_on_the_home_page(self):
        category = self.make_documents(8)
        newest = Document.objects.create(
            title="Ολοκαίνουριο", category=category, file=upload("new.pdf", PDF_BYTES)
        )
        response = self.client.get(reverse("content:home"))

        self.assertContains(response, "Πρόσφατο υλικό")
        self.assertContains(response, newest.title)
        # Six at most, newest first.
        self.assertEqual(len(response.context["recent_documents"]), 6)
        self.assertEqual(response.context["recent_documents"][0], newest)

    def test_hidden_documents_stay_off_the_home_page(self):
        category = self.make_documents(1)
        doc = Document.objects.get(category=category)
        Document.objects.filter(pk=doc.pk).update(is_active=False)

        self.assertNotContains(self.client.get(reverse("content:home")), doc.title)

    def test_feedback_affordances_are_present(self):
        home = self.client.get(reverse("content:home")).content.decode()
        contact = self.client.get(reverse("content:contact")).content.decode()

        # Downloads are silent, so the click needs a confirmation to land in.
        self.assertIn('id="toast-area"', home)
        self.assertIn('aria-live="polite"', home)
        # The submit button shows it is working instead of looking ignored.
        self.assertIn("btn-spinner", contact)

    def test_icon_only_controls_explain_themselves(self):
        html = self.client.get(reverse("content:home")).content.decode()

        for tag in re.finditer(r"<(?:a|button)\b[^>]*data-tip=[^>]*>", html):
            with self.subTest(tag=tag.group()[:70]):
                # A tooltip is not a substitute for a name a screen reader reads.
                self.assertIn("aria-label=", tag.group())

    def test_content_is_visible_without_javascript(self):
        """no-js on <html> keeps revealed elements from staying invisible."""
        html = self.client.get(reverse("content:home")).content.decode()
        self.assertRegex(html, r"<html[^>]*\bno-js\b")


class ProfileTests(TestCase):
    def test_page_shows_the_professional_history(self):
        response = self.client.get(reverse("content:profile"))

        self.assertEqual(response.status_code, 200)
        for fact in (
            "Ελληνικά Ναυπηγεία",
            "Φροντιστήρια Πουκαμισάς",
            "ΙΕΚ ΑΚΜΗ",
            "Ναυπηγική",
            "Μηχανολογία",
            "AutoCAD",
        ):
            with self.subTest(fact=fact):
                self.assertContains(response, fact)

    def test_private_details_from_the_cv_are_never_published(self):
        """Guards against someone later pasting the CV in wholesale.

        A home address, mobile number, date of birth and registry numbers on a
        public page are what identity theft is built from, and students have no
        use for them.
        """
        response = self.client.get(reverse("content:profile"))
        body = response.content.decode()

        for private in (
            "Αγίου Ελευθερίου",   # home address
            "18541",              # postcode
            "6972418502",         # mobile
            "2104828138",         # landline
            "23-03-1976",         # date of birth
            "10100066997",        # military registry number
            "35334",              # teaching licence number
            "6,45", "7,09", "8,98",  # degree marks
        ):
            with self.subTest(private=private):
                self.assertNotIn(private, body)

    def test_the_profile_is_reachable_from_the_rest_of_the_site(self):
        url = reverse("content:profile")
        for page in (reverse("content:home"), reverse("content:contact")):
            with self.subTest(page=page):
                self.assertContains(self.client.get(page), f'href="{url}"')


class SocialAndSharingTests(TestCase):
    ACCOUNTS = (
        "https://www.instagram.com/nick_vehicle_dynamics/",
        "https://www.tiktok.com/@nikos.vehicle.dyn",
    )

    def test_social_links_open_safely_in_a_new_tab(self):
        html = self.client.get(reverse("content:home")).content.decode()

        for url in self.ACCOUNTS:
            with self.subTest(url=url):
                self.assertIn(url, html)
        # rel=noopener stops the opened page reaching back into this one.
        for match in re.finditer(r'<a[^>]+(?:instagram|tiktok)\.com[^>]*>', html):
            with self.subTest(tag=match.group()[:80]):
                self.assertIn('target="_blank"', match.group())
                self.assertIn("noopener", match.group())
                self.assertIn("noreferrer", match.group())

    def test_pages_carry_an_open_graph_preview(self):
        response = self.client.get(reverse("content:home"))

        for tag in ('property="og:title"', 'property="og:description"',
                    'property="og:image"', 'property="og:url"',
                    'name="twitter:card"'):
            with self.subTest(tag=tag):
                self.assertContains(response, tag)

    def test_the_preview_image_exists(self):
        from django.contrib.staticfiles import finders

        self.assertIsNotNone(finders.find("img/og-preview.jpg"))


class ThemeTests(TestCase):
    """Light/dark switching. The theme itself is CSS, so these guard the wiring."""

    def test_theme_script_loads_before_the_page_is_painted(self):
        html = self.client.get(reverse("content:home")).content.decode()
        head = html.split("</head>")[0]

        self.assertIn("js/theme.js", head)
        # Deferring it would let the page paint in the wrong theme first.
        script = head[head.index("js/theme.js") - 60 : head.index("js/theme.js") + 40]
        self.assertNotIn("defer", script)

    def test_every_page_offers_the_toggle(self):
        for url in (
            reverse("content:home"),
            reverse("content:contact"),
            reverse("content:announcements"),
            reverse("content:section", args=[Section.EBOOKS]),
        ):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), "data-theme-toggle")

    def test_toggle_carries_both_icons_for_css_to_choose_from(self):
        html = self.client.get(reverse("content:home")).content.decode()

        self.assertIn("dark_mode", html)
        self.assertIn("light_mode", html)

    def test_theme_colour_meta_is_declared_for_both_schemes(self):
        html = self.client.get(reverse("content:home")).content.decode()

        self.assertIn('media="(prefers-color-scheme: light)"', html)
        self.assertIn('media="(prefers-color-scheme: dark)"', html)


class SanitisingTests(TestCase):
    def test_script_in_announcement_body_is_stripped_on_save(self):
        announcement = Announcement.objects.create(
            title="Κακόβουλη",
            content='<p>Γεια</p><script>alert(document.cookie)</script>',
        )
        announcement.refresh_from_db()

        self.assertNotIn("<script", announcement.content)
        self.assertIn("<p>Γεια</p>", announcement.content)

    def test_event_handlers_and_javascript_urls_are_stripped(self):
        announcement = Announcement.objects.create(
            title="Κλικ",
            content='<a href="javascript:alert(1)" onclick="alert(2)">κλικ</a>'
            '<img src="x" onerror="alert(3)">',
        )

        self.assertNotIn("javascript:", announcement.content)
        self.assertNotIn("onclick", announcement.content)
        self.assertNotIn("onerror", announcement.content)

    def test_ordinary_formatting_survives(self):
        announcement = Announcement.objects.create(
            title="Κανονική",
            content="<p><strong>Έντονα</strong> και <em>πλάγια</em></p><ul><li>ένα</li></ul>",
        )

        self.assertIn("<strong>Έντονα</strong>", announcement.content)
        self.assertIn("<li>ένα</li>", announcement.content)

    def test_rendered_page_contains_no_script_tag(self):
        announcement = Announcement.objects.create(
            title="Σελίδα", content='<p>ok</p><script>alert(1)</script>'
        )
        response = self.client.get(announcement.get_absolute_url())

        self.assertNotContains(response, "<script>alert")


class UploadHardeningTests(TestCase):
    def test_html_renamed_to_pdf_is_rejected(self):
        """Regression: unsniffable content used to pass the MIME check."""
        payload = b"<html><script>alert(1)</script></html>"
        with self.assertRaises(ValidationError):
            validate_upload(upload("notes.pdf", payload))

    def test_doc_without_magic_bytes_is_still_allowed(self):
        validate_upload(upload("palio.doc", b"some legacy word bytes" * 5))

    def test_directory_parts_never_survive_an_upload(self):
        """Django strips them first; assert it, so a regression is visible."""
        for name in ("../../etc/passwd.pdf", "a/b.pdf", "a\\b.pdf"):
            with self.subTest(name=name):
                uploaded = upload(name, PDF_BYTES)
                self.assertNotIn("/", uploaded.name)
                self.assertNotIn("\\", uploaded.name)
                validate_upload(uploaded)  # the sanitised name is fine

    def test_filename_that_could_forge_a_response_header_is_rejected(self):
        # This name is echoed back in Content-Disposition on download.
        for name in ('a"; filename="evil.pdf', "line\r\nInjected: 1.pdf", "a\x00b.pdf"):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                validate_filename(upload(name, PDF_BYTES))

    def test_stored_path_stays_inside_the_protected_root(self):
        with override_settings(PROTECTED_MEDIA_ROOT=_TMP_MEDIA):
            category = Category.objects.create(name="Β", section=Section.EBOOKS)
            doc = Document.objects.create(
                title="Δ", category=category, file=upload("../../escape.png", PNG_BYTES)
            )
            stored = Path(doc.file.path).resolve()

            self.assertTrue(stored.is_relative_to(Path(_TMP_MEDIA).resolve()))

    def test_download_response_cannot_be_rendered_in_the_browser(self):
        settings_override = override_settings(PROTECTED_MEDIA_ROOT=_TMP_MEDIA)
        settings_override.enable()
        try:
            category = Category.objects.create(name="Α", section=Section.EBOOKS)
            doc = Document.objects.create(
                title="Δ", category=category, file=upload("a.png", PNG_BYTES)
            )
            response = self.client.get(doc.get_download_url())

            self.assertIn("attachment", response["Content-Disposition"])
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            self.assertIn("sandbox", response["Content-Security-Policy"])
        finally:
            settings_override.disable()


class ContactRateLimitTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_flood_is_throttled(self):
        payload = {"name": "Α", "email": "a@b.gr", "message": "γεια"}
        accepted = 0
        for _unused in range(8):
            response = self.client.post(reverse("content:contact"), payload)
            if response.status_code == 302 and ContactMessage.objects.count() > accepted:
                accepted += 1

        self.assertEqual(accepted, 5)
        self.assertEqual(ContactMessage.objects.count(), 5)

    def test_a_message_is_emailed_to_the_superuser(self):
        from django.contrib.auth import get_user_model
        from django.core import mail

        get_user_model().objects.create_superuser(
            "karag", "nikoskarag08@example.gr", "a-long-enough-passphrase"
        )
        self.client.post(
            reverse("content:contact"),
            {"name": "Μαθητής", "email": "mathitis@example.com", "message": "Γεια σας!"},
        )

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["nikoskarag08@example.gr"])
        # Replying answers the student, not the server.
        self.assertEqual(sent.reply_to, ["mathitis@example.com"])
        self.assertIn("Μαθητής", sent.subject)
        self.assertIn("Γεια σας!", sent.body)

    def test_submission_still_succeeds_when_the_mail_server_fails(self):
        from unittest.mock import patch

        from django.contrib.auth import get_user_model

        get_user_model().objects.create_superuser(
            "karag", "k@example.gr", "a-long-enough-passphrase"
        )
        with patch(
            "content.notifications.EmailMessage.send", side_effect=OSError("smtp down")
        ):
            response = self.client.post(
                reverse("content:contact"),
                {"name": "Α", "email": "a@b.gr", "message": "γεια"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContactMessage.objects.count(), 1)  # not lost

    def test_no_recipient_configured_is_survivable(self):
        from django.core import mail

        response = self.client.post(
            reverse("content:contact"),
            {"name": "Α", "email": "a@b.gr", "message": "γεια"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_honeypot_field_blocks_the_message(self):
        self.client.post(
            reverse("content:contact"),
            {"name": "Bot", "email": "b@b.gr", "message": "spam", "website": "http://x"},
        )
        self.assertEqual(ContactMessage.objects.count(), 0)


class MenuTests(TestCase):
    """The navbar structure the teacher specified."""

    def setUp(self):
        call_command("setup_menu", stdout=StringIO())

    def test_sections_are_in_menu_order(self):
        self.assertEqual(
            list(Section.values),
            ["panellinies", "ebooks", "askiseis", "xrisima", "tritovathmia"],
        )

    def test_command_creates_the_whole_tree(self):
        expected = sum(1 + len(children) for roots in MENU.values() for _, children in roots)
        self.assertEqual(Category.objects.count(), expected)

        for section, roots in MENU.items():
            for order, (name, children) in enumerate(roots):
                with self.subTest(section=section, name=name):
                    parent = Category.objects.get(name=name, section=section, parent=None)
                    self.assertEqual(parent.order, order)
                    self.assertTrue(parent.is_active)
                    self.assertEqual(
                        list(parent.children.order_by("order").values_list("name", flat=True)),
                        children,
                    )

    def test_running_twice_changes_nothing(self):
        before = set(Category.objects.values_list("pk", flat=True))
        call_command("setup_menu", stdout=StringIO())
        self.assertEqual(set(Category.objects.values_list("pk", flat=True)), before)

    def test_prune_removes_strays_but_keeps_categories_holding_documents(self):
        stray = Category.objects.create(name="Παλιά κατηγορία", section=Section.EBOOKS)
        with_file = Category.objects.create(name="Με αρχείο", section=Section.EBOOKS)
        Document.objects.create(title="Κρατημένο", category=with_file, file="2020/01/x.pdf")

        call_command("setup_menu", "--prune", stdout=StringIO())

        self.assertFalse(Category.objects.filter(pk=stray.pk).exists())
        self.assertTrue(Category.objects.filter(pk=with_file.pk).exists())

    def test_navbar_lists_sections_subcategories_and_grandchildren(self):
        response = self.client.get(reverse("content:home"))

        for section, roots in MENU.items():
            self.assertContains(response, Section(section).label)
            for name, children in roots:
                with self.subTest(name=name):
                    self.assertContains(response, name)
                    for child in children:
                        self.assertContains(response, child)

    def test_every_menu_category_page_opens(self):
        for category in Category.objects.all():
            with self.subTest(category=str(category)):
                self.assertEqual(
                    self.client.get(category.get_absolute_url()).status_code, 200
                )
