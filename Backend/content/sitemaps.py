"""Sitemaps — the list of pages we ask Google to index.

No SITE_ID and no django.contrib.sites: Django's sitemap view falls back to
RequestSite, which takes the domain from the incoming request. One less piece
of configuration that can point at example.com in production.

Only public, indexable pages belong here. The admin and the download view are
deliberately absent — see robots.txt.
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Announcement, Category, Section


class StaticViewSitemap(Sitemap):
    """The fixed pages. The home page is what should rank for the name."""

    protocol = "https"
    changefreq = "weekly"

    def items(self):
        return [
            ("content:home", 1.0),
            ("content:profile", 0.9),
            ("content:announcements", 0.6),
            ("content:contact", 0.5),
        ]

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]


class SectionSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return list(Section.values)

    def location(self, section):
        return reverse("content:section", args=[section])


class CategorySitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Category.objects.filter(is_active=True)


class AnnouncementSitemap(Sitemap):
    protocol = "https"
    changefreq = "monthly"
    priority = 0.4

    def items(self):
        return Announcement.objects.filter(published=True)

    def lastmod(self, announcement):
        return announcement.updated_at


SITEMAPS = {
    "static": StaticViewSitemap,
    "sections": SectionSitemap,
    "categories": CategorySitemap,
    "announcements": AnnouncementSitemap,
}
