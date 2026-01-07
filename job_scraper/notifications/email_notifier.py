# Cleaned up version
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

try:
    from win10toast import ToastNotifier
except ImportError:
    ToastNotifier = None


logger = logging.getLogger(__name__)


class EmailNotifier:
    """
    Minimal email notification for accepted jobs and relevant profiles.
    Attributes:
        smtp_server (str): SMTP server address
        smtp_port (int): SMTP server port
        smtp_username (str): SMTP username
        smtp_password (str): SMTP password
        email_from (str): Sender email address
        email_to (str): Recipient email address
        smtp_use_ssl (bool): Whether to use SSL for SMTP
        enabled (bool): Whether email notifications are enabled
    """

    def __init__(self):
        """
        Initialize EmailNotifier and load SMTP/email configuration from environment variables.
        """
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.email_from = os.getenv("EMAIL_FROM", "")
        self.email_to = os.getenv("EMAIL_TO", "")
        self.smtp_use_ssl = os.getenv("SMTP_USE_SSL", "False").lower() in [
            "true",
            "1",
            "yes",
        ]
        self.enabled = os.getenv("ENABLE_EMAIL_NOTIFICATIONS", "True").lower() in [
            "true",
            "1",
            "yes",
        ]

    def send_job_notification(
        self, job_data: dict, match_profiles: Optional[list[dict[str, str]]] = None
    ) -> bool:
        logging.getLogger(__name__).info(
            f"[ENTER] {__file__}::{self.__class__.__name__}.send_job_notification"
        )
        """
        Send an email notification for an accepted job and relevant profiles.
        Args:
            job_data (dict): Job data to include in the email
            match_profiles (Optional[list[dict[str, str]]]): List of matched profiles
        Returns:
            bool: True if email sent, False otherwise
        """
        if not self.enabled:
            logger.info("Email notifications disabled, skipping")
            return False
        if not self._validate_config():
            logger.error("Email configuration invalid, cannot send notification")
            return False
        try:
            subject = self._compose_subject(job_data)
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.email_from
            msg["To"] = self.email_to
            body = self._compose_body(job_data, match_profiles)
            msg.attach(MIMEText(body, "plain"))
            # Compose HTML body with only job_data and match_profiles
            msg.attach(
                MIMEText(self._compose_html_body(job_data, match_profiles), "html")
            )
            self._send_email(msg)
            logger.info(
                f"✅ Email notification sent for job: {job_data.get('title', 'Unknown')}"
            )
            # Show Windows notification if possible, robust to all errors
            if ToastNotifier:
                try:
                    toaster = ToastNotifier()
                    try:
                        toaster.show_toast(
                            "New Job Alert!",
                            "A job notification email was sent.",
                            duration=5,
                        )
                    except Exception as notify_exc:
                        logger.error(f"Windows notification inner error: {notify_exc}")
                except Exception as outer_exc:
                    logger.error(f"Windows notification outer error: {outer_exc}")
            return True
        except smtplib.SMTPException as e:
            logger.error(f"❌ SMTP error occurred: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error sending email: {e}")
            return False

    def _compose_subject(self, job_data: dict) -> str:
        logging.getLogger(__name__).info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._compose_subject"
        )
        title = job_data.get("title", "Unknown")
        company = job_data.get("company", "Unknown")
        return f"🎯 Job Match: {title} at {company}"

    def _compose_body(
        self, job_data: dict, match_profiles: Optional[list[dict[str, str]]] = None
    ) -> str:
        logging.getLogger(__name__).info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._compose_body"
        )
        title = job_data.get("title", "Unknown")
        company = job_data.get("company", "Unknown")
        job_url = job_data.get("job_url", "")
        result = f"New Job Accepted!\n\nJob Title: {title}\nCompany: {company}\nJob URL: {job_url}\n\nRelevant Profiles:\n"
        if match_profiles:
            for p in match_profiles:
                result += f"- {p.get('name', 'Unknown')} ({p.get('title', '')}) {p.get('profile_url', '')}\n"
        else:
            result += "None\n"
        result += "\n---\nThis is an automated notification from the Job Scraper.\n"
        return result
    def _compose_html_body(
        self,
        job_data: Dict[str, Any],
        match_profiles: Optional[list[dict[str, str]]] = None,
    ) -> str:
        logging.getLogger(__name__).info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._compose_html_body"
        )
        """
        Compose HTML email body.

        Args:
            job_data: Job details (dict with keys: title, company, url, match_score)
            match_profiles: List of relevant profiles identified (dicts with keys: name, title, profile_url, company, searched_job_title)

        Returns:
            str: HTML email body
        """
        title = job_data.get("title", "Unknown")
        company = job_data.get("company", "Unknown")
        match_score = job_data.get("match_score", 0)
        job_url = job_data.get("job_url", "") or job_data.get("url", "")
        score_color = (
            "#28a745"
            if str(match_score).isdigit() and int(match_score) >= 8
            else "#ffc107"
        )

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset='UTF-8'>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: #0077b5;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px 5px 0 0;
        }}
        .content {{
            background-color: #f8f9fa;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 0 0 5px 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #0077b5;
            color: white;
        }}
        .section-title {{
            font-size: 1.2em;
            margin-top: 20px;
            margin-bottom: 10px;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class='header'>
        <h2>Job Match Notification</h2>
    </div>
    <div class='content'>
        <div class='section-title'>Job Details</div>
        <table>
            <tr>
                <th>Title</th>
                <th>Company</th>
                <th>URL</th>
                <th>Match Score</th>
            </tr>
            <tr>
                <td>{title}</td>
                <td>{company}</td>
                <td><a href='{job_url}'>Link</a></td>
                <td><span style='color: {score_color};'>{match_score}</span></td>
            </tr>
        </table>
        <div class='section-title'>Relevant Profiles</div>
        <table>
            <tr>
                <th>Name</th>
                <th>Title</th>
                <th>URL</th>
            </tr>
            {{
            "".join(
                [
                    f"<tr><td>{p.get('name', 'Unknown')}</td><td>{p.get('title', '')}</td><td><a href='{p.get('profile_url', p.get('url', ''))}'>Profile</a></td></tr>"
                    for p in (match_profiles or [])
                ]
            )
        }}
        </table>
    </div>
</body>
</html>
"""
        return html
        th {{
            background-color: #0077b5;
            color: white;
        }}
        .section-title {{
            font-size: 1.2em;
            margin-top: 20px;
            margin-bottom: 10px;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class='header'>
        <h2>Job Match Notification</h2>
    </div>
    <div class='content'>
        <div class='section-title'>Job Details</div>
        <table>
            <tr>
                <th>Title</th>
                <th>Company</th>
                <th>URL</th>
                <th>Applicants</th>
                <th>Match Score</th>
            </tr>
            <tr>
                <td>{title}</td>
                <td>{company}</td>
                <td><a href='{job_url}'>Link</a></td>
                <td>{applicants}</td>
                <td><span style='color: {score_color};'>{match_score}</span></td>
            </tr>
        </table>
        <div class='section-title'>Relevant Profiles</div>
        <table>
            <tr>
                <th>Name</th>
                <th>Title</th>
                <th>URL</th>
            </tr>
            {
            "".join(
                [
                    f"<tr><td>{p.get('name', 'Unknown')}</td><td>{p.get('title', '')}</td><td><a href='{p.get('profile_url', p.get('url', ''))}'>Profile</a></td></tr>"
                    for p in (match_profiles or [])
                ]
            )
        }
        </table>
    </div>
</body>
</html>
"""
        return html

    def test_connection(self) -> bool:
        logging.getLogger(__name__).info(
            f"[ENTER] {__file__}::{self.__class__.__name__}.test_connection"
        )
        """
        Test SMTP connection

        Returns:
            bool: True if connection successful, False otherwise
        """
        if not self._validate_config():
            return False

        try:
            logger.info(
                f"Testing SMTP connection to {self.smtp_server}:{self.smtp_port}..."
            )

            server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(self.smtp_username, self.smtp_password)
            server.quit()

            logger.info("✅ SMTP connection test successful")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"❌ SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False
