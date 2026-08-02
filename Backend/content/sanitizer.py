"""HTML sanitising for rich-text content written in the admin.

The announcement editor stores HTML that the site renders unescaped. Even
though only staff can write it, a stolen admin session should not be able to
plant a script that then runs in every visitor's browser. Everything is passed
through nh3 (Rust ammonia) on save, so what reaches the database is already
clean — the template never has to trust its input.
"""

import nh3

# Everything a teacher needs for an announcement, and nothing that executes.
ALLOWED_TAGS = {
    "p", "br", "hr", "div", "span",
    "strong", "b", "em", "i", "u", "s", "sub", "sup", "mark", "small",
    "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "blockquote", "pre", "code",
    "a", "img", "figure", "figcaption",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
    "*": {"class"},
}

# No javascript:, no data: — an <a href="javascript:..."> is a script.
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def clean_html(html: str) -> str:
    """Strip scripts, event handlers and unsafe URLs from admin-written HTML."""
    if not html:
        return html
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        # Outbound links cannot reach back into this tab.
        link_rel="noopener noreferrer",
        strip_comments=True,
    )
