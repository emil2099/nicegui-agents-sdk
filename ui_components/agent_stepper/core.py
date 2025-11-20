from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from nicegui import ui
    from events import AgentEvent

# ==============================================================================
# Models
# ==============================================================================

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


# ==============================================================================
# Context & Helpers
# ==============================================================================

class EventContext:
    """
    Helper context passed to event handlers.
    Encapsulates state management and common operations.
    """
    def __init__(self, steps: List[Step], main_agent_name: Optional[str], tool_title_map: Dict[str, str]):
        self.steps = steps
        self.main_agent_name = main_agent_name
        self.tool_title_map = tool_title_map
        self._step_counter = len(steps)

    def create_step(self, type: StepType, title: str, data: Dict[str, Any] = None, span_id: str = None) -> Step:
        self._step_counter += 1
        return Step(
            id=f"step_{self._step_counter}",
            type=type,
            title=title,
            status=StepStatus.RUNNING,
            span_id=span_id,
            data=data or {}
        )

    def get_last_step(self) -> Optional[Step]:
        return self.steps[-1] if self.steps else None

    def find_step_by_span_id(self, span_id: str) -> Optional[Step]:
        # Search in reverse to find the most recent one
        return next((s for s in reversed(self.steps) if s.span_id == span_id and s.status == StepStatus.RUNNING), None)

    def find_pending_tool_step(self, tool_name: str) -> Optional[Step]:
        return next((s for s in self.steps if s.type == StepType.TOOL and s.status == StepStatus.PENDING and s.data.get("tool_name") == tool_name), None)

    def get_tool_title(self, tool_name: str) -> str:
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


# ==============================================================================
# Protocols
# ==============================================================================

class EventHandler(Protocol):
    def can_handle(self, event: AgentEvent) -> bool:
        ...

    def handle(self, event: AgentEvent, context: EventContext) -> List[Step]:
        ...


class StepRenderer(Protocol):
    def can_handle(self, step: Step) -> bool:
        ...

    def render(self, step: Step, container: ui.element) -> None:
        ...


# ==============================================================================
# Registries
# ==============================================================================

class EventHandlerRegistry:
    def __init__(self):
        self._handlers: List[EventHandler] = []

    def register(self, handler: EventHandler):
        self._handlers.append(handler)

    def get_handlers(self, event: AgentEvent) -> List[EventHandler]:
        return [h for h in self._handlers if h.can_handle(event)]


class RendererRegistry:
    def __init__(self):
        self._renderers: List[StepRenderer] = []

    def register(self, renderer: StepRenderer, priority: int = 0):
        # Store as tuple (priority, renderer) to sort
        # Higher priority first
        self._renderers.append((priority, renderer))
        self._renderers.sort(key=lambda x: x[0], reverse=True)

    def get_renderer(self, step: Step) -> Optional[StepRenderer]:
        for _, renderer in self._renderers:
            if renderer.can_handle(step):
                return renderer
        return None
