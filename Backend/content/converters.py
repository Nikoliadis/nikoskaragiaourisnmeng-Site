class UnicodeSlugConverter:
    """Like Django's SlugConverter but also matches Greek/Unicode word chars.

    In Python 3, `\\w` matches Unicode letters by default, so Greek slugs
    such as «θεματα-2024» resolve correctly.
    """

    regex = r"[-\w]+"

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value
