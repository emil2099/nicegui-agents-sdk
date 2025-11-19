from __future__ import annotations

from typing import Any, Callable, AsyncGenerator
from nicegui import ui
from events import AgentEvent, EventPublisher
from agent_service import run_plan_execute

def _stringify(value: Any) -> str:
    if hasattr(value, "name"):
        return f"{value.__class__.__name__}(name={getattr(value, 'name', 'unknown')})"
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json()
    return repr(value)

def format_event_line(event: AgentEvent) -> str:
    if event.data:
        details = ", ".join(f"{key}={_stringify(value)}" for key, value in event.data.items())
    else:
        details = "no payload"
    timestamp = event.timestamp.astimezone().strftime("%H:%M:%S")
    rest = f"{event.event_type} | {details}"
    return f"{timestamp} [{event.source}] {rest}"

async def log_event_to_ui(event_log: ui.log | None, event: AgentEvent) -> None:
    if event_log is None:
        return
    event_log.push(format_event_line(event))

async def run_agent_cycle(
    prompt: str,
    event_publisher: EventPublisher,
    output_callback: Callable[[str], None],
) -> None:
    """Runs the agent and streams output to the callback."""
    stream = run_plan_execute(prompt, event_publisher=event_publisher)
    chunks: list[str] = []
    async for chunk in stream:
        if chunk:
            chunks.append(chunk)
            output_callback("".join(chunks))
    
    if not chunks:
        output_callback("(no response)")
