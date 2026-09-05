import asyncio
import logging
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape

logger = logging.getLogger("passport-tracker")
NON_DELIVERABLE_DOMAINS = {"example.com", "example.org", "example.net"}


def _is_deliverable_email(address: str) -> bool:
    normalized = address.strip().lower()
    if normalized.count("@") != 1:
        return False
    local_part, domain = normalized.rsplit("@", 1)
    return bool(local_part and domain) and domain not in NON_DELIVERABLE_DOMAINS


def _send_email_sync(recipient: str, file_no: str, previous_status: str, new_status: str) -> None:
    host = os.getenv("SMTP_HOST", "")
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", username)
    port = int(os.getenv("SMTP_PORT", "587"))
    use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

    if not all((host, username, password, sender)):
        logger.warning("Email not sent: SMTP settings are incomplete")
        return

    safe_file_no = escape(file_no)
    safe_previous_status = escape(previous_status)
    safe_new_status = escape(new_status)
    updated_at = datetime.now(timezone.utc).strftime("%d %B %Y at %H:%M UTC")

    message = EmailMessage()
    message["Subject"] = f"Passport Status Update | {file_no} | {new_status}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "PASSPORT STATUS NOTIFICATION\n\n"
        "Dear Applicant,\n\n"
        "There has been an update to your passport application.\n\n"
        f"File Number: {file_no}\n"
        f"Previous Status: {previous_status}\n"
        f"Current Status: {new_status}\n"
        f"Updated: {updated_at}\n\n"
        "No action is required unless you are contacted separately. Please keep your "
        "file number confidential.\n\nRegards,\nPassport Status Tracking Team\n\n"
        "This is an automated message. Please do not reply."
    )
    message.add_alternative(
        f"""
        <!doctype html>
        <html lang="en">
        <body style="margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#243b53;">
          <div style="max-width:620px;margin:32px auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 6px 24px rgba(16,42,67,.10);">
            <div style="padding:28px 32px;background:#123b5d;color:#ffffff;">
              <div style="font-size:12px;font-weight:bold;letter-spacing:2px;color:#9bd4f5;">CITIZEN SERVICES</div>
              <h1 style="margin:8px 0 0;font-size:25px;">Passport Status Update</h1>
            </div>
            <div style="padding:32px;">
              <p style="margin-top:0;font-size:16px;">Dear Applicant,</p>
              <p style="line-height:1.6;color:#486581;">There has been an update to your passport application. The latest details are shown below.</p>
              <div style="margin:24px 0;border:1px solid #d9e2ec;border-radius:10px;overflow:hidden;">
                <div style="padding:14px 18px;background:#f8fafc;border-bottom:1px solid #d9e2ec;">
                  <span style="display:block;font-size:11px;font-weight:bold;letter-spacing:1px;color:#829ab1;">FILE NUMBER</span>
                  <strong style="display:block;margin-top:5px;font-size:18px;color:#102a43;">{safe_file_no}</strong>
                </div>
                <div style="padding:18px;">
                  <div style="font-size:12px;color:#829ab1;">PREVIOUS STATUS</div>
                  <div style="margin:5px 0 18px;color:#627d98;">{safe_previous_status}</div>
                  <div style="font-size:12px;color:#829ab1;">CURRENT STATUS</div>
                  <div style="display:inline-block;margin-top:7px;padding:9px 14px;border-radius:999px;background:#dff4ea;color:#17613a;font-weight:bold;">{safe_new_status}</div>
                </div>
              </div>
              <p style="font-size:13px;color:#829ab1;">Updated on {updated_at}</p>
              <p style="margin-top:24px;line-height:1.6;color:#486581;">No action is required unless you are contacted separately. Please keep your file number confidential.</p>
              <p style="margin:28px 0 0;">Regards,<br><strong>Passport Status Tracking Team</strong></p>
            </div>
            <div style="padding:18px 32px;background:#f8fafc;border-top:1px solid #e6edf3;font-size:12px;color:#829ab1;text-align:center;">
              This is an automated notification. Please do not reply to this email.
            </div>
          </div>
        </body>
        </html>
        """,
        subtype="html",
    )

    context = ssl.create_default_context()
    if use_ssl:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
            server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(username, password)
            server.send_message(message)


async def send_status_email(
    *, recipient: str, file_no: str, previous_status: str, new_status: str
) -> None:
    """Send one status-change email without blocking FastAPI's event loop."""
    if not _is_deliverable_email(recipient):
        logger.info(
            "Email skipped for application %s: recipient is a placeholder or invalid address",
            file_no,
        )
        return
    try:
        await asyncio.to_thread(
            _send_email_sync, recipient, file_no, previous_status, new_status
        )
        logger.info("Email accepted by SMTP server for %s", recipient)
    except Exception:
        logger.exception("Email notification failed for %s", recipient)
