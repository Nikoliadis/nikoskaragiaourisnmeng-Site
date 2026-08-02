"""Emailing the site owner when a student sends a contact message."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.urls import reverse

log = logging.getLogger("content.security")


def notify_recipients() -> list[str]:
    """Who to tell about a new message.

    An explicit list in .env wins; otherwise every active superuser that has an
    address on their account. Keeping it in the database means changing the
    admin's email in the admin is enough — no redeploy, and no personal address
    committed to the repository.
    """
    if settings.CONTACT_NOTIFY_EMAILS:
        return settings.CONTACT_NOTIFY_EMAILS

    return list(
        get_user_model()
        ._default_manager.filter(is_superuser=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def send_contact_notification(message, request=None) -> bool:
    """Forward a ContactMessage by email. Never raises.

    A mail server that is down or misconfigured must not turn a student's
    successful submission into an error page — the message is already saved in
    the database, which stays the source of truth.
    """
    recipients = notify_recipients()
    if not recipients:
        log.warning("Contact message %s: no notification recipient configured", message.pk)
        return False

    admin_path = reverse("admin:content_contactmessage_change", args=[message.pk])
    admin_url = request.build_absolute_uri(admin_path) if request else admin_path

    body = (
        f"Νέο μήνυμα από τη φόρμα επικοινωνίας.\n\n"
        f"Όνομα: {message.name}\n"
        f"Email:  {message.email}\n"
        f"Ημ/νία: {message.created_at:%d/%m/%Y %H:%M}\n\n"
        f"{'-' * 50}\n"
        f"{message.message}\n"
        f"{'-' * 50}\n\n"
        f"Απάντησε κατευθείαν σε αυτό το email — πάει στον αποστολέα.\n"
        f"Στο admin: {admin_url}\n"
    )

    email = EmailMessage(
        # Django refuses a subject containing a newline, so a crafted name
        # cannot inject extra mail headers here.
        subject=f"Νέο μήνυμα από {message.name}",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
        # Hitting Reply answers the student, not the server's own address.
        reply_to=[message.email],
    )

    try:
        email.send(fail_silently=False)
    except Exception:
        log.exception("Could not email contact message %s", message.pk)
        return False

    log.info("Contact message %s emailed to %s", message.pk, ", ".join(recipients))
    return True
