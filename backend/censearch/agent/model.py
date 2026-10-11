"""One provider switch and process-wide model pacing, including rate-limit retries."""

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import threading
import time
from strands.models.openai import OpenAIModel
from strands.types.exceptions import ModelThrottledException


class ModelRateLimitExhausted(RuntimeError):
    """Bounded retries exhausted; do not let Strands start another retry cycle."""


class ModelLimiter:
    """Space request starts to at most 45/minute across all agents in this process.

    A threading lock also supports callers on different event loops. No lock is
    held during I/O or sleep. Other team processes still share the provider quota;
    a 429 therefore pauses all local callers before bounded retries.
    """

    def __init__(self, rpm=45, clock=time.monotonic, sleep=asyncio.sleep):
        self.interval = 60 / rpm
        self.clock = clock
        self.sleep = sleep
        self.lock = threading.Lock()
        self.next_start = 0.0

    async def acquire(self):
        while True:
            with self.lock:
                now = self.clock()
                delay = self.next_start - now
                if delay <= 0:
                    self.next_start = now + self.interval
                    return
            await self.sleep(delay)

    def defer(self, seconds):
        with self.lock:
            self.next_start = max(self.next_start, self.clock() + seconds)


MODEL_LIMITER = ModelLimiter()


def retry_delay(error, attempt):
    response = getattr(error.__cause__, "response", None)
    value = response.headers.get("retry-after") if response is not None else None
    if value:
        try:
            return max(0, float(value))
        except ValueError:
            try:
                when = parsedate_to_datetime(value)
                return max(0, (when - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
    return 5 * (2 ** attempt)


def model_metrics(model):
    return dict(getattr(model, "metrics", {}))


class ChatModel(OpenAIModel):
    def __init__(self, *args, limiter=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.limiter = limiter if limiter is not None else MODEL_LIMITER
        self.metrics = {"turns": 0, "requests": 0, "rate_limit_responses": 0}

    def format_request(self, *args, **kwargs):
        request = super().format_request(*args, **kwargs)
        # The Akamai endpoint rejects an empty tools array, which tool-less agents send.
        if not request.get("tools"):
            request.pop("tools", None)
            request.pop("tool_choice", None)
        else:
            request["parallel_tool_calls"] = True
        return request

    async def stream(self, *args, **kwargs):
        self.metrics["turns"] += 1
        for attempt in range(3):
            await self.limiter.acquire()
            self.metrics["requests"] += 1
            emitted = False
            try:
                async for event in super().stream(*args, **kwargs):
                    emitted = True
                    yield event
                return
            except ModelThrottledException as error:
                self.metrics["rate_limit_responses"] += 1
                delay = retry_delay(error, attempt)
                # Respect long Retry-After for other callers, but do not keep this
                # invocation alive indefinitely or replay a partially emitted turn.
                self.limiter.defer(delay)
                if emitted or attempt == 2 or delay > 120:
                    raise ModelRateLimitExhausted("Model rate-limit retries exhausted") from None


def build_model(settings):
    if settings.model_provider != "openai_compatible":
        raise ValueError("Unsupported MODEL_PROVIDER; expected openai_compatible")
    if not settings.model_configured:
        return None
    return ChatModel(
        client_args={
            "api_key": settings.openai_api_key.get_secret_value(),
            "base_url": settings.openai_base_url,
            "max_retries": 0,
            "timeout": 30,
        },
        model_id=settings.chat_model,
        params={"max_tokens": settings.model_max_tokens, "temperature": 0},
    )
