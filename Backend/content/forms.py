from django import forms
from django.utils.translation import gettext_lazy as _

from .models import ContactMessage

INPUT_CLASSES = (
    "w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 "
    "placeholder-slate-400 shadow-sm focus:border-sky-500 focus:ring-2 "
    "focus:ring-sky-200 focus:outline-none transition "
    # Tailwind scans this file (see @source in Frontend/src/input.css), so the
    # dark variants below are built like any class written in a template.
    "dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 "
    "dark:placeholder-slate-500 dark:focus:border-brand-500 dark:focus:ring-brand-900"
)


class ContactForm(forms.ModelForm):
    # Simple honeypot: bots fill hidden fields, humans don't.
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "message"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": INPUT_CLASSES, "placeholder": _("Το όνομά σας")}
            ),
            "email": forms.EmailInput(
                attrs={"class": INPUT_CLASSES, "placeholder": "email@example.com"}
            ),
            "message": forms.Textarea(
                attrs={
                    "class": INPUT_CLASSES,
                    "rows": 5,
                    "placeholder": _("Το μήνυμά σας…"),
                }
            ),
        }

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Spam detected.")
        return ""
