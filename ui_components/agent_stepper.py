from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

from nicegui import ui
from events import AgentEvent


class StepType(str, Enum):
    THINKING = "thinking"
    TOOL = "tool"
    MESSAGE = "message"
    ERROR = "error"
    FINISHED = "finished"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Step:
    id: str
    type: StepType
    title: str
    status: StepStatus = StepStatus.PENDING
    data: Dict[str, Any] = field(default_factory=dict)
    
    def update(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class StepManager:
    def __init__(self, tool_title_map: Optional[Dict[str, str]] = None):
        self.steps: List[Step] = []
        self._step_counter = 0
        self._main_agent_name: Optional[str] = None
        self.tool_title_map = tool_title_map or {} 

    def _create_step(self, type: StepType, title: str, data: Dict[str, Any] = None) -> Step:
        self._step_counter += 1
        return Step(
            id=f"step_{self._step_counter}",
            type=type,
            title=title,
            status=StepStatus.RUNNING,
            data=data or {}
        )

    def handle_event(self, event: AgentEvent) -> Optional[Step]:
        if event.event_type == "agent_started_stream_event":
            if not self._main_agent_name:
                self._main_agent_name = event.source
            
            if event.source != self._main_agent_name:
                return None

        if self._main_agent_name and event.source != self._main_agent_name:
            return None

        if event.event_type == "llm_started_stream_event":
            self._complete_last_step()
            step = self._create_step(StepType.THINKING, "Thinking...", data=event.data)
            self.steps.append(step)
            return step

        elif event.event_type == "llm_ended_stream_event":
            if self.steps and self.steps[-1].type == StepType.THINKING:
                self.steps[-1].status = StepStatus.COMPLETED
                if event.data:
                    self.steps[-1].data.update(event.data)
                return self.steps[-1]

        elif event.event_type == "tool_started_stream_event":
            self._complete_last_step()
            tool_name = "Unknown Tool"
            if event.data and "tool" in event.data:
                tool = event.data["tool"]
                if hasattr(tool, "name"):
                    tool_name = tool.name
                elif isinstance(tool, dict):
                    tool_name = tool.get("name", "Unknown Tool")
            
            # Map tool names to friendlier titles
            title = self._get_tool_title(tool_name)
            
            step = self._create_step(StepType.TOOL, title, data=event.data)
            self.steps.append(step)
            return step

        elif event.event_type == "tool_ended_stream_event":
            if self.steps and self.steps[-1].type == StepType.TOOL:
                self.steps[-1].status = StepStatus.COMPLETED
                if event.data:
                    self.steps[-1].data.update(event.data)
                return self.steps[-1]

        elif event.event_type == "agent_ended_stream_event":
            self._complete_last_step()
            step = self._create_step(StepType.FINISHED, "Finished", data=event.data)
            step.status = StepStatus.COMPLETED
            self.steps.append(step)
            return step

        return None

    def _complete_last_step(self):
        if self.steps and self.steps[-1].status == StepStatus.RUNNING:
            self.steps[-1].status = StepStatus.COMPLETED

    def _get_tool_title(self, tool_name: str) -> str:
        # Check custom map first
        if tool_name in self.tool_title_map:
            return self.tool_title_map[tool_name]

        # Friendly mapping for known tools
        mapping = {
            "search_web": "Searching the web",
            "execute_step": "Executing step",
            "draft_plan": "Drafting plan",
            "read_file": "Reading file",
            "write_file": "Writing file",
            "list_dir": "Listing directory",
        }
        # Check exact match first
        if tool_name in mapping:
            return mapping[tool_name]
        
        # Check partial match for search
        if "search" in tool_name.lower():
            return "Searching the web"
            
        # Fallback
        return f"Executing {tool_name}"


class ProgressItem(ui.item):
    """Timeline-style list item: dot + vertical line + free-form content."""

    def __init__(self, *, final: bool = False):
        super().__init__()
        with self:
            with ui.row().classes('w-full items-start no-wrap gap-2 overflow-clip mb-2'):
                # LEFT RAIL / ICON COLUMN
                with ui.column().classes('w-6 shrink-0 items-center self-stretch gap-0'):
                    if final:
                        # Replace dot + line with icon for final item
                        ui.icon('sym_o_checklist_rtl').classes('text-xl text-gray-500 mt-[2px]')
                    else:
                        with ui.row().classes('h-5 items-center justify-center'):
                            ui.element('div').classes('h-[6px] w-[6px] rounded-full bg-gray-400')
                        ui.element('div').classes('w-[1px] rounded-full grow bg-gray-300')

                # RIGHT CONTENT (free-form)
                self.container = ui.column().classes('grow min-w-0 gap-2')


class StepRenderer(Protocol):
    def can_handle(self, step: Step) -> bool:
        ...

    def render(self, step: Step, container: ui.element) -> None:
        ...


class ThinkingRenderer:
    def can_handle(self, step: Step) -> bool:
        return step.type == StepType.THINKING

    def render(self, step: Step, container: ui.element) -> None:
        with container:
            label = ui.label(step.title).classes('text-gray-500')
            if step.status == StepStatus.RUNNING:
                label.classes('shimmer')


class ToolRenderer:
    def can_handle(self, step: Step) -> bool:
        return step.type == StepType.TOOL

    def render(self, step: Step, container: ui.element) -> None:
        with container:
            # Try to look like the static search card if possible
            if "Searching" in step.title:
                with ui.row().classes('items-center gap-2'):
                    ui.icon('sym_o_search').classes('text-lg text-gray-600')
                    ui.label(step.title).classes('font-medium')
            else:
                ui.label(step.title).classes('text-gray-500')
            
            if step.status == StepStatus.COMPLETED:
                result = step.data.get('result', 'No result')
                result_str = str(result)
                
                # Use CSS truncation for better UX
                ui.label(result_str).classes('text-sm text-gray-600 w-full truncate')
                
                # We could try to parse links here for the "card" look, but for now keep it simple
                # as per "best effort" mapping.

class FinishedRenderer:
    def can_handle(self, step: Step) -> bool:
        return step.type == StepType.FINISHED

    def render(self, step: Step, container: ui.element) -> None:
        with container:
            ui.label("Task Completed").classes('text-gray-500')
class AgentStepper(ui.list):
    """
    Orchestrator component for agent execution visualization.
    Matches the static prototype structure.
    """

    def __init__(self, tool_title_map: Optional[Dict[str, str]] = None) -> None:
        super().__init__()
        self.manager = StepManager(tool_title_map=tool_title_map)
        self.step_ui_map: Dict[str, Any] = {} 
        self._main_agent_name: Optional[str] = None
        
        self.props('dense').classes('w-full max-w-xl gap-0')
        
        with self:
            self.expansion = ui.expansion().props('dense default-opened').classes('w-full group')
            
            with self.expansion.add_slot('header'):
                self._build_header()
            
            with self.expansion:
                self.body_container = ui.list().props('dense').classes('w-full pl-0')

    def _build_header(self) -> None:
        with ui.item_section().classes('w-full'):
            with ui.row().classes('items-center gap-2'):
                with ui.column().classes('w-6 shrink-0 items-center justify-center'):
                    self.status_icon = ui.icon('sym_o_token').classes('text-xl text-gray-400')
                self.status_label = ui.label('Agent Ready').classes('text-gray-700')

    async def handle_event(self, event: AgentEvent) -> None:
        affected_step = self.manager.handle_event(event)
        
        self._update_header(event, affected_step)
        
        if event.event_type == "agent_started_stream_event":
            # Reset if it's a new main agent run
            if self._main_agent_name is None or event.source == self._main_agent_name:
                self._main_agent_name = event.source
                self.body_container.clear()
                self.step_ui_map.clear()
                self.expansion.open()

        if affected_step:
            self._update_step_ui(affected_step)

    def _update_header(self, event: AgentEvent, step: Optional[Step] = None):
        # Only update header for the main manager agent
        if self._main_agent_name and event.source != self._main_agent_name:
            return

        if event.event_type == "agent_started_stream_event":
            self.status_label.text = "Agent Working..."
            self.status_icon.classes('text-gray-800', remove='text-gray-400')
            # Start shimmer once
            self.status_label.classes('shimmer')
        elif event.event_type == "llm_started_stream_event":
            self.status_label.text = "Thinking..."
        elif event.event_type == "tool_started_stream_event":
            # Use the friendly title from the step if available
            if step:
                self.status_label.text = step.title
            else:
                self.status_label.text = "Running Tool..."
        elif event.event_type == "agent_ended_stream_event":
            self.status_label.text = "Agent Finished"
            self.status_icon.classes('text-gray-400', remove='text-gray-800')
            # Remove shimmer at the end
            self.status_label.classes(remove='shimmer')

    def _update_step_ui(self, step: Step) -> None:
        if step.id in self.step_ui_map:
            container, item = self.step_ui_map[step.id]
            container.clear()
            self._render_step_content(step, container)
        else:
            with self.body_container:
                # Check if it's a finished step to pass final=True
                is_final = step.type == StepType.FINISHED
                item = ProgressItem(final=is_final)
                self.step_ui_map[step.id] = (item.container, item)
                self._render_step_content(step, item.container)

    def _render_step_content(self, step: Step, container: ui.element) -> None:
        renderers = [ThinkingRenderer(), ToolRenderer(), FinishedRenderer()]
        for renderer in renderers:
            if renderer.can_handle(step):
                renderer.render(step, container)
                break
