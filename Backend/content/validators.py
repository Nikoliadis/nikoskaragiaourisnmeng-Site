"""Upload validation: extension whitelist, size limit, and MIME sniffing.

We never trust the browser-supplied content type. Instead we read the file's
magic bytes with `filetype` (pure-Python, works on Windows without libmagic)
and require the sniffed MIME to match the declared extension.
"""

from pathlib import Path

import filetype
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def file_extension(name: str) -> str:
    return Path(name).suffix.lower().lstrip(".")


def sniff_mimetype(uploaded_file) -> str | None:
    """Return the MIME type read from the file's magic bytes, or None.

    Leaves the file's read position where it found it, so callers can run this
    before Django streams the upload to storage.
    """
    pos = uploaded_file.tell()
    header = uploaded_file.read(262)  # filetype needs at most 262 bytes
    uploaded_file.seek(pos)

    kind = filetype.guess(header)
    return kind.mime if kind else None


def detect_content_type(uploaded_file) -> str:
    """The MIME type to store for an upload that has already been validated.

    Prefer the canonical type for the extension — validation has already
    confirmed the magic bytes agree with it, and it avoids storing the generic
    `application/zip` that a .docx sniffs as. The browser-supplied
    Content-Type is never consulted.
    """
    ext = file_extension(uploaded_file.name)
    canonical = settings.CANONICAL_UPLOAD_MIME.get(ext)
    return canonical or sniff_mimetype(uploaded_file) or "application/octet-stream"


def validate_file_extension(uploaded_file):
    ext = file_extension(uploaded_file.name)
    allowed = settings.ALLOWED_UPLOAD_TYPES
    if ext not in allowed:
        raise ValidationError(
            _("Μη επιτρεπτός τύπος αρχείου «.%(ext)s». Επιτρέπονται: %(allowed)s."),
            params={"ext": ext, "allowed": ", ".join(sorted(allowed))},
        )


def validate_file_size(uploaded_file):
    limit = settings.MAX_UPLOAD_SIZE
    if uploaded_file.size > limit:
        raise ValidationError(
            _("Το αρχείο είναι πολύ μεγάλο (%(size).1f MB). Μέγιστο: %(limit).1f MB."),
            params={
                "size": uploaded_file.size / (1024 * 1024),
                "limit": limit / (1024 * 1024),
            },
        )


def validate_file_mimetype(uploaded_file):
    """Sniff magic bytes and require them to match the declared extension."""
    ext = file_extension(uploaded_file.name)
    expected_mimes = settings.ALLOWED_UPLOAD_TYPES.get(ext)
    if not expected_mimes:
        return  # extension validator already rejected it

    sniffed = sniff_mimetype(uploaded_file)

    # Legacy .doc and some text-ish files are not detectable by magic bytes.
    # Only enforce when we could sniff a type at all.
    if sniffed is not None and sniffed not in expected_mimes:
        raise ValidationError(
            _(
                "Το περιεχόμενο του αρχείου (%(sniffed)s) δεν ταιριάζει με την "
                "επέκταση «.%(ext)s»."
            ),
            params={"sniffed": sniffed, "ext": ext},
        )


def validate_upload(uploaded_file):
    """Run all upload validators. Attach this to the model FileField."""
    validate_file_extension(uploaded_file)
    validate_file_size(uploaded_file)
    validate_file_mimetype(uploaded_file)
