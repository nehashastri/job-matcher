"""
Phase 7 Tests: Email Notifications
Tests email sending, SMTP failures, authentication errors
"""

import smtplib
from unittest.mock import MagicMock, patch

import pytest
from config.config import Config
from notifications.email_notifier import EmailNotifier


@pytest.fixture
def config():
    """Create a config object with email settings"""
    config = Config()
    config.smtp_server = "smtp.gmail.com"
    config.smtp_port = 587
    config.smtp_username = "test@gmail.com"
    config.smtp_password = "testpassword"
    config.email_from = "test@gmail.com"
    config.email_to = "recipient@gmail.com"
    config.enable_email_notifications = True
    return config


@pytest.fixture
def sample_job():
    """Create sample job data"""
    return {
        "title": "Senior Software Engineer",
        "company": "Acme Corp",
        "location": "San Francisco, CA",
        "match_score": 9,
        "job_url": "https://linkedin.com/jobs/view/12345",
        "applicants": "50 applicants",
        "posted_date": "2 days ago",
        "seniority": "Mid-Senior level",
        "remote": "Remote",
    }


class TestEmailNotifierInit:
    """Test EmailNotifier initialization"""

    def test_init_with_config(self, config):
        """Test initialization with valid config"""
        notifier = EmailNotifier(config)

        assert notifier.smtp_server == "smtp.gmail.com"
        assert notifier.smtp_port == 587
        assert notifier.smtp_username == "test@gmail.com"
        assert notifier.email_from == "test@gmail.com"
        assert notifier.email_to == "recipient@gmail.com"
        assert notifier.enabled is True

    def test_init_with_disabled_notifications(self, config):
        """Test initialization with disabled notifications"""
        config.enable_email_notifications = False
        notifier = EmailNotifier(config)

        assert notifier.enabled is False


class TestEmailValidation:
    """Test email configuration validation"""

    def test_validate_config_success(self, config):
        """Test validation with valid config"""
        notifier = EmailNotifier(config)
        assert notifier._validate_config() is True

    def test_validate_config_missing_server(self, config):
        """Test validation fails with missing SMTP server"""
        config.smtp_server = ""
        notifier = EmailNotifier(config)
        assert notifier._validate_config() is False

    def test_validate_config_missing_username(self, config):
        """Test validation fails with missing username"""
        config.smtp_username = ""
        notifier = EmailNotifier(config)
        assert notifier._validate_config() is False

    def test_validate_config_missing_password(self, config):
        """Test validation fails with missing password"""
        config.smtp_password = ""
        notifier = EmailNotifier(config)
        assert notifier._validate_config() is False

    def test_validate_config_missing_from(self, config):
        """Test validation fails with missing email_from"""
        config.email_from = ""
        notifier = EmailNotifier(config)
        assert notifier._validate_config() is False

    def test_validate_config_missing_to(self, config):
        """Test validation fails with missing email_to"""
        config.email_to = ""
        notifier = EmailNotifier(config)
        assert notifier._validate_config() is False


class TestEmailComposition:
    """Test email composition functions"""

    def test_compose_subject(self, config, sample_job):
        """Test subject line composition"""
        notifier = EmailNotifier(config)
        subject = notifier._compose_subject(sample_job)

        assert "Senior Software Engineer" in subject
        assert "Acme Corp" in subject
        assert "🎯" in subject

    def test_compose_body(self, config, sample_job):
        """Test plain text body composition"""
        notifier = EmailNotifier(config)
        body = notifier._compose_body(sample_job, connection_count=5)

        assert "Senior Software Engineer" in body
        assert "Acme Corp" in body
        assert "San Francisco, CA" in body
        assert "9/10" in body
        assert "Connection Requests Sent: 5" in body
        assert "https://linkedin.com/jobs/view/12345" in body

    def test_compose_html_body(self, config, sample_job):
        """Test HTML body composition"""
        notifier = EmailNotifier(config)
        html = notifier._compose_html_body(sample_job, connection_count=3)

        assert "<html>" in html
        assert "Senior Software Engineer" in html
        assert "Acme Corp" in html
        assert "San Francisco, CA" in html
        assert "9/10" in html
        assert "Connection Requests Sent:</span>" in html
        assert "<span>3</span>" in html
        assert "https://linkedin.com/jobs/view/12345" in html

    def test_compose_body_with_unknown_fields(self, config):
        """Test body composition handles missing fields"""
        notifier = EmailNotifier(config)
        job = {"title": "Engineer"}  # Minimal job data
        body = notifier._compose_body(job, connection_count=0)

        assert "Engineer" in body
        assert "Unknown" in body  # Missing fields default to "Unknown"


