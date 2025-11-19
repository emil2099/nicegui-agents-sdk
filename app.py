"""Barebones NiceGUI page that triggers an OpenAI Agent run."""

from __future__ import annotations

from pathlib import Path

from nicegui import app, ui

from events import EventPublisher
from ui_components.agent_stepper import AgentStepper
from ui_components.agent_stepper_static import AgentStepperStatic
from ui_components.step_tracker import StepTracker
from event_handlers import log_event_to_ui, run_agent_cycle

BASE_DIR = Path(__file__).parent
STYLE_PATH = BASE_DIR / 'style.css'

app.add_static_file(local_file=STYLE_PATH, url_path='/style.css')
ui.add_head_html('<link rel="stylesheet" href="/style.css">', shared=True)

ui.query('.nicegui-content').classes('p-0 gap-0')

event_log = None
step_tracker: StepTracker | None = None


ui.colors(primary="#000000")
ui.button.default_props('unelevated')
ui.card.default_props('flat bordered')

with ui.column().classes(
    'w-full items-center justify-center px-4 pt-16 box-border gap-4'
):
    # 1. Combined Header & Input Card
    with ui.card().tight().classes('gradient-card w-full max-w-xl p-4 gap-4'):
        # Header
        with ui.column().classes('gap-1'):
            with ui.row().classes('items-center gap-2 text-sm font-medium text-gray-800'):
                ui.icon('o_auto_awesome').classes('text-base text-indigo-500')
                ui.label('GPT-5 mini agent')
            ui.label(
                'Lightweight agent that plans, executes, and reports each reasoning step while streaming progress back to you.'
            ).classes('text-xs text-gray-600 leading-snug mt-2')

        # Input Area
        prompt_input = ui.textarea(
            placeholder="Ask me anything"
        ).props("autogrow outlined dense rows=1").classes('w-full')
        
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
            async def ui_logger(event):
                await log_event_to_ui(event_log, event)

            subscribers = [ui_logger]
            if step_tracker is not None:
                subscribers.append(step_tracker.handle_event)
            subscribers.append(agent_stepper.handle_event)

            event_publisher = EventPublisher(subscribers=subscribers)

            # Run Agent
            try:
                await run_agent_cycle(
                    prompt=text,
                    event_publisher=event_publisher,
                    output_callback=output_area.set_content
                )
            except Exception as e:
                output_area.set_content(f"Error: {e}")
                if event_log is not None:
                    event_log.push(f"error: {e}")
            finally:
                ask_button.enable()

        with ui.row().classes('w-full justify-end'):
            ask_button = ui.button("Ask", on_click=on_submit).props('padding="xs lg"')

    # 2. Interactive Stepper (Agent Progress)
    tool_map = {
        "execute_step": "Executing research step",
        "draft_plan": "Drafting a plan",
        "random_number": "Generating random number",
        "web_search": "Searching the web",
        "code_interpreter": "Running code"
    }
    agent_stepper = AgentStepper(
        tool_title_map=tool_map,
        hidden_tool_details=["execute_step"]
    )

    # 3. Response Area
    with ui.card().tight().classes('w-full max-w-xl'):
        with ui.card_section().classes('w-full'):
            ui.label("Response").classes('font-medium text-gray-800')
            output_area = ui.markdown("Waiting for a question…").classes('w-full min-h-[5rem] text-sm')

    # 4. Old Stepper (Legacy)
    step_tracker = StepTracker()

    # 5. Static Prototype (Comparison)
    with ui.expansion('Static Prototype', icon='o_compare').classes('w-full max-w-xl'):
        AgentStepperStatic()

    # 6. Full Log
    with ui.expansion('Event Log', icon='o_list').classes('w-full max-w-xl'):
        event_log = ui.log(max_lines=200).classes('w-full min-h-[12rem] text-xs')
        event_log.push("No events yet. Submit a prompt to see activity.")

ui.run(title="Mini agent demo")
