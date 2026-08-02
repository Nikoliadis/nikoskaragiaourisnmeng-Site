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


def validate_file_extension(uploaded_file):
    ext = Path(uploaded_file.name).suffix.lower().lstrip(".")
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
    ext = Path(uploaded_file.name).suffix.lower().lstrip(".")
    expected_mimes = settings.ALLOWED_UPLOAD_TYPES.get(ext)
    if not expected_mimes:
        return  # extension validator already rejected it

    pos = uploaded_file.tell()
    header = uploaded_file.read(262)  # filetype needs at most 262 bytes
    uploaded_file.seek(pos)

    kind = filetype.guess(header)
    sniffed = kind.mime if kind else None

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