class TestEmailSending:
    """Test email sending functionality"""

    @patch("notifications.email_notifier.smtplib.SMTP")
    def test_send_job_notification_success(self, mock_smtp, config, sample_job):
        """Test successful email sending"""
        # Mock SMTP server
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        notifier = EmailNotifier(config)
        result = notifier.send_job_notification(sample_job, connection_count=5)

        assert result is True
        mock_smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=30)
        mock_server.ehlo.assert_called()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@gmail.com", "testpassword")
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()

    def test_send_job_notification_disabled(self, config, sample_job):
        """Test email sending when notifications are disabled"""
        config.enable_email_notifications = False
        notifier = EmailNotifier(config)

        result = notifier.send_job_notification(sample_job, connection_count=0)

        assert result is False

    def test_send_job_notification_invalid_config(self, config, sample_job):
        """Test email sending fails with invalid config"""
        config.smtp_server = ""
        notifier = EmailNotifier(config)

        result = notifier.send_job_notification(sample_job, connection_count=0)

        assert result is False

    @patch("notifications.email_notifier.smtplib.SMTP")
    def test_send_job_notification_auth_error(self, mock_smtp, config, sample_job):
        """Test email sending handles authentication error"""
        mock_smtp.return_value.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b"Invalid credentials"
        )

        notifier = EmailNotifier(config)
        result = notifier.send_job_notification(sample_job, connection_count=0)

        assert result is False

    @patch("notifications.email_notifier.smtplib.SMTP")
    def test_send_job_notification_smtp_error(self, mock_smtp, config, sample_job):
        """Test email sending handles SMTP error"""
        mock_smtp.return_value.send_message.side_effect = smtplib.SMTPException(
            "Server error"
        )

        notifier = EmailNotifier(config)
        result = notifier.send_job_notification(sample_job, connection_count=0)

        assert result is False

    @patch("notifications.email_notifier.smtplib.SMTP")
    def test_send_job_notification_connection_error(
        self, mock_smtp, config, sample_job
    ):
        """Test email sending handles connection error"""
        mock_smtp.side_effect = smtplib.SMTPConnectError(421, b"Service not available")

        notifier = EmailNotifier(config)
        result = notifier.send_job_notification(sample_job, connection_count=0)

        assert result is False

    @patch("notifications.email_notifier.smtplib.SMTP")
    def test_send_job_notification_server_disconnected(
        self, mock_smtp, config, sample_job
    ):
        """Test email sending handles server disconnection"""
        mock_smtp.return_value.starttls.side_effect = smtplib.SMTPServerDisconnected(
            "Connection unexpectedly closed"
        )

        notifier = EmailNotifier(config)
        result = notifier.send_job_notification(sample_job, connection_count=0)

        assert result is False

    @patch("notifications.email_notifier.smtplib.SMTP")
    def test_send_job_notification_unexpected_error(
        self, mock_smtp, config, sample_job
    ):
        """Test email sending handles unexpected error"""
        mock_smtp.return_value.login.side_effect = Exception("Unexpected error")

        notifier = EmailNotifier(config)
        result = notifier.send_job_notification(sample_job, connection_count=0)

        assert result is False


