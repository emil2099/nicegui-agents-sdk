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
            # Generic Tool Header Style
            with ui.column().classes('w-full gap-1'):
                # Title
                ui.label('Running Code').classes('text-gray-700 font-medium')
                
                # Code Block (Arguments style)
                code = step.data.get('code', '')
                if code:
                    with ui.element('div').classes('w-full mt-1 pl-2 border-l-2 border-gray-200'):
                        ui.label("Code").classes('text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1')
                        ui.code(code, language='python').classes('w-full text-xs !bg-transparent !p-0 text-gray-600')
                
                # Outputs (Output style)
                outputs = step.data.get('outputs')
                if outputs:
                    with ui.element('div').classes('w-full mt-1 pl-2 border-l-2 border-gray-200'):
                        ui.label("Output").classes('text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1')
                        
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
                                ui.markdown(f"```\n{content}\n```").classes('w-full text-xs text-gray-700 font-mono max-h-60 overflow-y-auto [&_pre]:whitespace-pre-wrap [&_pre]:break-all')
