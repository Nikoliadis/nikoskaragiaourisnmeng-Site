"""Security-related response middleware.

Two things Django does not ship a setting for:

* the Permissions-Policy and Cross-Origin-Resource-Policy headers;
* a Content-Security-Policy that is strict on the public site but still
  workable inside the admin, which renders inline styles and scripts.
"""

from csp.middleware import CSPMiddleware
from django.conf import settings

# Features this site never uses. Denying them means a script that somehow got
# injected still cannot reach the camera, microphone or location.
PERMISSIONS_POLICY = ", ".join(
    f"{feature}=()"
    for feature in (
        "accelerometer",
        "autoplay",
        "camera",
        "display-capture",
        "encrypted-media",
        "fullscreen",
        "geolocation",
        "gyroscope",
        "magnetometer",
        "microphone",
        "midi",
        "payment",
        "usb",
        "xr-spatial-tracking",
        "interest-cohort",  # opts out of FLoC-style tracking
    )
)


class SecurityHeadersMiddleware:
    """Adds the response headers Django has no setting for."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        # Stops other origins from embedding our documents and images.
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return response


class AdminAwareCSPMiddleware(CSPMiddleware):
    """CSP middleware that relaxes the policy for the admin only.

    The public pages get a policy with no 'unsafe-inline' anywhere. The admin
    (django-unfold, Alpine.js) cannot run under that, so it gets a looser
    policy — still limited to this origin, so an injected <script src="..."> to
    an attacker's domain is refused either way.
    """

    # Derived, not hardcoded: with a renamed admin a literal "/admin/" would
    # silently stop matching, and the admin would be served the strict public
    # policy — a broken admin, with no error to explain why.
    @property
    def admin_prefix(self):
        return f"/{settings.ADMIN_PATH}/"

    def get_policy_parts(self, request, response, report_only=False):
        parts = super().get_policy_parts(request, response, report_only=report_only)
        if (
            not report_only
            and parts.config is None
            and request.path_info.startswith(self.admin_prefix)
        ):
            parts.config = settings.ADMIN_CONTENT_SECURITY_POLICY["DIRECTIVES"]
        return parts
