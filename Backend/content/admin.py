from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.contrib.forms.widgets import WysiwygWidget

from .models import Announcement, Category, ContactMessage, Document


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("name", "section", "parent", "order", "is_active")
    list_filter = ("section", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("name",)
    prepopulated_fields = {}  # slug auto-fills from name in the model
    autocomplete_fields = ("parent",)
    fields = ("name", "slug", "section", "parent", "order", "is_active")
    readonly_fields = ()

    def get_prepopulated_fields(self, request, obj=None):
        return {}


@admin.register(Document)
class DocumentAdmin(ModelAdmin):
    list_display = ("title", "category", "extension_badge", "size_display", "uploaded_at", "is_active")
    list_filter = ("category__section", "category", "is_active", "uploaded_at")
    list_editable = ("is_active",)
    search_fields = ("title", "description", "original_filename")
    autocomplete_fields = ("category",)
    date_hierarchy = "uploaded_at"
    readonly_fields = ("original_filename", "content_type", "size", "uploaded_at")
    fieldsets = (
        (None, {"fields": ("title", "description", "category", "file", "is_active")}),
        (
            _("Στοιχεία αρχείου (αυτόματα)"),
            {
                "classes": ("collapse",),
                "fields": ("original_filename", "content_type", "size", "uploaded_at"),
            },
        ),
    )

    @admin.display(description=_("Τύπος"))
    def extension_badge(self, obj):
        return format_html(
            '<span class="inline-flex rounded bg-slate-100 px-2 py-0.5 '
            'text-xs font-semibold uppercase text-slate-700 '
            'dark:bg-slate-700 dark:text-slate-200">{}</span>',
            obj.extension or "—",
        )


@admin.register(Announcement)
class AnnouncementAdmin(ModelAdmin):
    list_display = ("title", "created_at", "published")
    list_filter = ("published", "created_at")
    list_editable = ("published",)
    search_fields = ("title", "content")
    date_hierarchy = "created_at"
    fields = ("title", "slug", "content", "image", "published")

    formfield_overrides = {
        models.TextField: {"widget": WysiwygWidget},
    }

    def get_prepopulated_fields(self, request, obj=None):
        return {}


@admin.register(ContactMessage)
class ContactMessageAdmin(ModelAdmin):
    list_display = ("name", "email", "short_message", "created_at", "is_read")
    list_filter = ("is_read", "created_at")
    search_fields = ("name", "email", "message")
    readonly_fields = ("name", "email", "message", "created_at")
    date_hierarchy = "created_at"

    @admin.display(description=_("Μήνυμα"))
    def short_message(self, obj):
        return (obj.message[:60] + "…") if len(obj.message) > 60 else obj.message

    def has_add_permission(self, request):
        return False  # messages arrive only via the public contact form
