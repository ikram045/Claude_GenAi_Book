import pytest
from pydantic import ValidationError

from genai_toolkit.config import Settings


def test_loads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-long-enough")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.anthropic_api_key.startswith("sk-ant")
    assert s.max_tokens == 16_000


def test_rejects_short_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "short")
    with pytest.raises(ValidationError, match="anthropic_api_key"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_rejects_out_of_range_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-long-enough")
    monkeypatch.setenv("MAX_TOKENS", "0")
    with pytest.raises(ValidationError, match="max_tokens"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_missing_required_field_names_the_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """The payoff over os.environ: the error tells you exactly what's missing."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="anthropic_api_key"):
        Settings(_env_file=None)  # type: ignore[call-arg]
