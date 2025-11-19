"""Barebones NiceGUI page that triggers an OpenAI Agent run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nicegui import app, ui

from agent_service import run_plan_execute
from events import AgentEvent, EventPublisher
from ui_components.agent_stepper import AgentStepper
from ui_components.agent_stepper_static import AgentStepperStatic
from ui_components.step_tracker import StepTracker

BASE_DIR = Path(__file__).parent
STYLE_PATH = BASE_DIR / 'style.css'

app.add_static_file(local_file=STYLE_PATH, url_path='/style.css')
ui.add_head_html('<link rel="stylesheet" href="/style.css">', shared=True)

ui.query('.nicegui-content').classes('p-0 gap-0')

event_log = None
step_tracker: StepTracker | None = None


def _stringify(value: Any) -> str:
    if hasattr(value, "name"):
        return f"{value.__class__.__name__}(name={getattr(value, 'name', 'unknown')})"
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json()
    return repr(value)


def _format_event_line(event: AgentEvent) -> str:
    if event.data:
        details = ", ".join(f"{key}={_stringify(value)}" for key, value in event.data.items())
    else:
        details = "no payload"
    timestamp = event.timestamp.astimezone().strftime("%H:%M:%S")
    rest = f"{event.event_type} | {details}"
    return f"{timestamp} [{event.source}] {rest}"


async def ui_event_logger(event: AgentEvent) -> None:
    if event_log is None:
        return
    event_log.push(_format_event_line(event))


ui.colors(primary="#000000")
ui.button.default_props('unelevated')
ui.card.default_props('flat bordered')

with ui.column().classes(
    'w-full items-center justify-center px-4 pt-16 box-border gap-4'
):
    # 1. Gradient Card
    with ui.column().classes('w-full max-w-xl gradient-card rounded-borders p-4'):
        with ui.row().classes('items-center gap-1 text-sm font-medium text-gray-800'):
            ui.icon('o_auto_awesome').classes('text-base text-indigo-500')
            ui.label('GPT-5 mini agent')
        ui.label(
            'Lightweight agent that plans, executes, and reports each reasoning step while streaming progress back to you.'
        ).classes('text-xs text-gray-600 leading-snug')

    # 2. Input Area
    with ui.card().tight().classes('w-full max-w-xl'):
        with ui.card_section().classes('w-full'):
            with ui.column().classes('gap-4'):

                prompt_input = ui.textarea(
                    placeholder="Ask me anything"
                ).props("autogrow outlined dense").classes('w-full ')

                async def on_submit() -> None:
                    ask_button.disable()
                    output_area.set_content("Thinking…")
                    text = prompt_input.value.strip()
                    if not text:
                        output_area.set_content("Please enter a prompt.")
                        ask_button.enable()
                        return
                    
                    # Reset UI
                    if event_log is not None:
                        event_log.clear()
                        event_log.push("listening for events…")
                    if step_tracker is not None:
                        step_tracker.reset()
                    
                    # Setup subscribers
                    subscribers = [ui_event_logger]
                    if step_tracker is not None:
                        subscribers.append(step_tracker.handle_event)
                    subscribers.append(agent_stepper.handle_event)

                    event_publisher = EventPublisher(subscribers=subscribers)

                    # Run Agent
                    stream = run_plan_execute(text, event_publisher=event_publisher)

                    chunks: list[str] = []
                    captured_error: Exception | None = None
                    try:
                        async for chunk in stream:
                            if chunk:
                                chunks.append(chunk)
                                output_area.set_content("".join(chunks))
                    except Exception as e:
                        captured_error = e
                        output_area.set_content(f"Error: {e}")
                        if event_log is not None:
                            event_log.push(f"error: {e}")
                    finally:
                        ask_button.enable()

                    if captured_error is not None:
                        raise captured_error

                    if not chunks:
                        output_area.set_content("(no response)")

        ui.separator()
        with ui.card_actions().classes('w-full items-center justify-between gap-4 p-4'):
            ask_button = ui.button("Ask", on_click=on_submit).props('padding="xs md"').classes('ml-auto')

    # Response Area (kept near input)
    with ui.card().tight().classes('w-full max-w-xl'):
        with ui.card_section().classes('w-full'):
            ui.label("Response").classes('font-medium')
            output_area = ui.markdown("Waiting for a question…").classes('w-full min-h-[5rem]')

    # 3. Interactive Stepper
    tool_map = {
        "execute_step": "Executing research step",
        "draft_plan": "Drafting a plan",
        "random_number": "Generating random number",
        "web_search": "Searching the web",
        "code_interpreter": "Running code"
    }
    agent_stepper = AgentStepper(tool_title_map=tool_map)

    # 4. Old Stepper
    step_tracker = StepTracker()

    # 5. Static Prototype
    ui.label("Static Prototype (Comparison)").classes('text-xs font-bold text-gray-400 mt-4')
    AgentStepperStatic()

    # 6. Full Log
    with ui.card().tight().classes('w-full max-w-xl'):
        with ui.card_section().classes('w-full'):
            ui.label("Event Log").classes('font-medium')
            event_log = ui.log(max_lines=200).classes('w-full min-h-[12rem] text-xs')
            event_log.push("No events yet. Submit a prompt to see activity.")

ui.run(title="Mini agent demo")
