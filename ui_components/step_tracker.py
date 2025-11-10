from __future__ import annotations

from typing import Any, Optional

from nicegui import ui

from events import AgentEvent


class StepTracker(ui.list):
    """Expansion list that mirrors agent steps with badges and header state."""

    def __init__(self) -> None:
        super().__init__()
        # self.classes('w-full max-w-xl rounded-borders').props('bordered dense')
        self.classes('w-full max-w-xl').props('dense')

        self._base_label = "Agent steps"
        self._step_index = 0
        self._root_agent: Optional[str] = None

        with self:
            self._expansion = ui.expansion(value=False).props('dense').classes('w-full')

            with self._expansion.add_slot('header'):
                with ui.item().classes('w-full items-center px-0').props('dense'):
                    with ui.item_section().props('avatar').classes('items-center justify-center'):
                        self._avatar_icon = ui.icon('smart_toy').classes('text-secondary')
                        self._avatar_spinner = ui.spinner(size='sm').classes('text-primary')
                        self._avatar_check = ui.icon('check_circle').classes('text-positive')
                    with ui.item_section():
                        self._header_label = ui.label(self._base_label).classes('font-medium truncate')

            with self._expansion:
                ui.query('.nicegui-expansion .q-expansion-item__content').style('padding:0', replace='gap:0')
                self._event_list = ui.list().props('dense').classes('w-full text-sm')

        self._set_header_state('idle')

    async def handle_event(self, event: AgentEvent) -> None:
        """Async subscriber compatible with EventPublisher."""
        summary = self._summarize_event(event)
        self._maybe_update_run_state(event)

        self._step_index += 1
        self._append_item(self._step_index, summary)
        self._update_title(summary)

    def _append_item(self, step_number: int, summary: str) -> None:
        with self._event_list:
            with ui.item().props('clickable').classes('w-full'):
                with ui.item_section().props('avatar'):
                    with ui.row().classes('items-center justify-center w-full'):
                        ui.badge(text=str(step_number)).props('color=green-2 text-color=green-9').classes('px-2 py-0.5 rounded-borders text-xs font-medium flex items-center justify-center')
                with ui.item_section():
                    ui.item_label(summary)

    def _maybe_update_run_state(self, event: AgentEvent) -> None:
        if event.event_type == "agent_started_stream_event":
            if self._root_agent is None:
                self._root_agent = event.source
            if event.source == self._root_agent:
                self._set_header_state('running')
        elif event.event_type == "agent_ended_stream_event" and self._root_agent == event.source:
            self._set_header_state('done')

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
        self._root_agent = None
        self._header_label.text = self._base_label
        self._set_header_state('idle')

    def _update_title(self, summary: str) -> None:
        self._header_label.text = f"Step {self._step_index}: {summary}"

    def _set_header_state(self, state: str) -> None:
        self._avatar_icon.set_visibility(state == 'idle')
        self._avatar_spinner.set_visibility(state == 'running')
        self._avatar_check.set_visibility(state == 'done')
