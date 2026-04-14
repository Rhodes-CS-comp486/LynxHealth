"""
Email utility for LynxHealth backend.

Provides a function to send emails using Gmail SMTP and app password.
Credentials are loaded from environment variables for security.
"""
import os
import smtplib
from email.message import EmailMessage

EMAIL_ADDRESS = os.getenv("LYNXHEALTH_EMAIL")
EMAIL_PASSWORD = os.getenv("LYNXHEALTH_EMAIL_PASSWORD")


def send_email(to_address: str, subject: str, body: str) -> None:
    """
    Send an email using Gmail SMTP.

    Args:
        to_address (str): Recipient email address.
        subject (str): Email subject.
        body (str): Email body (plain text).
    """
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        raise RuntimeError("Email credentials not set in environment variables.")

    msg = EmailMessage()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)
