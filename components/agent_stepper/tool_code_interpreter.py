from __future__ import annotations
from typing import List, TYPE_CHECKING
from nicegui import ui
from .core import EventHandler, StepRenderer, EventContext, Step, StepType, StepStatus

if TYPE_CHECKING:
    from agentic.core.events import AgentEvent

# ==============================================================================
# Event Handler
# ==============================================================================

class CodeInterpreterEventHandler(EventHandler):
    def can_handle(self, event: AgentEvent) -> bool:
        return event.event_type == "tool_code_interpreter_event"

    def handle(self, event: AgentEvent, context: EventContext) -> List[Step]:
        # Create a RUNNING step for code interpreter
        # We will update this step when tool_ended_stream_event arrives with the result
        step = context.create_step(
            StepType.TOOL, 
            "Running code", 
            data={
                "tool_type": "code_interpreter",
                "code": event.data.get("code"),
                # outputs might be empty here if it's just the call
                "outputs": event.data.get("outputs") 
            }
        )
        step.status = StepStatus.RUNNING
        context.steps.append(step)
        return [step]


# ==============================================================================
# Renderer
# ==============================================================================

class CodeInterpreterRenderer(StepRenderer):
    def can_handle(self, step: Step) -> bool:
        return step.type == StepType.TOOL and step.data.get("tool_type") == "code_interpreter"

    def render(self, step: Step, container: ui.element) -> None:
        with container:
            # Header
            with ui.row().classes('items-center gap-2 mb-1'):
                ui.icon('code').classes('text-lg text-gray-600')
                ui.label(step.title).classes('text-gray-700 font-medium')
                
            # Card Container
            with ui.column().classes('w-full border border-gray-200 rounded-lg overflow-hidden gap-0'):
                
                # Code Section (Arguments)
                code = step.data.get('code', '')
                if code:
                    with ui.column().classes('w-full p-2 bg-gray-50/50'):
                        ui.label("Code").classes('text-xs text-gray-500 font-medium')
                        ui.markdown(f"```python\n{code}\n```").classes('w-full text-xs text-gray-700 font-mono [&_pre]:whitespace-pre-wrap [&_pre]:bg-transparent [&_pre]:p-0')
                
                # Separator
                if code:
                    ui.separator().classes('border-gray-200')

                # Output Section
                with ui.column().classes('w-full p-2 bg-white'):
                    ui.label("Output").classes('text-xs text-gray-500 font-medium')
                    
                    outputs = step.data.get('outputs')
                    if outputs:
                        for output in outputs:
                            # Handle different output types
                            content = ""
                            if isinstance(output, str):
                                content = output
                            elif hasattr(output, 'logs') and output.logs:
                                content = output.logs
                            elif hasattr(output, 'image') and output.image:
                                ui.label("[Image Output]").classes('text-gray-500 italic text-xs')
                                continue
                            else:
                                content = str(output)
                                
                            if content:
                                ui.markdown(f"```\n{content}\n```").classes('w-full text-xs text-gray-700 font-mono max-h-60 overflow-y-auto [&_pre]:whitespace-pre-wrap [&_pre]:bg-transparent [&_pre]:p-0')
                    else:
                        if step.status == StepStatus.RUNNING:
                             ui.label("...").classes('text-sm text-gray-400 italic')
                        else:
                             ui.label("No output").classes('text-sm text-gray-500')
