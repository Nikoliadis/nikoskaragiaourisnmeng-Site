"""Builds the navbar dropdown structure available to every template."""

from .models import Category, Section


def navigation(request):
    """Group active top-level categories by section for the navbar dropdowns."""
    roots = (
        Category.objects.filter(parent__isnull=True, is_active=True)
        .prefetch_related("children")
    )
    menu = {value: {"label": label, "items": []} for value, label in Section.choices}
    for category in roots:
        menu[category.section]["items"].append(category)

    return {
        "nav_sections": Section,
        "nav_menu": menu,
    }
