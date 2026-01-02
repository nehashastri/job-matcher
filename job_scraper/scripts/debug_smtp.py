"""Diagnostic SMTP script: tests STARTTLS (587) and SSL (465) with current env."""

import os
import smtplib
import traceback
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

user = os.environ.get("SMTP_USERNAME", "")
pwd = os.environ.get("SMTP_PASSWORD", "")
server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")

print(f"User: {user}")
print(f"Password length: {len(pwd)}")
print(f"Password repr: {pwd!r}")


def test_starttls():
    print("\n=== STARTTLS 587 ===")
    try:
        with smtplib.SMTP(server, 587, timeout=15) as s:
            s.set_debuglevel(1)
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(user, pwd)
            print("LOGIN OK (587)")
    except Exception as e:
        print("FAILED 587:", repr(e))
        traceback.print_exc()


def test_ssl():
    print("\n=== SSL 465 ===")
    try:
        with smtplib.SMTP_SSL(server, 465, timeout=15) as s:
            s.set_debuglevel(1)
            s.ehlo()
            s.login(user, pwd)
            print("LOGIN OK (465)")
    except Exception as e:
        print("FAILED 465:", repr(e))
        traceback.print_exc()


test_starttls()
test_ssl()