class TestSMTPConnection:
    """Test SMTP connection functionality"""

    @patch("notifications.email_notifier.smtplib.SMTP")
    def test_connection_test_success(self, mock_smtp, config):
        """Test successful SMTP connection test"""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        notifier = EmailNotifier(config)
        result = notifier.test_connection()

        assert result is True
        mock_smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=30)
        mock_server.ehlo.assert_called()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@gmail.com", "testpassword")
        mock_server.quit.assert_called_once()

    def test_connection_test_invalid_config(self, config):
        """Test connection test fails with invalid config"""
        config.smtp_server = ""
        notifier = EmailNotifier(config)

        result = notifier.test_connection()

        assert result is False

    @patch("notifications.email_notifier.smtplib.SMTP")
    def test_connection_test_auth_error(self, mock_smtp, config):
        """Test connection test handles authentication error"""
        mock_smtp.return_value.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b"Invalid credentials"
        )

        notifier = EmailNotifier(config)
        result = notifier.test_connection()

        assert result is False

    @patch("notifications.email_notifier.smtplib.SMTP")
    def test_connection_test_smtp_error(self, mock_smtp, config):
        """Test connection test handles SMTP error"""
        mock_smtp.side_effect = smtplib.SMTPException("Connection failed")

        notifier = EmailNotifier(config)
        result = notifier.test_connection()

        assert result is False

    @patch("notifications.email_notifier.smtplib.SMTP")
    def test_connection_test_timeout(self, mock_smtp, config):
        """Test connection test handles timeout"""
        mock_smtp.side_effect = TimeoutError("Connection timed out")

        notifier = EmailNotifier(config)
        result = notifier.test_connection()

        assert result is False


class TestEmailEdgeCases:
    """Test edge cases and corner scenarios"""

    @patch("notifications.email_notifier.smtplib.SMTP")
    def test_send_with_zero_connections(self, mock_smtp, config, sample_job):
        """Test email sending with zero connection requests"""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        notifier = EmailNotifier(config)
        result = notifier.send_job_notification(sample_job, connection_count=0)

        assert result is True

    @patch("notifications.email_notifier.smtplib.SMTP")
    def test_send_with_high_connection_count(self, mock_smtp, config, sample_job):
        """Test email sending with high connection count"""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        notifier = EmailNotifier(config)
        result = notifier.send_job_notification(sample_job, connection_count=100)

        assert result is True

    @patch("notifications.email_notifier.smtplib.SMTP")
    def test_send_with_special_characters_in_job(self, mock_smtp, config):
        """Test email sending with special characters in job data"""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        job = {
            "title": "C++ & Python Engineer (Sr.)",
            "company": "Tech Co. & Partners",
            "location": "São Paulo, Brazil",
            "match_score": 8,
            "job_url": "https://linkedin.com/jobs/view/12345?param=value&other=123",
        }

        notifier = EmailNotifier(config)
        result = notifier.send_job_notification(job, connection_count=5)

        assert result is True

    @patch("notifications.email_notifier.smtplib.SMTP")
    def test_send_with_unicode_in_job(self, mock_smtp, config):
        """Test email sending with Unicode characters"""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        job = {
            "title": "软件工程师",
            "company": "北京科技公司",
            "location": "北京, 中国",
            "match_score": 9,
            "job_url": "https://linkedin.com/jobs/view/12345",
        }

        notifier = EmailNotifier(config)
        result = notifier.send_job_notification(job, connection_count=3)

        assert result is True

    def test_compose_with_missing_job_url(self, config):
        """Test composition handles missing job URL"""
        job = {
            "title": "Engineer",
            "company": "TechCorp",
            "location": "Remote",
            "match_score": 8,
        }

        notifier = EmailNotifier(config)
        body = notifier._compose_body(job, connection_count=0)

        assert "Engineer" in body
        assert "TechCorp" in body

    def test_compose_with_low_match_score(self, config):
        """Test HTML body uses correct color for low match score"""
        job = {
            "title": "Engineer",
            "company": "TechCorp",
            "match_score": 6,
            "job_url": "https://example.com",
        }

        notifier = EmailNotifier(config)
        html = notifier._compose_html_body(job, connection_count=0)

        # Low score should use warning color
        assert "#ffc107" in html or "#28a745" in html

    def test_compose_with_high_match_score(self, config):
        """Test HTML body uses correct color for high match score"""
        job = {
            "title": "Engineer",
            "company": "TechCorp",
            "match_score": 10,
            "job_url": "https://example.com",
        }

        notifier = EmailNotifier(config)
        html = notifier._compose_html_body(job, connection_count=0)

        # High score should use success color
        assert "#28a745" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
