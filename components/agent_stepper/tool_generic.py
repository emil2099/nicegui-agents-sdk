from __future__ import annotations
from typing import List, TYPE_CHECKING
import json
from nicegui import ui
from .core import EventHandler, StepRenderer, EventContext, Step, StepType, StepStatus

if TYPE_CHECKING:
    from agentic.core.events import AgentEvent

# ==============================================================================
# Event Handler
# ==============================================================================

class GenericToolEventHandler(EventHandler):
    def can_handle(self, event: AgentEvent) -> bool:
        return event.event_type in ["tool_call_detected_event", "tool_started_stream_event", "tool_ended_stream_event"]

    def handle(self, event: AgentEvent, context: EventContext) -> List[Step]:
        affected_steps = []

        if event.event_type == "tool_call_detected_event":
            # Create a PENDING step for the tool call
            tool_name = event.data.get("tool_name", "Unknown Tool")
            title = context.get_tool_title(tool_name)
            
            step = context.create_step(
                StepType.TOOL, 
                title, 
                data={
                    "tool_type": "generic",
                    "tool_name": tool_name,
                    "arguments": event.data.get("arguments"),
                    "call_id": event.data.get("tool_call_id")
                }
            )
            step.status = StepStatus.PENDING
            context.steps.append(step)
            affected_steps.append(step)

        elif event.event_type == "tool_started_stream_event":
            # If the last step is already a "Running code" step (created by tool_code_interpreter_event),
            # we don't want to create a duplicate generic tool step.
            last_step = context.get_last_step()
            if last_step and last_step.data.get("tool_type") == "code_interpreter" and last_step.status == StepStatus.RUNNING:
                # Just update the title if needed, or ignore
                pass
            else:
                tool_name = "Unknown Tool"
                if event.data and "tool" in event.data:
                    tool = event.data["tool"]
                    if hasattr(tool, "name"):
                        tool_name = tool.name
                    elif isinstance(tool, dict):
                        tool_name = tool.get("name", "Unknown Tool")
                
                title = context.get_tool_title(tool_name)
                
                # Check for existing PENDING step for this tool
                existing_step = context.find_pending_tool_step(tool_name)
                
                if existing_step:
                    step = existing_step
                    step.status = StepStatus.RUNNING
                    step.span_id = event.span_id
                    # Merge data (keep arguments)
                    step.data.update(event.data)
                else:
                    step = context.create_step(StepType.TOOL, title, data=event.data, span_id=event.span_id)
                    context.steps.append(step)
                
                affected_steps.append(step)

        elif event.event_type == "tool_ended_stream_event":
            # Find step by span_id if available
            target_step = context.find_step_by_span_id(event.span_id)
            
            # Fallback to last running tool step if no span_id match
            if not target_step:
                last_step = context.get_last_step()
                if last_step and last_step.type == StepType.TOOL and last_step.status == StepStatus.RUNNING:
                    target_step = last_step

            if target_step:
                target_step.status = StepStatus.COMPLETED
                if event.data:
                    # Update data with result
                    target_step.data.update(event.data)
                    
                    # If this was a code interpreter step, ensure 'outputs' is populated from 'result' if needed
                    if target_step.data.get("tool_type") == "code_interpreter":
                        result = event.data.get("result")
                        # If we didn't have outputs before, use result
                        if result:
                            if not target_step.data.get("outputs"):
                                target_step.data["outputs"] = [result]
                            elif isinstance(target_step.data["outputs"], list) and result not in target_step.data["outputs"]:
                                target_step.data["outputs"].append(result)
                            
                affected_steps.append(target_step)

        return affected_steps


# ==============================================================================
# Renderer
# ==============================================================================

class GenericToolRenderer(StepRenderer):
    def __init__(self, hidden_tool_details: List[str] = None):
        self.hidden_tool_details = hidden_tool_details or []

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
                # Generic Tool Header
                with ui.column().classes('w-full gap-1'):
                    # Title
                    ui.label(step.title).classes('text-gray-700 font-medium')
                    
                    # Check if details should be hidden
                    tool_name = step.data.get('tool_name', 'tool')
                    if tool_name in self.hidden_tool_details:
                        return

                    # Arguments (Minimalist Function Call style)
                    arguments = step.data.get('arguments')
                    if arguments:
                        tool_name = step.data.get('tool_name', 'tool')
                        
                        # Format arguments
                        try:
                            if isinstance(arguments, str):
                                parsed = json.loads(arguments)
                                # If it's a dict, format it nicely inside the function call
                                args_str = json.dumps(parsed, indent=2)
                                # Indent the args to look like a function body
                                args_str = args_str.replace('\n', '\n  ')
                                display_code = f"{tool_name}(\n  {args_str}\n)"
                            else:
                                display_code = f"{tool_name}({str(arguments)})"
                        except:
                            display_code = f"{tool_name}({str(arguments)})"
                            
                        # Clean, light code block (Matching Output style)
                        with ui.element('div').classes('w-full mt-1 pl-2 border-l-2 border-gray-200'):
                            ui.label("Function call").classes('text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1')
                            # Use markdown for consistency and wrapping
                            ui.markdown(f"```python\n{display_code}\n```").classes('w-full text-xs text-gray-600 font-mono [&_pre]:whitespace-pre-wrap [&_pre]:break-all')

            if step.status == StepStatus.COMPLETED:
                result = step.data.get('result', 'No result')
                
                # Output (Minimalist)
                with ui.element('div').classes('w-full mt-1 pl-2 border-l-2 border-gray-200'):
                    ui.label("Output").classes('text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1')
                    
                    result_str = str(result)
                    # Use markdown code block for result, but cleaner
                    # Added [&_pre]:whitespace-pre-wrap to force wrapping in the generated pre tag
                    ui.markdown(f"```\n{result_str}\n```").classes('w-full text-xs text-gray-700 font-mono max-h-60 overflow-y-auto [&_pre]:whitespace-pre-wrap [&_pre]:break-all')
