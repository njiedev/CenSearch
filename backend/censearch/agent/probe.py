"""Small Strands agent with actual tool-call results returned to the console."""

import asyncio
import time
from strands import Agent
from strands.hooks import AfterToolCallEvent
from strands.types.agent import Limits
from censearch.agent.model import build_model
from censearch.agent.tools import dns_lookup


class ToolTrace:
    def __init__(self):
        self.calls = []

    def register_hooks(self, registry, **kwargs):
        registry.add_callback(AfterToolCallEvent, self.after)

    def after(self, event):
        self.calls.append({"tool_use": event.tool_use, "result": event.result})


class Probe:
    def __init__(self, settings):
        self.settings = settings
        self.lock = asyncio.Lock()
        self.last_started = 0.0
        self.live_call_verified = False

    async def run(self, hostname):
        if not self.settings.model_configured:
            return {
                "status": "model_not_configured",
                "answer": None,
                "tool_calls": [],
                "message": "Model not configured. Set OPENAI_API_KEY in backend/.env.",
            }
        async with self.lock:
            # At most one three-call probe per 6 seconds in this process.
            await asyncio.sleep(max(0, self.last_started + 6 - time.monotonic()))
            self.last_started = time.monotonic()
            trace = ToolTrace()
            agent = Agent(
                model=build_model(self.settings),
                tools=[dns_lookup],
                hooks=[trace],
                callback_handler=None,
                system_prompt=(
                    "Resolve the supplied hostname with dns_lookup, then summarize only its result. "
                    "Do not infer identity, ownership, consent or a removal route."
                ),
            )
            try:
                result = await agent.invoke_async(
                    f"Resolve this hostname using the tool: {hostname}",
                    limits=Limits(turns=3),
                )
                self.live_call_verified = True
                return {
                    "status": "completed",
                    "answer": str(result),
                    "tool_calls": trace.calls,
                    "message": None,
                }
            except Exception as error:
                # Never echo provider exception messages: some include headers or credentials.
                return {
                    "status": "model_error",
                    "answer": None,
                    "tool_calls": trace.calls,
                    "message": "Model invocation failed: " + type(error).__name__,
                }
