from unittest.mock import MagicMock
from app.config import settings
from app.groq_client import complete, complete_json


def test_groq_model_from_env_completes(monkeypatch):
    assert settings.GROQ_MODEL
    assert settings.GROQ_MODEL == settings.GROQ_MODEL

    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "pong"
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    monkeypatch.setattr("app.groq_client._client", lambda: mock_client)

    text = complete(
        [
            {
                "role": "system",
                "content": "Reply with the single word pong and nothing else.",
            },
            {"role": "user", "content": "ping"},
        ],
        max_tokens=16,
        retries=2,
    )
    assert text
    assert "pong" in text.lower()
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == settings.GROQ_MODEL


def test_groq_complete_json(monkeypatch):
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"intent": "appointment", "confirms": true}'
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    monkeypatch.setattr("app.groq_client._client", lambda: mock_client)

    data = complete_json([{"role": "user", "content": "book appointment"}])
    assert isinstance(data, dict)
    assert data.get("intent") == "appointment"
    assert data.get("confirms") is True

