from __future__ import annotations
from typing import Dict, List, Optional, Any
from nicegui import ui
from agentic.core.events import AgentEvent

from .core import (
    Step, StepType, StepStatus, EventContext, 
    EventHandlerRegistry, RendererRegistry,
    EventHandler, StepRenderer
)

# Import default tools
from .tool_thinking import ThinkingEventHandler, ThinkingRenderer
from .tool_websearch import WebSearchEventHandler, WebSearchRenderer
from .tool_code_interpreter import CodeInterpreterEventHandler, CodeInterpreterRenderer
from .tool_generic import GenericToolEventHandler, GenericToolRenderer
from .lifecycle import LifecycleEventHandler, FinishedRenderer


class ProgressItem(ui.item):
    """Timeline-style list item: dot + vertical line + free-form content."""

    def __init__(self, *, final: bool = False):
        super().__init__()
        with self:
            with ui.row().classes('w-full items-start no-wrap gap-2 overflow-clip mb-2 p-0'):
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


class AgentStepper(ui.list):
    """
    Orchestrator component for agent execution visualization.
    Uses registry pattern for extensibility.
    """

    def __init__(self, tool_title_map: Optional[Dict[str, str]] = None, hidden_tool_details: List[str] = None) -> None:
        super().__init__()
        
        # Initialize Registries
        self.event_registry = EventHandlerRegistry()
        self.renderer_registry = RendererRegistry()
        
        # Initialize Context State
        self.steps: List[Step] = []
        self._main_agent_name: Optional[str] = None
        self.tool_title_map = tool_title_map or {}
        
        # Register Default Tools
        self._register_defaults(hidden_tool_details)
        
        # UI State
        self.step_ui_map: Dict[str, Any] = {} 
        self.props('dense').classes('w-full max-w-xl gap-0 p-0')
        
        with self:
            self.expansion = ui.expansion().props('dense').classes('w-full')
            
            with self.expansion.add_slot('header'):
                self._build_header()
            
            with self.expansion:
                self.body_container = ui.list().props('dense').classes('w-full')

    def _register_defaults(self, hidden_tool_details: List[str] = None):
        # Thinking
        self.event_registry.register(ThinkingEventHandler())
        self.renderer_registry.register(ThinkingRenderer(), priority=100)
        
        # Web Search
        self.event_registry.register(WebSearchEventHandler())
        self.renderer_registry.register(WebSearchRenderer(), priority=90)
        
        # Code Interpreter
        self.event_registry.register(CodeInterpreterEventHandler())
        self.renderer_registry.register(CodeInterpreterRenderer(), priority=90)
        
        # Lifecycle
        self.event_registry.register(LifecycleEventHandler())
        self.renderer_registry.register(FinishedRenderer(), priority=100)
        
        # Generic Tool (Fallback)
        self.event_registry.register(GenericToolEventHandler())
        self.renderer_registry.register(GenericToolRenderer(hidden_tool_details), priority=10)

    def _build_header(self) -> None:
        with ui.item_section().classes('w-full'):
            with ui.row().classes('items-center gap-2'):
                with ui.column().classes('w-6 shrink-0 items-center justify-center'):
                    self.status_icon = ui.icon('sym_o_token').classes('text-xl text-gray-400')
                self.status_label = ui.label('Agent Ready').classes('text-gray-700')

    async def handle_event(self, event: AgentEvent) -> None:
        # Filter logic:
        # 1. Always allow specific hosted tool events regardless of source (to support sub-agents)
        # Note: This logic is now distributed, but we still need a high-level check for main agent focus
        # if we want to strictly filter thoughts from sub-agents.
        
        if event.event_type == "agent_started_stream_event":
            if not self._main_agent_name:
                self._main_agent_name = event.source
                self.body_container.clear()
                self.step_ui_map.clear()
                self.steps.clear()
                self.expansion.open()
            
            # Update header for start
            if event.source == self._main_agent_name:
                self.status_label.text = "Agent Working..."
                self.status_icon.classes('text-gray-800', remove='text-gray-400')
                self.status_label.classes('shimmer')
        
        # Check main agent filter for non-global events
        # This mimics the original logic: "For other events, strictly filter by main agent"
        # We might want to move this into specific handlers later, but keeping it here for safety
        is_global_event = event.event_type in ["tool_web_search_event", "tool_code_interpreter_event"]
        if self._main_agent_name and event.source != self._main_agent_name and not is_global_event:
            return

        # Create Context
        context = EventContext(self.steps, self._main_agent_name, self.tool_title_map)
        
        # Delegate to Handlers
        handlers = self.event_registry.get_handlers(event)
        affected_steps = []
        for handler in handlers:
            new_steps = handler.handle(event, context)
            if new_steps:
                affected_steps.extend(new_steps)
        
        # Update Header based on activity
        self._update_header(event, affected_steps[-1] if affected_steps else None)
        
        # Render Updates
        for step in affected_steps:
            self._update_step_ui(step)

    def _update_header(self, event: AgentEvent, step: Optional[Step] = None):
        # Only update header for the main manager agent
        if self._main_agent_name and event.source != self._main_agent_name:
            return

        if event.event_type == "llm_started_stream_event":
            self.status_label.text = "Thinking..."
        elif event.event_type == "tool_started_stream_event":
            if step:
                self.status_label.text = step.title
            else:
                self.status_label.text = "Running Tool..."
        elif event.event_type == "agent_ended_stream_event":
            self.status_label.text = "Agent Finished"
            self.status_icon.classes('text-gray-400', remove='text-gray-800')
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
        renderer = self.renderer_registry.get_renderer(step)
        if renderer:
            renderer.render(step, container)
        else:
            # Fallback if no renderer found
            with container:
                ui.label(f"Unknown step: {step.title}").classes('text-red-500')
