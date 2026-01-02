"""
Email notification module for job scraper
Sends email alerts for accepted jobs via Gmail SMTP
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict

from config.config import Config

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Handles sending email notifications for matched jobs"""

    def __init__(self, config: Config):
        """
        Initialize email notifier

        Args:
            config: Configuration object with SMTP settings
        """
        self.config = config
        self.smtp_server = config.smtp_server
        self.smtp_port = config.smtp_port
        self.smtp_username = config.smtp_username
        self.smtp_password = config.smtp_password
        self.email_from = config.email_from
        self.email_to = config.email_to
        self.smtp_use_ssl = getattr(config, "smtp_use_ssl", False)
        self.enabled = config.enable_email_notifications

    def send_job_notification(
        self, job_data: Dict[str, Any], connection_count: int = 0
    ) -> bool:
        """
        Send email notification for a matched job

        Args:
            job_data: Dictionary containing job details
            connection_count: Number of connection requests sent

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.enabled:
            logger.info("Email notifications disabled, skipping")
            return False

        if not self._validate_config():
            logger.error("Email configuration invalid, cannot send notification")
            return False

        try:
            # Compose email
            subject = self._compose_subject(job_data)
            body = self._compose_body(job_data, connection_count)

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.email_from
            msg["To"] = self.email_to

            # Attach plain text and HTML versions
            msg.attach(MIMEText(body, "plain"))
            msg.attach(
                MIMEText(self._compose_html_body(job_data, connection_count), "html")
            )

            # Send email
            self._send_email(msg)

            logger.info(
                f"✅ Email notification sent for job: {job_data.get('title', 'Unknown')}"
            )
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"❌ SMTP authentication failed: {e}")
            logger.error("Check SMTP_USERNAME and SMTP_PASSWORD in .env")
            return False

        except smtplib.SMTPException as e:
            logger.error(f"❌ SMTP error occurred: {e}")
            return False

        except Exception as e:
            logger.error(f"❌ Unexpected error sending email: {e}")
            return False

    def _validate_config(self) -> bool:
        """
        Validate email configuration

        Returns:
            bool: True if config is valid, False otherwise
        """
        if not self.smtp_server:
            logger.error("SMTP_SERVER not configured in .env")
            return False
        if not self.smtp_username:
            logger.error("SMTP_USERNAME not configured in .env")
            return False
        if not self.smtp_password:
            logger.error("SMTP_PASSWORD not configured in .env")
            return False
        if not self.email_from:
            logger.error("EMAIL_FROM not configured in .env")
            return False
        if not self.email_to:
            logger.error("EMAIL_TO not configured in .env")
            return False
        return True

    def _send_email(self, msg: MIMEMultipart) -> None:
        """
        Send email via SMTP with TLS

        Args:
            msg: Email message to send

        Raises:
            smtplib.SMTPException: If SMTP error occurs
        """
        try:
            # Prefer SSL when configured or using port 465; otherwise use STARTTLS
            if self.smtp_use_ssl or self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30)
                server.ehlo()
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
                server.ehlo()
                server.starttls()
                server.ehlo()

            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
            server.quit()

        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"❌ SMTP server disconnected: {e}")
            raise
        except smtplib.SMTPConnectError as e:
            logger.error(
                f"❌ Failed to connect to SMTP server {self.smtp_server}:{self.smtp_port}: {e}"
            )
            raise
        except Exception as e:
            logger.error(f"❌ Error during SMTP operation: {e}")
            raise

    def _compose_subject(self, job_data: Dict[str, Any]) -> str:
        """
        Compose email subject line

        Args:
            job_data: Job details

        Returns:
            str: Email subject
        """
        title = job_data.get("title", "Unknown")
        company = job_data.get("company", "Unknown")
        return f"🎯 Job Match: {title} at {company}"

    def _compose_body(self, job_data: Dict[str, Any], connection_count: int) -> str:
        """
        Compose plain text email body

        Args:
            job_data: Job details
            connection_count: Number of connection requests sent

        Returns:
            str: Email body
        """
        title = job_data.get("title", "Unknown")
        company = job_data.get("company", "Unknown")
        location = job_data.get("location", "Unknown")
        match_score = job_data.get("match_score", 0)
        job_url = job_data.get("job_url", "")
        applicants = job_data.get("applicants", "Unknown")
        posted_date = job_data.get("posted_date", "Unknown")
        seniority = job_data.get("seniority", "Unknown")
        remote = job_data.get("remote", "Unknown")

        body = f"""
New Job Match Found!

Job Title: {title}
Company: {company}
Location: {location}
Match Score: {match_score}/10
Seniority: {seniority}
Remote: {remote}
Applicants: {applicants}
Posted: {posted_date}

Connection Requests Sent: {connection_count}

Job URL: {job_url}

---
This is an automated notification from the Job Scraper.
"""
        return body

    def _compose_html_body(
        self, job_data: Dict[str, Any], connection_count: int
    ) -> str:
        """
        Compose HTML email body

        Args:
            job_data: Job details
            connection_count: Number of connection requests sent

        Returns:
            str: HTML email body
        """
        title = job_data.get("title", "Unknown")
        company = job_data.get("company", "Unknown")
        location = job_data.get("location", "Unknown")
        match_score = job_data.get("match_score", 0)
        job_url = job_data.get("job_url", "")
        applicants = job_data.get("applicants", "Unknown")
        posted_date = job_data.get("posted_date", "Unknown")
        seniority = job_data.get("seniority", "Unknown")
        remote = job_data.get("remote", "Unknown")

        # Color code match score
        score_color = "#28a745" if match_score >= 8 else "#ffc107"

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
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
        .job-title {{
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 10px;
            color: #0077b5;
        }}
        .company {{
            font-size: 18px;
            color: #555;
            margin-bottom: 20px;
        }}
        .detail-row {{
            margin: 10px 0;
            padding: 8px;
            background-color: white;
            border-left: 3px solid #0077b5;
        }}
        .label {{
            font-weight: bold;
            display: inline-block;
            width: 140px;
        }}
        .match-score {{
            font-size: 20px;
            font-weight: bold;
            color: {score_color};
        }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            margin: 20px 0;
            background-color: #0077b5;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
        }}
        .footer {{
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            font-size: 12px;
            color: #666;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 New Job Match Found!</h1>
    </div>
    <div class="content">
        <div class="job-title">{title}</div>
        <div class="company">{company}</div>

        <div class="detail-row">
            <span class="label">Location:</span>
            <span>{location}</span>
        </div>

        <div class="detail-row">
            <span class="label">Match Score:</span>
            <span class="match-score">{match_score}/10</span>
        </div>

        <div class="detail-row">
            <span class="label">Seniority:</span>
            <span>{seniority}</span>
        </div>

        <div class="detail-row">
            <span class="label">Remote:</span>
            <span>{remote}</span>
        </div>

        <div class="detail-row">
            <span class="label">Applicants:</span>
            <span>{applicants}</span>
        </div>

        <div class="detail-row">
            <span class="label">Posted:</span>
            <span>{posted_date}</span>
        </div>

        <div class="detail-row">
            <span class="label">Connections Sent:</span>
            <span>{connection_count}</span>
        </div>

        <a href="{job_url}" class="button">View Job on LinkedIn</a>

        <div class="footer">
            This is an automated notification from the Job Scraper.
        </div>
    </div>
</body>
</html>
"""
        return html

    def test_connection(self) -> bool:
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
