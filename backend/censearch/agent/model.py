"""One provider switch. Akamai uses chat completions, never Responses or images."""

from strands.models.openai import OpenAIModel


def build_model(settings):
    if settings.model_provider != "openai_compatible":
        raise ValueError("Unsupported MODEL_PROVIDER; expected openai_compatible")
    if not settings.model_configured:
        return None
    return OpenAIModel(
        client_args={
            "api_key": settings.openai_api_key.get_secret_value(),
            "base_url": settings.openai_base_url,
            "max_retries": 0,
            "timeout": 30,
        },
        model_id=settings.chat_model,
        params={"max_tokens": settings.model_max_tokens, "temperature": 0},
    )
