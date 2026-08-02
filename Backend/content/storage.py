"""Storage backend and upload path for protected documents.

Files are written under settings.PROTECTED_MEDIA_ROOT with a random UUID name
and NO public base_url — so Django can never build a directly reachable URL.
Downloads only happen through content.views.download.
"""

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.functional import cached_property


class ProtectedFileSystemStorage(FileSystemStorage):
    """FileSystemStorage rooted outside the public media directory."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("base_url", None)  # never expose a public URL
        super().__init__(*args, **kwargs)

    @cached_property
    def base_location(self):
        # Read the setting on first use rather than at import time, so the
        # location follows settings changes (an overridden PROTECTED_MEDIA_ROOT
        # in the tests, for instance).
        return self._value_or_setting(self._location, str(settings.PROTECTED_MEDIA_ROOT))

    def _clear_cached_properties(self, setting, **kwargs):
        if setting == "PROTECTED_MEDIA_ROOT":
            self.__dict__.pop("base_location", None)
            self.__dict__.pop("location", None)
        super()._clear_cached_properties(setting, **kwargs)


protected_storage = ProtectedFileSystemStorage()


def uuid_upload_to(instance, filename):
    """Store as <yyyy>/<mm>/<uuid>.<ext>; real name is kept on the model."""
    from django.utils import timezone

    ext = Path(filename).suffix.lower()
    now = timezone.now()
    return f"{now:%Y/%m}/{uuid.uuid4().hex}{ext}"
