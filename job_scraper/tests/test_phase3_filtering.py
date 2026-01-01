"""Tests for Phase 3: blocklist and HR checker."""

import json
from types import SimpleNamespace

from config.config import Config
from filtering.blocklist import Blocklist
from matching.hr_checker import HRChecker


class DummyResponsesClient:
    """Minimal stub to mimic OpenAI responses.create output."""

    def __init__(self, payload: str):
        self.payload = payload

    def responses(self):  # pragma: no cover - compatibility guard
        return self

    def create(self, **kwargs):  # pragma: no cover - compatibility guard
        return self._build_response()

    def _build_response(self):
        return SimpleNamespace(
            output=[SimpleNamespace(content=[SimpleNamespace(text=self.payload)])]
        )

    # Support both client.responses.create and client.create patterns
    responses = property(lambda self: self)


def make_client(payload: str) -> DummyResponsesClient:
    return DummyResponsesClient(payload)


class TestBlocklist:
    def test_blocklist_exact_and_pattern_match(self, mock_env, mock_blocklist_json, monkeypatch):
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))
        blocklist = Blocklist(file_path=mock_blocklist_json)

        assert blocklist.is_blocked("Lensa") is True
        assert blocklist.is_blocked("Amazing Recruiting Group") is True
        assert blocklist.is_blocked("Product Corp") is False

    def test_blocklist_add_persists(self, mock_env, mock_blocklist_json, monkeypatch):
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))
        blocklist = Blocklist(file_path=mock_blocklist_json)

        added = blocklist.add("NewCompany")

        assert added is True
        assert blocklist.is_blocked("NewCompany") is True

        with open(mock_blocklist_json, encoding="utf-8") as f:
            data = json.load(f)
        assert "NewCompany" in data["blocklist"]


class TestHRChecker:
    def test_hr_company_rejected_and_blocklisted(self, mock_env, mock_blocklist_json, monkeypatch):
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))
        config = Config()
        blocklist = Blocklist(file_path=mock_blocklist_json, config=config)
        client = make_client('{"is_hr_company": true, "reason": "staffing"}')

        checker = HRChecker(openai_client=client, config=config, blocklist=blocklist)
        result = checker.check("Talent Recruiters LLC", description="contract hiring")

        assert result["is_hr_company"] is True
        assert blocklist.is_blocked("Talent Recruiters LLC") is True

        with open(mock_blocklist_json, encoding="utf-8") as f:
            data = json.load(f)
        assert "Talent Recruiters LLC" in data["blocklist"]

    def test_non_hr_company_passes(self, mock_env, mock_blocklist_json, monkeypatch):
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))
        config = Config()
        blocklist = Blocklist(file_path=mock_blocklist_json, config=config)
        client = make_client('{"is_hr_company": false, "reason": "product company"}')

        checker = HRChecker(openai_client=client, config=config, blocklist=blocklist)
        result = checker.check("Tech Products Inc", description="building devices")

        assert result["is_hr_company"] is False
        assert blocklist.is_blocked("Tech Products Inc") is False

        with open(mock_blocklist_json, encoding="utf-8") as f:
            data = json.load(f)
        assert "Tech Products Inc" not in data["blocklist"]

    def test_invalid_json_defaults_to_reject(self, mock_env, mock_blocklist_json, monkeypatch):
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))
        config = Config()
        blocklist = Blocklist(file_path=mock_blocklist_json, config=config)
        client = make_client("not valid json")

        checker = HRChecker(openai_client=client, config=config, blocklist=blocklist)
        result = checker.check("Unknown Staffing", description="irrelevant text")

        assert result["is_hr_company"] is False
        assert blocklist.is_blocked("Unknown Staffing") is False

        with open(mock_blocklist_json, encoding="utf-8") as f:
            data = json.load(f)
        assert "Unknown Staffing" not in data["blocklist"]
