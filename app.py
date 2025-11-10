"""Barebones NiceGUI page that triggers an OpenAI Agent run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nicegui import app, ui

from agent_service import run_plan_execute
from events import AgentEvent, EventPublisher
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
    with ui.card().tight().classes('w-full max-w-xl'):
        with ui.card_section().classes('w-full'):
            with ui.column().classes('gap-4'):
                ui.label("GPT-5 mini agent").classes('font-medium')

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

                    if event_log is not None:
                        event_log.clear()
                        event_log.push("listening for events…")

                    if step_tracker is not None:
                        step_tracker.reset()

                    subscribers = [ui_event_logger]
                    if step_tracker is not None:
                        subscribers.append(step_tracker.handle_event)

                    event_publisher = EventPublisher(subscribers=subscribers)

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

    step_tracker = StepTracker()

    class ProgressItem(ui.item):
        """Timeline-style list item: dot + vertical line + free-form content."""
        def __init__(self):
            super().__init__()
            with self:
                with ui.row().classes('w-full items-start no-wrap gap-2 overflow-clip mb-2'):
                    # LEFT RAIL
                    with ui.column().classes('w-4 shrink-0 items-center self-stretch gap-0'):
                        with ui.row().classes('h-5 items-center justify-center'):
                            ui.element('div').classes('h-[6px] w-[6px] rounded-full bg-gray-400')
                        # vertical line
                        ui.element('div').classes('w-[1px] rounded-full grow bg-gray-300')

                    # RIGHT CONTENT (you can fill this freely)
                    self.container = ui.column().classes('grow min-w-0')

    with ui.list().props('dense').classes('w-full max-w-xl'):
        dummy_tracker = ui.expansion(text='Hello').props('dense').classes('w-full')

        with dummy_tracker.add_slot('header'):
            with ui.item_section().classes('w-full'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('sym_o_token').classes('text-xl')
                    ui.label('Hello! I am thinking!').classes('shimmer')

        with dummy_tracker:
            with ui.list().props('dense').classes('w-full'):
                with ProgressItem() as item:
                    with item.container:
                        ui.label('Debugging invisible text')
                        ui.label(
                            'Add a solid base layer under the gradient so the text remains visible '
                            'even when most of the gradient is transparent.'
                        )

                with ProgressItem() as item:
                    with item.container:
                        ui.label('Follow-up observation')
                        ui.label(
                            'Confirmed the base background layer prevents the text from vanishing '
                            'across themes and backgrounds.'
                        )

    with ui.card().tight().classes('w-full max-w-xl'):
        with ui.card_section().classes('w-full'):
            ui.label("Response").classes('font-medium')
            output_area = ui.markdown("Waiting for a question…").classes('w-full min-h-[10rem]')

with ui.element().classes('w-full px-4 pb-16 box-border'):
    with ui.card().tight().classes('w-full'):
        with ui.card_section().classes('w-full'):
            ui.label("Event Log").classes('font-medium')
            event_log = ui.log(max_lines=200).classes('w-full min-h-[12rem] text-xs')
            event_log.push("No events yet. Submit a prompt to see activity.")

ui.run(title="Mini agent demo")
