import logging
from pathlib import Path

from django.contrib import messages
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django_ratelimit.decorators import ratelimit

from .forms import ContactForm
from .models import Announcement, Category, Document, Section
from .notifications import send_contact_notification

security_log = logging.getLogger("content.security")


def _client_ip(request) -> str:
    """Best-effort client IP for the security log.

    X-Forwarded-For is attacker-controlled unless a proxy you own rewrites it,
    so the value is only ever logged, never used for an access decision.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return request.META.get("REMOTE_ADDR", "?")


# Icon shown on the home page card for each section. Sections without an entry
# fall back to a generic folder, so adding a Section never leaves a blank card.
SECTION_ICONS = {
    Section.PANELLINIES: "school",
    Section.ASKISEIS: "assignment",
    Section.EBOOKS: "menu_book",
    Section.XRISIMA: "engineering",
    Section.TRITOVATHMIA: "account_balance",
}


# Hero banner slideshow. The files are CC0 photographs cropped to 1920x900 —
# see Frontend/static/img/hero/CREDITS.md.
HERO_SLIDES = [
    {"src": "img/hero/ship.jpg", "alt": _("Φορτηγό πλοίο στη θάλασσα")},
    {"src": "img/hero/wind.jpg", "alt": _("Θαλάσσιο αιολικό πάρκο στο ηλιοβασίλεμα")},
    {"src": "img/hero/study.jpg", "alt": _("Μαθητής διαβάζει βιβλίο κρατώντας σημειώσεις")},
]


def _active_documents(category):
    """All visible documents in a category and its direct subcategories."""
    return (
        Document.objects.filter(is_active=True)
        .filter(Q(category=category) | Q(category__parent=category))
        .select_related("category")
    )


def home(request):
    latest = Announcement.objects.filter(published=True)[:3]
    # Built from Section itself so the cards always match the navbar, and a new
    # section shows up on the home page without a second edit here.
    cards = [
        {"section": value, "icon": SECTION_ICONS.get(value, "folder"), "label": label}
        for value, label in Section.choices
    ]
    # What a returning student actually wants: what went up since last time.
    recent = (
        Document.objects.filter(is_active=True, category__is_active=True)
        .select_related("category")
        .order_by("-uploaded_at")[:6]
    )
    return render(
        request,
        "content/home.html",
        {
            "announcements": latest,
            "cards": cards,
            "hero_slides": HERO_SLIDES,
            "recent_documents": recent,
        },
    )


def section_view(request, section):
    if section not in Section.values:
        raise Http404
    label = Section(section).label
    roots = (
        Category.objects.filter(section=section, parent__isnull=True, is_active=True)
        .annotate(doc_count=Count("documents", filter=Q(documents__is_active=True)))
        .prefetch_related("children")
    )
    loose_docs = Document.objects.filter(
        is_active=True, category__section=section
    ).select_related("category")[:100]
    return render(
        request,
        "content/section.html",
        {"section": section, "section_label": label, "roots": roots, "documents": loose_docs},
    )


def category_view(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    documents = _active_documents(category)
    return render(
        request,
        "content/category.html",
        {"category": category, "documents": documents},
    )


def profile(request):
    """The teacher's professional profile.

    Everything here is public-facing detail from his CV. The private parts —
    home address, mobile number, date of birth, military and licence numbers,
    degree marks — are deliberately not published; students and parents have no
    need for them and they are exactly what identity theft feeds on. Contact
    goes through the form instead.
    """
    specialisations = [
        _("Σχεδίαση αγωνιστικών οχημάτων"),
        _("Δυναμική οχήματος"),
        _("Ενεργειακά & περιβαλλοντικά έργα"),
        _("Ανεμογεννήτριες & αιολικά πάρκα"),
        _("Φωτοβολταϊκά συστήματα"),
        _("Δίκτυα φυσικού αερίου"),
        _("Συστήματα CAD – CAM"),
        _("AutoCAD (ECDL CAD)"),
        _("Βιομηχανική παραγωγή & ποιοτικός έλεγχος"),
        _("Θερμαντικός & ψυκτικός εξοπλισμός"),
        _("SAP R/3"),
        _("Αγγλικά"),
    ]
    return render(request, "content/profile.html", {"specialisations": specialisations})


def announcements(request):
    items = Announcement.objects.filter(published=True)
    return render(request, "content/announcements.html", {"announcements": items})


def announcement_detail(request, slug):
    item = get_object_or_404(Announcement, slug=slug, published=True)
    return render(request, "content/announcement_detail.html", {"announcement": item})


@ratelimit(key="ip", rate="5/h", method="POST", block=False)
def contact(request):
    if request.method == "POST":
        if getattr(request, "limited", False):
            # Silent throttle: the honeypot stops naive bots, this stops the
            # ones that fill the form correctly and hammer it.
            security_log.warning(
                "Contact form rate limit hit from %s", _client_ip(request)
            )
            message = _(
                "Έχεις στείλει πολλά μηνύματα. Δοκίμασε ξανά σε λίγη ώρα."
            )
            if request.htmx:
                return render(
                    request, "content/partials/contact_success.html", {"message": message}
                )
            messages.error(request, message)
            return redirect("content:contact")

        form = ContactForm(request.POST)
        if form.is_valid():
            message = form.save()
            # Saved first, emailed second: if the mail server is unreachable the
            # message is still safe in the admin.
            send_contact_notification(message, request=request)
            success = _("Το μήνυμά σας στάλθηκε! Θα λάβετε απάντηση σύντομα.")
            if request.htmx:
                return render(
                    request, "content/partials/contact_success.html", {"message": success}
                )
            messages.success(request, success)
            return redirect("content:contact")
        # Invalid: re-render just the form for HTMX, full page otherwise.
        if request.htmx:
            return render(request, "content/partials/contact_form.html", {"form": form})
    else:
        form = ContactForm()
    return render(request, "content/contact.html", {"form": form})


def download(request, pk):
    """Protected download: streams a file that lives outside the web root.

    The stored disk name is a random UUID; we send it back to the browser
    under its real, human-readable filename.
    """
    document = get_object_or_404(Document, pk=pk, is_active=True)
    try:
        file_handle = document.file.open("rb")
    except FileNotFoundError:
        # A row pointing at a file that is gone is worth knowing about.
        security_log.warning(
            "Document %s references a missing file %s", document.pk, document.file.name
        )
        raise Http404(_("Το αρχείο δεν βρέθηκε."))

    download_name = Path(document.original_filename or document.file.name).name
    response = FileResponse(file_handle, as_attachment=True, filename=download_name)
    if document.content_type:
        response["Content-Type"] = document.content_type
    # Belt and braces: always a download, never rendered in the visitor's tab,
    # and never sniffed into something executable.
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox; default-src 'none'"
    return response
