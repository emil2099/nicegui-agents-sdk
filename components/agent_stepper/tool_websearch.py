from __future__ import annotations
from typing import List, TYPE_CHECKING
from nicegui import ui
from .core import EventHandler, StepRenderer, EventContext, Step, StepType, StepStatus

if TYPE_CHECKING:
    from agentic.core.events import AgentEvent

# ==============================================================================
# Event Handler
# ==============================================================================

class WebSearchEventHandler(EventHandler):
    def can_handle(self, event: AgentEvent) -> bool:
        return event.event_type == "tool_web_search_event"

    def handle(self, event: AgentEvent, context: EventContext) -> List[Step]:
        # Create a completed step for the web search
        step = context.create_step(
            StepType.TOOL, 
            "Searching the web", 
            data={
                "tool_type": "web_search",
                "query": event.data.get("query"),
                "sources": event.data.get("sources")
            }
        )
        step.status = StepStatus.COMPLETED
        context.steps.append(step)
        return [step]


# ==============================================================================
# Renderer
# ==============================================================================

class WebSearchRenderer(StepRenderer):
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
                        with ui.item().props(f'tag="a" href="{url}" target="_blank" clickable dense').classes('hover:bg-gray-50 transition-colors text-decoration-none pl-2 pr-2'):
                            with ui.item_section():
                                with ui.row().classes('items-center w-full gap-2 no-wrap'):
                                    ui.icon('public').classes('text-gray-400 text-xs shrink-0')
                                    ui.label(title).classes('text-xs text-gray-700 truncate font-medium grow')
                                    if domain:
                                        ui.label(domain).classes('text-[10px] text-gray-400 shrink-0')
