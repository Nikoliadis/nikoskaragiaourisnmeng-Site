"""Assets that identify the teacher, shared by the views and the templates."""

from functools import lru_cache

from django.contrib.staticfiles import finders

# Drop the photo into Frontend/static/img/ under any of these names and it
# appears; leave it out and the pages render without it.
PORTRAIT_CANDIDATES = (
    "img/profile.jpg",
    "img/profile.jpeg",
    "img/profile.png",
    "img/profile.webp",
)


@lru_cache(maxsize=1)
def portrait_path():
    """The portrait's static path, or None if the photo hasn't been added.

    Checked rather than assumed: under ManifestStaticFilesStorage a {% static %}
    pointing at a file that isn't there raises at render time, so an absent
    photo would take the whole page down instead of simply not showing.

    Cached because it hits the filesystem and the answer only changes when
    someone adds the file and restarts the server.
    """
    return next((path for path in PORTRAIT_CANDIDATES if finders.find(path)), None)


def branding(request):
    """Context processor: makes the portrait available to every template."""
    return {"portrait": portrait_path()}
