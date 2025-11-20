"""Barebones NiceGUI page that triggers an OpenAI Agent run."""

from __future__ import annotations

from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from nicegui import app, ui

from agentic.core.events import EventPublisher
from agentic.workflows.plan_execute import run_plan_execute
from components.agent_stepper import AgentStepper
from components.agent_logger import AgentLogger

BASE_DIR = Path(__file__).parent

app.add_static_file(local_file='style.css', url_path='/style.css')
ui.add_head_html('<link rel="stylesheet" href="/style.css">', shared=True)
ui.colors(primary="#000000")
ui.button.default_props('unelevated')
ui.card.default_props('flat bordered')

event_logger: AgentLogger | None = None

with ui.column().classes('w-full items-center justify-center px-4 pt-16 box-border gap-4'):
    
    # 1. Combined Header & Input Card
    with ui.card().tight().classes('gradient-card w-full max-w-xl p-4 gap-4'):
        with ui.column().classes('gap-1'):
            with ui.row().classes('items-center gap-2 text-sm font-medium text-gray-800'):
                ui.icon('o_auto_awesome').classes('text-base text-indigo-500')
                ui.label('GPT-5 mini agent')
            ui.label('Lightweight agent that plans, executes, and reports each reasoning step.').classes('text-xs text-gray-600 leading-snug mt-2')

        prompt_input = ui.textarea(placeholder="Ask me anything").props("autogrow outlined dense rows=1").classes('w-full')
        
        async def on_submit() -> None:
            ask_button.disable()
            output_area.set_content("Thinking…")
            text = prompt_input.value.strip()
            if not text:
                output_area.set_content("Please enter a prompt.")
                ask_button.enable()
                return
            
            if event_logger:
                event_logger.clear()
                event_logger.push("listening for events…")
            
            # Setup subscribers
            subscribers = [agent_stepper.handle_event]
            if event_logger:
                subscribers.append(event_logger.handle_event)

            event_publisher = EventPublisher(subscribers=subscribers)

            try:
                chunks = []
                async for chunk in run_plan_execute(text, event_publisher=event_publisher):
                    if chunk:
                        chunks.append(chunk)
                        output_area.set_content("".join(chunks))
                if not chunks:
                    output_area.set_content("(no response)")
            except Exception as e:
                output_area.set_content(f"Error: {e}")
                if event_logger:
                    event_logger.push(f"error: {e}")
            finally:
                ask_button.enable()

        with ui.row().classes('w-full justify-end'):
            ask_button = ui.button("Ask", on_click=on_submit).props('padding="xs lg"')

    # 2. Interactive Stepper
    agent_stepper = AgentStepper(
        tool_title_map={
            "execute_step": "Executing research step",
            "draft_plan": "Drafting a plan",
            "random_number": "Generating random number",
            "web_search": "Searching the web",
            "code_interpreter": "Running code"
        },
        hidden_tool_details=["execute_step"]
    )

    # 3. Response Area
    with ui.card().tight().classes('w-full max-w-xl'):
        with ui.card_section().classes('w-full'):
            ui.label("Response").classes('font-medium text-gray-800')
            output_area = ui.markdown("Waiting for a question…").classes('w-full min-h-[5rem] text-sm')

    # 4. Full Log
    with ui.expansion('Event Log', icon='o_list').classes('w-full max-w-xl'):
        event_logger = AgentLogger(max_lines=200).classes('w-full min-h-[12rem] text-xs')
        event_logger.push("No events yet.")

ui.run(title="Mini agent demo")
