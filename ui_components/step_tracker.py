from __future__ import annotations

from typing import Any

from nicegui import ui

from events import AgentEvent


class StepTracker(ui.list):
    """Simple expansion-backed list that mirrors agent progress."""

    def __init__(self) -> None:
        super().__init__()
        self.classes('w-full max-w-xl rounded-borders').props('bordered dense')

        with self:
            self._expansion = ui.expansion(text="Agent ready to go", icon="o_task", value=False).props('dense').classes('w-full')
            
            with self._expansion:
                ui.query('.nicegui-expansion .q-expansion-item__content').style('padding:0',replace='gap:0')
                self._event_list = ui.list().props('dense').classes('w-full text-sm')

        self._base_label = "Agent steps"
        self._step_index = 0

    async def handle_event(self, event: AgentEvent) -> None:
        """Async subscriber compatible with EventPublisher."""
        self._step_index += 1
        summary = self._summarize_event(event)
        self._append_item(summary)
        self._update_title(summary)

    def _append_item(self, summary: str) -> None:
        with self._event_list:
            item = ui.item(text=summary).props('clickable').classes('break-words w-full')
    @staticmethod
    def _summarize_event(event: AgentEvent) -> str:
        source = event.source
        data = event.data or {}
        event_type = event.event_type

        if event_type == "agent_started_stream_event":
            return f"{source} started planning"
        if event_type == "agent_ended_stream_event":
            return f"{source} delivered the response"
        if event_type == "agent_handoff_stream_event":
            to_agent = StepTracker._agent_name(data.get("to_agent"))
            return f"{source} handed off to {to_agent}"
        if event_type == "llm_started_stream_event":
            return f"{source} is thinking"
        if event_type == "llm_ended_stream_event":
            return f"{source} finished reasoning"
        if event_type == "tool_started_stream_event":
            tool = StepTracker._tool_name(data.get("tool"))
            return f"{source} is using {tool}"
        if event_type == "tool_ended_stream_event":
            tool = StepTracker._tool_name(data.get("tool"))
            result_preview = StepTracker._preview_text(data.get("result"))
            return f"{source} finished {tool}{result_preview}"
        if event_type == "tool_random_number_event":
            value = data.get("result")
            max_value = data.get("max")
            return f"Random number tool returned {value} (max {max_value})"

        friendly = event_type.replace('_stream_event', '').replace('_', ' ')
        return f"{friendly.capitalize()} – {source}"

    @staticmethod
    def _agent_name(agent: Any) -> str:
        if hasattr(agent, "name"):
            return getattr(agent, "name")
        return str(agent)

    @staticmethod
    def _tool_name(tool: Any) -> str:
        if hasattr(tool, "name"):
            return getattr(tool, "name")
        return str(tool) if tool else "a tool"

    @staticmethod
    def _preview_text(result: Any) -> str:
        if not result:
            return ""
        text = str(result)
        if len(text) > 80:
            text = text[:77] + "…"
        return f" → {text}"

    def reset(self) -> None:
        self._step_index = 0
        self._event_list.clear()
        self._expansion.text = self._base_label

    def _update_title(self, summary: str) -> None:
        self._expansion.text = f"Step {self._step_index}: {summary}"
