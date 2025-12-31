"""
Unit tests for configuration module (Phase 0)
"""

import json

from config.config import Config, get_config, reload_config


class TestConfigLoading:
    """Test configuration loading from environment and JSON files"""

    def test_config_loads_env_variables(self, mock_env, monkeypatch):
        """Test that Config loads values from environment variables"""
        config = Config()

        assert config.openai_api_key == "test-api-key"
        assert config.openai_model == "gpt-4o-mini"
        assert config.job_match_threshold == 8.0
        assert config.linkedin_email == "test@example.com"
        assert config.linkedin_password == "test_password"
        assert config.scrape_interval_minutes == 30
        assert config.max_retries == 5
        assert config.max_applicants == 100
        assert config.requires_sponsorship is True
        assert config.skip_viewed_jobs is True

    def test_config_loads_roles_json(self, mock_env, mock_roles_json, monkeypatch):
        """Test that Config loads roles from JSON file"""
        monkeypatch.setenv("ROLES_PATH", str(mock_roles_json))
        config = Config()

        assert len(config.roles) == 2
        assert config.roles[0]["title"] == "Software Engineer"
        assert config.roles[0]["enabled"] is True
        assert config.roles[1]["title"] == "Data Engineer"
        assert config.roles[1]["enabled"] is False
        assert config.search_settings["date_posted"] == "r86400"

    def test_config_loads_blocklist_json(self, mock_env, mock_blocklist_json, monkeypatch):
        """Test that Config loads blocklist from JSON file"""
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))
        config = Config()

        assert len(config.blocklist) == 3
        assert "Lensa" in config.blocklist
        assert "Dice" in config.blocklist
        assert len(config.blocklist_patterns) == 2
        assert ".*[Rr]ecruiting.*" in config.blocklist_patterns

    def test_config_handles_missing_json_files(self, mock_env):
        """Test that Config handles missing JSON files gracefully"""
        config = Config()

        # Should not crash, just have empty lists
        assert isinstance(config.roles, list)
        assert isinstance(config.blocklist, list)
        assert isinstance(config.blocklist_patterns, list)

    def test_config_default_values(self):
        """Test that Config has sensible defaults"""
        config = Config()

        # Should have defaults even without env vars
        assert config.openai_model == "gpt-4o-mini"
        assert config.job_match_threshold == 8.0
        assert config.scrape_interval_minutes == 30
        assert config.max_retries == 5


class TestConfigValidation:
    """Test configuration validation"""

    def test_validate_missing_required_fields(self, monkeypatch, temp_dir):
        """Test validation fails when required fields are missing"""
        # Clear required env vars
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("LINKEDIN_EMAIL", "")
        monkeypatch.setenv("LINKEDIN_PASSWORD", "")

        config = Config()
        errors = config.validate()

        assert len(errors) > 0
        assert any("OPENAI_API_KEY" in err for err in errors)
        assert any("LINKEDIN_EMAIL" in err for err in errors)
        assert any("LINKEDIN_PASSWORD" in err for err in errors)

    def test_validate_missing_files(self, mock_env, monkeypatch):
        """Test validation fails when required files are missing"""
        monkeypatch.setenv("RESUME_PATH", "./nonexistent_resume.pdf")

        config = Config()
        errors = config.validate()

        assert len(errors) > 0
        assert any("Resume file not found" in err for err in errors)

    def test_validate_invalid_threshold(self, mock_env, monkeypatch):
        """Test validation fails when threshold is out of range"""
        monkeypatch.setenv("JOB_MATCH_THRESHOLD", "15")

        config = Config()
        errors = config.validate()

        assert len(errors) > 0
        assert any("must be between 0 and 10" in err for err in errors)

    def test_validate_success(
        self, mock_env, mock_roles_json, mock_resume_file, mock_preferences_file, monkeypatch
    ):
        """Test validation succeeds with all required fields"""
        monkeypatch.setenv("ROLES_PATH", str(mock_roles_json))
        monkeypatch.setenv("RESUME_PATH", str(mock_resume_file))
        monkeypatch.setenv("PREFERENCES_PATH", str(mock_preferences_file))

        config = Config()
        errors = config.validate()

        assert len(errors) == 0


class TestConfigMethods:
    """Test configuration helper methods"""

    def test_get_enabled_roles(self, mock_env, mock_roles_json, monkeypatch):
        """Test getting only enabled roles"""
        monkeypatch.setenv("ROLES_PATH", str(mock_roles_json))

        config = Config()
        enabled_roles = config.get_enabled_roles()

        assert len(enabled_roles) == 1
        assert enabled_roles[0]["title"] == "Software Engineer"

    def test_add_to_blocklist(self, mock_env, mock_blocklist_json, monkeypatch, temp_dir):
        """Test adding a company to the blocklist"""
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))

        config = Config()
        initial_count = len(config.blocklist)

        # Add new company
        result = config.add_to_blocklist("NewCompany")
        assert result is True
        assert "NewCompany" in config.blocklist
        assert len(config.blocklist) == initial_count + 1

        # Verify it was saved to file
        with open(mock_blocklist_json, encoding="utf-8") as f:
            data = json.load(f)
            assert "NewCompany" in data["blocklist"]

    def test_add_duplicate_to_blocklist(self, mock_env, mock_blocklist_json, monkeypatch):
        """Test adding a duplicate company to the blocklist"""
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))

        config = Config()

        # Add existing company
        result = config.add_to_blocklist("Lensa")
        assert result is False

        # Blocklist should not grow
        assert config.blocklist.count("Lensa") == 1


class TestGlobalConfig:
    """Test global config instance management"""

    def test_get_config_returns_singleton(self, mock_env):
        """Test that get_config returns the same instance"""
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

    def test_reload_config_creates_new_instance(self, mock_env):
        """Test that reload_config creates a new instance"""
        config1 = get_config()
        config2 = reload_config()

        assert config1 is not config2
