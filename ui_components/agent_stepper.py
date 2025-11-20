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
    span_id: Optional[str] = None
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

    def _create_step(self, type: StepType, title: str, data: Dict[str, Any] = None, span_id: str = None) -> Step:
        self._step_counter += 1
        return Step(
            id=f"step_{self._step_counter}",
            type=type,
            title=title,
            status=StepStatus.RUNNING,
            span_id=span_id,
            data=data or {}
        )

    def handle_event(self, event: AgentEvent) -> List[Step]:
        affected_steps = []

        if event.event_type == "agent_started_stream_event":
            if not self._main_agent_name:
                self._main_agent_name = event.source
            
            if event.source != self._main_agent_name:
                return []

        # Filter logic:
        # 1. Always allow specific hosted tool events regardless of source (to support sub-agents)
        if event.event_type in ["tool_web_search_event", "tool_code_interpreter_event"]:
            pass # Allow these to proceed
        
        # 2. For other events, strictly filter by main agent to avoid cluttering the UI with sub-agent thoughts
        elif self._main_agent_name and event.source != self._main_agent_name:
            return []

        if event.event_type == "llm_started_stream_event":
            self._complete_last_step()
            step = self._create_step(StepType.THINKING, "Thinking...", data=event.data)
            self.steps.append(step)
            affected_steps.append(step)

        elif event.event_type == "llm_ended_stream_event":
            if self.steps and self.steps[-1].type == StepType.THINKING:
                self.steps[-1].status = StepStatus.COMPLETED
                if event.data:
                    self.steps[-1].data.update(event.data)
                affected_steps.append(self.steps[-1])
            
            # Note: We no longer parse tool calls here as we use specific events now.

        elif event.event_type == "tool_web_search_event":
            # Create a completed step for the web search
            step = self._create_step(
                StepType.TOOL, 
                "Searching the web", 
                data={
                    "tool_type": "web_search",
                    "query": event.data.get("query"),
                    "sources": event.data.get("sources")
                }
            )
            step.status = StepStatus.COMPLETED
            self.steps.append(step)
            affected_steps.append(step)

        elif event.event_type == "tool_code_interpreter_event":
             # Create a RUNNING step for code interpreter
             # We will update this step when tool_ended_stream_event arrives with the result
            step = self._create_step(
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
            self.steps.append(step)
            affected_steps.append(step)

        elif event.event_type == "tool_call_detected_event":
            # Create a PENDING step for the tool call
            tool_name = event.data.get("tool_name", "Unknown Tool")
            title = self._get_tool_title(tool_name)
            
            step = self._create_step(
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
            self.steps.append(step)
            affected_steps.append(step)

        elif event.event_type == "tool_started_stream_event":
            # If the last step is already a "Running code" step (created by tool_code_interpreter_event),
            # we don't want to create a duplicate generic tool step.
            if self.steps and self.steps[-1].data.get("tool_type") == "code_interpreter" and self.steps[-1].status == StepStatus.RUNNING:
                # Just update the title if needed, or ignore
                pass
            else:
                # Do NOT complete last step automatically to allow parallel tools
                # self._complete_last_step()
                
                tool_name = "Unknown Tool"
                if event.data and "tool" in event.data:
                    tool = event.data["tool"]
                    if hasattr(tool, "name"):
                        tool_name = tool.name
                    elif isinstance(tool, dict):
                        tool_name = tool.get("name", "Unknown Tool")
                
                # Map tool names to friendlier titles
                title = self._get_tool_title(tool_name)
                
                # Check for existing PENDING step for this tool
                # We match by tool_name and PENDING status. 
                # Since we process events in order, the first PENDING step for this tool should be the one.
                existing_step = next((s for s in self.steps if s.type == StepType.TOOL and s.status == StepStatus.PENDING and s.data.get("tool_name") == tool_name), None)
                
                if existing_step:
                    step = existing_step
                    step.status = StepStatus.RUNNING
                    step.span_id = event.span_id
                    # Merge data (keep arguments)
                    step.data.update(event.data)
                else:
                    step = self._create_step(StepType.TOOL, title, data=event.data, span_id=event.span_id)
                    self.steps.append(step)
                
                affected_steps.append(step)

        elif event.event_type == "tool_ended_stream_event":
            print(f"[\033[94mStepManager\033[0m] tool_ended_stream_event received")
            
            # Find step by span_id if available
            target_step = None
            if event.span_id:
                target_step = next((s for s in reversed(self.steps) if s.span_id == event.span_id and s.status == StepStatus.RUNNING), None)
            
            # Fallback to last running tool step if no span_id match
            if not target_step and self.steps and self.steps[-1].type == StepType.TOOL and self.steps[-1].status == StepStatus.RUNNING:
                target_step = self.steps[-1]

            if target_step:
                print(f"  Target step: {target_step.title} (id={target_step.id})")
                print(f"  Event data keys: {event.data.keys() if event.data else 'None'}")
                print(f"  Result: {str(event.data.get('result'))[:100] if event.data else 'None'}...")
                
                target_step.status = StepStatus.COMPLETED
                if event.data:
                    # Update data with result
                    target_step.data.update(event.data)
                    
                    # If this was a code interpreter step, ensure 'outputs' is populated from 'result' if needed
                    if target_step.data.get("tool_type") == "code_interpreter":
                        result = event.data.get("result")
                        print(f"  Code interpreter result: {result}")
                        # If we didn't have outputs before, use result
                        if result:
                            if not target_step.data.get("outputs"):
                                target_step.data["outputs"] = [result]
                            elif isinstance(target_step.data["outputs"], list) and result not in target_step.data["outputs"]:
                                target_step.data["outputs"].append(result)
                            
                            print(f"  Updated outputs: {target_step.data['outputs']}")
                            
                affected_steps.append(target_step)

        elif event.event_type == "agent_ended_stream_event":
            self._complete_last_step()
            step = self._create_step(StepType.FINISHED, "Finished", data=event.data)
            step.status = StepStatus.COMPLETED
            self.steps.append(step)
            affected_steps.append(step)

        return affected_steps

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


class ToolRenderer:
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
                        import json
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
                
class WebSearchRenderer:
    def can_handle(self, step: Step) -> bool:
        return step.type == StepType.TOOL and step.data.get("tool_type") == "web_search"

    def render(self, step: Step, container: ui.element) -> None:
        with container:
            # 1. Header Row
            with ui.row().classes('items-center gap-2'):
                ui.icon('sym_o_search').classes('text-lg text-gray-600')
                ui.label('Searching the web').classes('font-medium')

            # 2. Content Card
            with ui.card().props('flat bordered').classes('w-full bg-gray-50 p-3'):
                with ui.column().classes('w-full gap-2'):
                    # Optional description (could be dynamic if we had it)
                    # ui.label('Searching for information...').classes('text-sm text-gray-600')

                    # Query Box
                    with ui.row().classes('w-full items-center no-wrap gap-2 bg-white border border-gray-200 rounded-lg px-3 py-2'):
                        ui.icon('sym_o_search').classes('text-gray-500')
                        ui.label(step.data.get('query', 'Searching...')).classes('text-sm text-gray-700 grow min-w-0 truncate')

            # 3. Sources (if available)
            sources = step.data.get('sources')
            if sources:
                # "Reviewing sources" Header
                with ui.row().classes('items-center gap-2 mt-2'):
                    ui.icon('library_books').classes('text-xs text-gray-500')
                    ui.label(f"Reviewing sources").classes('text-xs text-gray-500 font-medium')
                    with ui.element('div').classes('bg-gray-200 px-1.5 rounded text-[10px] text-gray-600'):
                        ui.label(str(len(sources)))

                # Sources List (Vertical List)
                with ui.list().props('dense separator').classes('w-full border border-gray-200 rounded-md mt-1 bg-white'):
                    for source in sources:
                        # Robust Extraction Logic
                        url = None
                        title = None
                        
                        # 1. Try attribute access (Pydantic model)
                        if hasattr(source, 'url'):
                            url = source.url
                        if hasattr(source, 'title'):
                            title = source.title
                            
                        # 2. Try dict access
                        if url is None and isinstance(source, dict):
                            url = source.get('url')
                        if title is None and isinstance(source, dict):
                            title = source.get('title')
                            
                        # 3. Fallback
                        if url is None: 
                            url = str(source)
                        if title is None: 
                            title = url

                        # Domain extraction
                        domain = ""
                        try:
                            from urllib.parse import urlparse
                            if url and url.startswith('http'):
                                domain = urlparse(url).netloc.replace('www.', '')
                        except:
                            pass

                        # List Item as Link
                        # Use tag="a" in props for real hyperlink behavior
                        with ui.item().props(f'tag="a" href="{url}" target="_blank" clickable dense').classes('hover:bg-gray-50 transition-colors text-decoration-none pl-2 pr-2'):
                            # Single section with row for tight control over icon/text spacing
                            with ui.item_section():
                                with ui.row().classes('items-center w-full gap-2 no-wrap'):
                                    # Icon
                                    ui.icon('public').classes('text-gray-400 text-xs shrink-0')
                                    
                                    # Title
                                    ui.label(title).classes('text-xs text-gray-700 truncate font-medium grow')
                                    
                                    # Domain
                                    if domain:
                                        ui.label(domain).classes('text-[10px] text-gray-400 shrink-0')

class CodeInterpreterRenderer:
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

    def __init__(self, tool_title_map: Optional[Dict[str, str]] = None, hidden_tool_details: List[str] = None) -> None:
        super().__init__()
        self.manager = StepManager(tool_title_map=tool_title_map)
        self.step_ui_map: Dict[str, Any] = {} 
        self._main_agent_name: Optional[str] = None
        
        self.renderers = [
            ThinkingRenderer(),
            WebSearchRenderer(),
            CodeInterpreterRenderer(),
            ToolRenderer(hidden_tool_details=hidden_tool_details), # Generic fallback
            FinishedRenderer()
        ]

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
        affected_steps = self.manager.handle_event(event)
        
        # Update header based on the event and the last affected step (if any)
        last_step = affected_steps[-1] if affected_steps else None
        self._update_header(event, last_step)
        
        if event.event_type == "agent_started_stream_event":
            # Reset if it's a new main agent run
            if self._main_agent_name is None or event.source == self._main_agent_name:
                self._main_agent_name = event.source
                self.body_container.clear()
                self.step_ui_map.clear()
                self.expansion.open()

        for step in affected_steps:
            self._update_step_ui(step)

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
        for renderer in self.renderers:
            if renderer.can_handle(step):
                renderer.render(step, container)
                break
