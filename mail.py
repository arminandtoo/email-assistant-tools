import json
import smtplib
from datetime import datetime
from email.message import EmailMessage

from imap_tools import AND, MailBox, MailMessageFlags

# Gmail servers. For Outlook use outlook.office365.com / smtp.office365.com
IMAP_HOST = "imap.gmail.com"
SMTP_HOST = "smtp.gmail.com"

EMAIL = ""
PASSWORD = ""

# Sandbox
SANDBOX = False
sandbox_inbox = []


def login(email, password):
    """Check the credentials, then keep them for the other functions."""
    global EMAIL, PASSWORD, SANDBOX
    MailBox(IMAP_HOST).login(email, password).logout()
    EMAIL, PASSWORD, SANDBOX = email, password, False


def start_sandbox():
    """Use the fake inbox from sample_emails.json (resets it every time)."""
    global EMAIL, SANDBOX, sandbox_inbox
    with open("sample_emails.json", encoding="utf-8") as f:
        sandbox_inbox = json.load(f)
    EMAIL, SANDBOX = "you@email.com", True


def fetch_emails(limit=20, unread_only=False):
    """Return the newest emails as a list of dicts."""
    if SANDBOX:
        return [e for e in sandbox_inbox if not (unread_only and e["seen"])][:limit]

    criteria = AND(seen=False) if unread_only else "ALL"
    with MailBox(IMAP_HOST).login(EMAIL, PASSWORD) as box:
        return [
            {
                "uid": msg.uid,
                "from": msg.from_,
                "subject": msg.subject,
                "date": msg.date.strftime("%Y-%m-%d %H:%M"),
                "text": (msg.text or msg.html)[:1000],
            }
            for msg in box.fetch(criteria, limit=limit, reverse=True, mark_seen=False, bulk=True)
        ]


def mark_as_read(uid):
    if SANDBOX:
        for e in sandbox_inbox:
            if e["uid"] == uid:
                e["seen"] = True
        return

    with MailBox(IMAP_HOST).login(EMAIL, PASSWORD) as box:
        box.flag(uid, MailMessageFlags.SEEN, True)


def delete_email(uid):
    global sandbox_inbox
    if SANDBOX:
        sandbox_inbox = [e for e in sandbox_inbox if e["uid"] != uid]
        return

    # Gmail moves it out of the inbox (archive) by default
    with MailBox(IMAP_HOST).login(EMAIL, PASSWORD) as box:
        box.delete(uid)


def send_email(to, subject, body):
    if SANDBOX:
        new_uid = str(max((int(e["uid"]) for e in sandbox_inbox), default=0) + 1)
        sandbox_inbox.insert(0, {
            "uid": new_uid, "from": EMAIL, "subject": subject, "seen": True,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "text": f"To: {to}\n\n{body}",
        })
        return

    msg = EmailMessage()
    msg["From"] = EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP_SSL(SMTP_HOST, 465) as server:
        server.login(EMAIL, PASSWORD)
        server.send_message(msg)
