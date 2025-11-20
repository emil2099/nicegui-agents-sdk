from __future__ import annotations
from typing import List, TYPE_CHECKING
from nicegui import ui
from .core import EventHandler, StepRenderer, EventContext, Step, StepType, StepStatus

if TYPE_CHECKING:
    from agentic.core.events import AgentEvent

# ==============================================================================
# Event Handler
# ==============================================================================

class LifecycleEventHandler(EventHandler):
    def can_handle(self, event: AgentEvent) -> bool:
        return event.event_type == "agent_ended_stream_event"

    def handle(self, event: AgentEvent, context: EventContext) -> List[Step]:
        # Complete last step if running
        last_step = context.get_last_step()
        if last_step and last_step.status == StepStatus.RUNNING:
            last_step.status = StepStatus.COMPLETED
            
        step = context.create_step(StepType.FINISHED, "Finished", data=event.data)
        step.status = StepStatus.COMPLETED
        context.steps.append(step)
        return [step]


# ==============================================================================
# Renderer
# ==============================================================================

class FinishedRenderer(StepRenderer):
    def can_handle(self, step: Step) -> bool:
        return step.type == StepType.FINISHED

    def render(self, step: Step, container: ui.element) -> None:
        with container:
            ui.label("Task Completed").classes('text-gray-500')
