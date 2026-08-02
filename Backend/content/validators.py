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
    """Sniff magic bytes and require them to match the declared extension.

    Every allowed format except legacy .doc starts with a signature `filetype`
    recognises, so for those an unrecognised file is rejected outright. That
    closes the hole where an HTML (or any text) payload renamed to .pdf sailed
    through simply because nothing could be sniffed.
    """
    ext = file_extension(uploaded_file.name)
    expected_mimes = settings.ALLOWED_UPLOAD_TYPES.get(ext)
    if not expected_mimes:
        return  # extension validator already rejected it

    sniffed = sniff_mimetype(uploaded_file)

    if sniffed is None:
        if ext in settings.UNSNIFFABLE_UPLOAD_TYPES:
            return  # .doc has no reliable magic bytes
        raise ValidationError(
            _(
                "Δεν αναγνωρίστηκε το περιεχόμενο του αρχείου ως «.%(ext)s». "
                "Ανέβασε το αρχείο στην κανονική του μορφή."
            ),
            params={"ext": ext},
        )

    if sniffed not in expected_mimes:
        raise ValidationError(
            _(
                "Το περιεχόμενο του αρχείου (%(sniffed)s) δεν ταιριάζει με την "
                "επέκταση «.%(ext)s»."
            ),
            params={"sniffed": sniffed, "ext": ext},
        )


def validate_filename(uploaded_file):
    """Reject filenames that try to escape the upload directory.

    The stored name is a fresh UUID so a traversal attempt cannot reach the
    filesystem, but the original name is echoed back in Content-Disposition on
    download — it must not carry path separators or control characters.
    """
    name = Path(uploaded_file.name).name  # strips any directory part
    if not name or name in {".", ".."}:
        raise ValidationError(_("Μη έγκυρο όνομα αρχείου."))
    if any(ord(char) < 32 or char in '"\\/' for char in name):
        raise ValidationError(
            _("Το όνομα του αρχείου περιέχει μη επιτρεπτούς χαρακτήρες."),
        )
    if len(name) > 200:
        raise ValidationError(_("Το όνομα του αρχείου είναι πολύ μεγάλο."))


def validate_upload(uploaded_file):
    """Run all upload validators. Attach this to the model FileField."""
    validate_filename(uploaded_file)
    validate_file_extension(uploaded_file)
    validate_file_size(uploaded_file)
    validate_file_mimetype(uploaded_file)
