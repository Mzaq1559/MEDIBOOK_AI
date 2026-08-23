from app.config import settings
from app.groq_client import complete


def test_groq_model_from_env_completes():
    assert settings.GROQ_MODEL
    assert settings.GROQ_MODEL != "mixtral-8x7b-32768"
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
