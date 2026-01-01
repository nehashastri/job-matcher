"""Tests for Phase 4: sponsorship filter."""

from types import SimpleNamespace

from config.config import Config
from matching.sponsorship_filter import SponsorshipFilter


class DummyResponsesClient:
    """Minimal stub to mimic OpenAI responses.create output."""

    def __init__(self, payload: str):
        self.payload = payload

    def _build_response(self):
        return SimpleNamespace(
            output=[SimpleNamespace(content=[SimpleNamespace(text=self.payload)])]
        )

    def create(self, **kwargs):  # pragma: no cover - compatibility guard
        return self._build_response()

    responses = property(lambda self: self)


def make_client(payload: str) -> DummyResponsesClient:
    return DummyResponsesClient(payload)


class TestSponsorshipFilter:
    def test_rejects_when_no_sponsorship(self, mock_env, mock_blocklist_json, monkeypatch):
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))
        config = Config()
        client = make_client(
            '{"accepts_sponsorship": false, "reason": "explicitly states no sponsorship"}'
        )

        checker = SponsorshipFilter(openai_client=client, config=config)
        result = checker.check("This role does not provide visa sponsorship.")

        assert result["accepts_sponsorship"] is False
        assert "no sponsorship" in result["reason"].lower()

    def test_accepts_when_sponsorship_offered(self, mock_env, mock_blocklist_json, monkeypatch):
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))
        config = Config()
        client = make_client('{"accepts_sponsorship": true, "reason": "mentions visa sponsorship"}')

        checker = SponsorshipFilter(openai_client=client, config=config)
        result = checker.check("We sponsor H-1B and TN visas for qualified candidates.")

        assert result["accepts_sponsorship"] is True
        assert "sponsor" in result["reason"].lower()

    def test_disabled_flag_skips_check(self, mock_env, mock_blocklist_json, monkeypatch):
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))
        monkeypatch.setenv("REQUIRES_SPONSORSHIP", "false")
        config = Config()
        client = make_client('{"accepts_sponsorship": false, "reason": "irrelevant"}')

        checker = SponsorshipFilter(openai_client=client, config=config)
        result = checker.check("We do not sponsor visas.")

        assert result["accepts_sponsorship"] is True
        assert "disabled" in result["reason"]

    def test_invalid_json_defaults_to_accept(self, mock_env, mock_blocklist_json, monkeypatch):
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))
        config = Config()
        client = make_client("not valid json")

        checker = SponsorshipFilter(openai_client=client, config=config)
        result = checker.check("Sponsorship unclear.")

        assert result["accepts_sponsorship"] is True
        assert "llm error" in result["reason"].lower()

    def test_missing_sponsorship_language_assumes_accept(
        self, mock_env, mock_blocklist_json, monkeypatch
    ):
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))
        config = Config()
        # Return a rejecting payload; heuristic should short-circuit before LLM
        client = make_client('{"accepts_sponsorship": false, "reason": "irrelevant"}')

        checker = SponsorshipFilter(openai_client=client, config=config)
        result = checker.check("We build delightful products for our customers.")

        assert result["accepts_sponsorship"] is True
        assert "no sponsorship info" in result["reason"].lower()

    def test_rejects_international_not_allowed(self, mock_env, mock_blocklist_json, monkeypatch):
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))
        config = Config()
        # Strong negative phrase should short-circuit before LLM
        client = make_client('{"accepts_sponsorship": true, "reason": "irrelevant"}')

        checker = SponsorshipFilter(openai_client=client, config=config)
        result = checker.check("We cannot hire international candidates or provide visas.")

        assert result["accepts_sponsorship"] is False
        assert "international" in result["reason"].lower()

    def test_rejects_us_citizens_only(self, mock_env, mock_blocklist_json, monkeypatch):
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))
        config = Config()
        client = make_client('{"accepts_sponsorship": true, "reason": "irrelevant"}')

        checker = SponsorshipFilter(openai_client=client, config=config)
        result = checker.check("US citizens only. Permanent work authorization required.")

        assert result["accepts_sponsorship"] is False
        assert "citizen" in result["reason"].lower()

    def test_rejects_permanent_authorization_required(
        self, mock_env, mock_blocklist_json, monkeypatch
    ):
        monkeypatch.setenv("BLOCKLIST_PATH", str(mock_blocklist_json))
        config = Config()
        client = make_client('{"accepts_sponsorship": true, "reason": "irrelevant"}')

        checker = SponsorshipFilter(openai_client=client, config=config)
        result = checker.check(
            "Must have permanent work authorization; no OPT/CPT or sponsorship offered."
        )

        assert result["accepts_sponsorship"] is False
        assert "permanent" in result["reason"].lower()
