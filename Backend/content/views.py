from pathlib import Path

from django.contrib import messages
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .forms import ContactForm
from .models import Announcement, Category, Document, Section


def _active_documents(category):
    """All visible documents in a category and its direct subcategories."""
    return (
        Document.objects.filter(is_active=True)
        .filter(Q(category=category) | Q(category__parent=category))
        .select_related("category")
    )


def home(request):
    latest = Announcement.objects.filter(published=True)[:3]
    cards = [
        {"section": Section.PANELLINIES, "icon": "school", "label": _("Πανελλαδικές")},
        {"section": Section.ASKISEIS, "icon": "assignment", "label": _("Ασκήσεις")},
        {"section": Section.EBOOKS, "icon": "menu_book", "label": _("e-books")},
    ]
    return render(request, "content/home.html", {"announcements": latest, "cards": cards})


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


def announcements(request):
    items = Announcement.objects.filter(published=True)
    return render(request, "content/announcements.html", {"announcements": items})


def announcement_detail(request, slug):
    item = get_object_or_404(Announcement, slug=slug, published=True)
    return render(request, "content/announcement_detail.html", {"announcement": item})


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
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
        raise Http404(_("Το αρχείο δεν βρέθηκε."))

    download_name = document.original_filename or Path(document.file.name).name
    response = FileResponse(file_handle, as_attachment=True, filename=download_name)
    if document.content_type:
        response["Content-Type"] = document.content_type
    return response
