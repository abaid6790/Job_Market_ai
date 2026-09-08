"""
Minimal, dependency-light email service.

If MAIL_SERVER is configured, real emails are sent over SMTP.
If not (the default in development), the email is written to
logs/dev_emails.log and printed to the console instead, so the full
registration / verification / password-reset flow works out of the box
with zero email setup.
"""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

logger = logging.getLogger("jobmarket_ai.email")


def _dev_deliver(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    log_dir = current_app.config.get("LOG_DIR")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "dev_emails.log")

    entry = (
        "\n" + "=" * 70 + "\n"
        f"TO:      {to_email}\n"
        f"SUBJECT: {subject}\n"
        "-" * 70 + "\n"
        f"{text_body}\n"
        + "=" * 70 + "\n"
    )
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(entry)

    # Also surface it in the app console for quick manual testing.
    print(entry)
    logger.info("DEV EMAIL delivered to log file for %s (%s)", to_email, subject)


def _smtp_deliver(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    cfg = current_app.config
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["MAIL_DEFAULT_SENDER"]
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"]) as server:
        if cfg.get("MAIL_USE_TLS"):
            server.starttls()
        if cfg.get("MAIL_USERNAME"):
            server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        server.sendmail(cfg["MAIL_DEFAULT_SENDER"], [to_email], msg.as_string())


def send_email(to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """Send an email, or log it in dev mode. Returns True on (attempted) success."""
    text_body = text_body or html_body

    try:
        if current_app.config.get("MAIL_SERVER"):
            _smtp_deliver(to_email, subject, html_body, text_body)
        else:
            _dev_deliver(to_email, subject, html_body, text_body)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False


def send_verification_email(to_email: str, name: str, verify_url: str) -> bool:
    subject = "Verify your JobMarket AI account"
    text = (
        f"Hi {name},\n\n"
        f"Welcome to JobMarket AI. Please verify your email address by opening "
        f"this link:\n\n{verify_url}\n\n"
        f"This link expires soon. If you didn't create this account, you can "
        f"ignore this email."
    )
    html = f"""
    <div style="font-family: -apple-system, Arial, sans-serif; max-width: 480px;">
      <h2>Welcome to JobMarket AI, {name}!</h2>
      <p>Please verify your email address to activate your account.</p>
      <p><a href="{verify_url}" style="background:#4f46e5;color:#fff;padding:10px 18px;
         border-radius:6px;text-decoration:none;">Verify Email</a></p>
      <p>Or copy this link into your browser:<br>{verify_url}</p>
      <p style="color:#6b7280;font-size:13px;">If you didn't create this account,
      you can safely ignore this email.</p>
    </div>
    """
    return send_email(to_email, subject, html, text)


def send_password_reset_email(to_email: str, name: str, reset_url: str) -> bool:
    subject = "Reset your JobMarket AI password"
    text = (
        f"Hi {name},\n\n"
        f"We received a request to reset your password. Open this link to "
        f"choose a new password:\n\n{reset_url}\n\n"
        f"This link expires soon. If you didn't request this, you can ignore "
        f"this email and your password will stay the same."
    )
    html = f"""
    <div style="font-family: -apple-system, Arial, sans-serif; max-width: 480px;">
      <h2>Reset your password</h2>
      <p>Hi {name}, we received a request to reset your password.</p>
      <p><a href="{reset_url}" style="background:#4f46e5;color:#fff;padding:10px 18px;
         border-radius:6px;text-decoration:none;">Reset Password</a></p>
      <p>Or copy this link into your browser:<br>{reset_url}</p>
      <p style="color:#6b7280;font-size:13px;">If you didn't request this,
      you can safely ignore this email.</p>
    </div>
    """
    return send_email(to_email, subject, html, text)
