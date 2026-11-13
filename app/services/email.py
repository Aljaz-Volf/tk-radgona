import smtplib
from email.message import EmailMessage
from urllib.parse import urljoin

from flask import current_app, render_template, url_for


def send_password_reset_email(user) -> bool:
    """Send a password-change link without trusting the request Host header."""
    server = current_app.config.get("MAIL_SERVER")
    sender = current_app.config.get("MAIL_DEFAULT_SENDER")
    if not server or not sender:
        current_app.logger.warning(
            "Password reset email skipped because SMTP is not configured for user_id=%s",
            user.id,
        )
        return False

    base_url = current_app.config["PUBLIC_BASE_URL"].rstrip("/") + "/"
    reset_path = url_for("auth.reset_password", token=user.get_reset_token()).lstrip("/")
    reset_url = urljoin(base_url, reset_path)

    message = EmailMessage()
    message["Subject"] = "Sprememba gesla — TK Gornja Radgona"
    message["From"] = sender
    message["To"] = user.email
    message.set_content(
        render_template("email/password_reset.txt", user=user, reset_url=reset_url)
    )
    message.add_alternative(
        render_template("email/password_reset.html", user=user, reset_url=reset_url),
        subtype="html",
    )

    try:
        with smtplib.SMTP(server, current_app.config["MAIL_PORT"], timeout=15) as smtp:
            if current_app.config["MAIL_USE_TLS"]:
                smtp.starttls()
            if current_app.config["MAIL_USERNAME"]:
                smtp.login(
                    current_app.config["MAIL_USERNAME"],
                    current_app.config["MAIL_PASSWORD"],
                )
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        current_app.logger.exception(
            "Password reset email delivery failed for user_id=%s", user.id
        )
        return False
    return True
