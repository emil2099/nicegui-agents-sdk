from __future__ import annotations

from typing import Any
from nicegui import ui
from agentic.core.events import AgentEvent

class AgentLogger:
    """Component for logging agent events to a NiceGUI log element."""
    
    def __init__(self, log_element: ui.log, wrap: bool = True):
        self.log_element = log_element
        if wrap:
            self.log_element.style('white-space: pre-wrap')

    def _stringify(self, value: Any) -> str:
        if hasattr(value, "name"):
            return f"{value.__class__.__name__}(name={getattr(value, 'name', 'unknown')})"
        if hasattr(value, "model_dump_json"):
            return value.model_dump_json()
        return repr(value)

    def format_event_line(self, event: AgentEvent) -> str:
        if event.data:
            details = ", ".join(f"{key}={self._stringify(value)}" for key, value in event.data.items())
        else:
            details = "no payload"
        timestamp = event.timestamp.astimezone().strftime("%H:%M:%S")
        rest = f"{event.event_type} | {details}"
        return f"{timestamp} [{event.source}] {rest}"

    async def handle_event(self, event: AgentEvent) -> None:
        """Async handler compatible with EventPublisher."""
        self.log_element.push(self.format_event_line(event))

    def clear(self) -> None:
        self.log_element.clear()

    def push(self, message: str) -> None:
        self.log_element.push(message)
