from django.urls import path, register_converter

from . import views
from .converters import UnicodeSlugConverter

register_converter(UnicodeSlugConverter, "uslug")

app_name = "content"

urlpatterns = [
    path("", views.home, name="home"),
    path("profil/", views.profile, name="profile"),
    path("enimerosi/", views.announcements, name="announcements"),
    path("enimerosi/<uslug:slug>/", views.announcement_detail, name="announcement"),
    path("epikoinonia/", views.contact, name="contact"),
    path("kateigoria/<uslug:slug>/", views.category_view, name="category"),
    path("lipsi/<int:pk>/", views.download, name="download"),
    # Top-level sections (panellinies / askiseis / ebooks / xrisima)
    path("<slug:section>/", views.section_view, name="section"),
]
