# Cleaned up version

import logging
import os
import smtplib
from typing import Any, Dict, Optional

try:
    from win10toast import ToastNotifier
except ImportError:
    ToastNotifier = None


logger = logging.getLogger(__name__)


class EmailNotifier:
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

    def _validate_config(self) -> bool:
        """
        Validate that all required SMTP/email configuration is present.
        Returns:
            bool: True if config is valid, False otherwise
        """
        if not self.smtp_server:
            logger.error("SMTP_SERVER not configured in environment")
            return False
        if not self.smtp_username:
            logger.error("SMTP_USERNAME not configured in environment")
            return False
        if not self.smtp_password:
            logger.error("SMTP_PASSWORD not configured in environment")
            return False
        if not self.email_from:
            logger.error("EMAIL_FROM not configured in environment")
            return False
        if not self.email_to:
            logger.error("EMAIL_TO not configured in environment")
            return False
        return True

    def _compose_html_body(
        self,
        job_data: Dict[str, Any],
        match_profiles: Optional[list[dict[str, str]]] = None,
    ) -> str:
        """
        Compose HTML email body.

        Args:
            job_data: Job details (dict with keys: title, company, url, match_score)
            match_profiles: List of relevant profiles identified (dicts with keys: name, title, profile_url, company, searched_job_title)

        Returns:
            str: HTML email body
        """
        logging.getLogger(__name__).info(
            f"[ENTER] {__file__}::{self.__class__.__name__}._compose_html_body"
        )
        title = job_data.get("title", "Unknown")
        company = job_data.get("company", "Unknown")
        match_score = job_data.get("match_score", 0)
        job_url = job_data.get("job_url", "") or job_data.get("url", "")
        score_color = (
            "#28a745"
            if str(match_score).isdigit() and int(match_score) >= 8
            else "#ffc107"
        )

        profiles_html = "".join(
            [
                f"<tr><td>{p.get('name', 'Unknown')}</td><td>{p.get('title', '')}</td><td><a href='{p.get('profile_url', p.get('url', ''))}'>Profile</a></td></tr>"
                for p in (match_profiles or [])
            ]
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
            {profiles_html}
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
