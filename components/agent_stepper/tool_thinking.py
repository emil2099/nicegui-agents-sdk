from __future__ import annotations
from typing import List, TYPE_CHECKING
from nicegui import ui
from .core import EventHandler, StepRenderer, EventContext, Step, StepType, StepStatus

if TYPE_CHECKING:
    from agentic.core.events import AgentEvent

# ==============================================================================
# Event Handler
# ==============================================================================

class ThinkingEventHandler(EventHandler):
    def can_handle(self, event: AgentEvent) -> bool:
        return event.event_type in ["llm_started_stream_event", "llm_ended_stream_event"]

    def handle(self, event: AgentEvent, context: EventContext) -> List[Step]:
        affected_steps = []
        
        if event.event_type == "llm_started_stream_event":
            # Complete previous step if running
            last_step = context.get_last_step()
            if last_step and last_step.status == StepStatus.RUNNING:
                last_step.status = StepStatus.COMPLETED
            
            step = context.create_step(StepType.THINKING, "Thinking...", data=event.data)
            context.steps.append(step)
            affected_steps.append(step)

        elif event.event_type == "llm_ended_stream_event":
            last_step = context.get_last_step()
            if last_step and last_step.type == StepType.THINKING:
                last_step.status = StepStatus.COMPLETED
                if event.data:
                    last_step.data.update(event.data)
                affected_steps.append(last_step)
                
        return affected_steps


# ==============================================================================
# Renderer
# ==============================================================================

class ThinkingRenderer(StepRenderer):
    def can_handle(self, step: Step) -> bool:
        return step.type == StepType.THINKING

    def render(self, step: Step, container: ui.element) -> None:
        with container:
            ui.label(step.title).classes('text-gray-500')
