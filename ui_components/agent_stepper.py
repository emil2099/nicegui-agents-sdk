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

        elif event.event_type == "tool_started_stream_event":
            # If the last step is already a "Running code" step (created by tool_code_interpreter_event),
            # we don't want to create a duplicate generic tool step.
            if self.steps and self.steps[-1].data.get("tool_type") == "code_interpreter" and self.steps[-1].status == StepStatus.RUNNING:
                # Just update the title if needed, or ignore
                pass
            else:
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
                affected_steps.append(step)

        elif event.event_type == "tool_ended_stream_event":
            print(f"[\033[94mStepManager\033[0m] tool_ended_stream_event received")
            if self.steps and self.steps[-1].type == StepType.TOOL:
                print(f"  Last step type: {self.steps[-1].data.get('tool_type')}")
                print(f"  Event data keys: {event.data.keys() if event.data else 'None'}")
                print(f"  Result: {str(event.data.get('result'))[:100] if event.data else 'None'}...")
                
                self.steps[-1].status = StepStatus.COMPLETED
                if event.data:
                    # Update data with result
                    self.steps[-1].data.update(event.data)
                    
                    # If this was a code interpreter step, ensure 'outputs' is populated from 'result' if needed
                    if self.steps[-1].data.get("tool_type") == "code_interpreter":
                        result = event.data.get("result")
                        print(f"  Code interpreter result: {result}")
                        # If we didn't have outputs before, use result
                        if not self.steps[-1].data.get("outputs") and result:
                            self.steps[-1].data["outputs"] = [result] # Wrap in list to match renderer expectation
                            print(f"  Updated outputs: {self.steps[-1].data['outputs']}")
                            
                affected_steps.append(self.steps[-1])

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
            # 1. Header Row
            with ui.row().classes('items-center gap-2'):
                ui.icon('terminal').classes('text-lg text-gray-600')
                ui.label('Running Code').classes('font-medium')
            
            # 2. Content Card
            with ui.card().props('flat bordered').classes('w-full bg-gray-50 p-0 overflow-hidden'):
                with ui.column().classes('w-full gap-0'):
                    # Code Block
                    code = step.data.get('code', '')
                    if code:
                        # Use ui.code for syntax highlighting
                        # Remove default padding/margin to fit card
                        ui.code(code, language='python').classes('w-full text-xs bg-transparent p-3')
                    
                    # Outputs (only if completed and has output)
                    outputs = step.data.get('outputs')
                    if outputs:
                        ui.separator().classes('bg-gray-200')
                        with ui.column().classes('w-full p-3 bg-white'):
                            ui.label("Output:").classes('text-[10px] font-bold text-gray-400 mb-1 uppercase tracking-wider')
                            
                            for output in outputs:
                                # Handle different output types
                                # 1. String output (most common)
                                if isinstance(output, str):
                                    ui.markdown(f"```\n{output}\n```").classes('w-full text-xs text-gray-700 font-mono max-h-40 overflow-y-auto')
                                
                                # 2. Object with logs/image (if structured)
                                elif hasattr(output, 'logs') and output.logs:
                                    ui.markdown(f"```\n{output.logs}\n```").classes('w-full text-xs text-gray-700 font-mono max-h-40 overflow-y-auto')
                                elif hasattr(output, 'image') and output.image:
                                    ui.label("[Image Output]").classes('text-gray-500 italic text-xs')
                                    # If we had base64 image handling, we'd render it here
                                
                                # 3. Fallback
                                else:
                                    ui.label(str(output)).classes('text-xs text-gray-600 font-mono truncate')



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
        renderers = [ThinkingRenderer(), WebSearchRenderer(), CodeInterpreterRenderer(), ToolRenderer(), FinishedRenderer()]
        for renderer in renderers:
            if renderer.can_handle(step):
                renderer.render(step, container)
                break
