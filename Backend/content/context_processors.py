"""Builds the navbar dropdown structure available to every template."""

from django.db.models import Prefetch

from .models import Category, Section


def navigation(request):
    """Group active top-level categories by section for the navbar dropdowns.

    Each root category carries its active subcategories, so a dropdown can show
    two levels (e.g. ΠΑΝΕΠΙΣΤΗΜΙΑ › ΠΡΟΠΤΥΧΙΑΚΑ) without a query per row.
    """
    roots = (
        Category.objects.filter(parent__isnull=True, is_active=True)
        .order_by("order", "name")
        .prefetch_related(
            Prefetch(
                "children",
                queryset=Category.objects.filter(is_active=True).order_by("order", "name"),
            )
        )
    )
    menu = {value: {"label": label, "items": []} for value, label in Section.choices}
    for category in roots:
        # Ignore rows pointing at a section that no longer exists.
        if category.section in menu:
            menu[category.section]["items"].append(category)

    return {
        "nav_sections": Section,
        "nav_menu": menu,
    }
