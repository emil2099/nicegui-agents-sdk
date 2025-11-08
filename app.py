"""Barebones NiceGUI page that triggers an OpenAI Agent run."""

from __future__ import annotations
from nicegui import ui

# ⬇️ Keep existing simple path; add run_plan_execute for the multi-agent flow
from agent_service import run_prompt, run_plan_execute

ui.colors(primary="#000000")
ui.button.default_props('unelevated')
ui.card.default_props('flat bordered')
ui.toggle.default_props('unelevated')

with ui.column().classes(
    'min-h-screen w-full items-center justify-center px-4 py-16 box-border'
):
    with ui.card().tight().classes('w-full max-w-xl'):
        with ui.card_section().classes('w-full'):
            with ui.column().classes('gap-4'):
                ui.label("Ask the GPT-5 mini agent").classes('font-medium')
            
                prompt_input = ui.textarea(
                    placeholder="Ask me anything"
                ).props("autogrow outlined dense").classes('w-full ')
                output_area = ui.markdown("Waiting for a question…")

                async def on_submit() -> None:
                    output_area.set_content("Thinking…")
                    text = prompt_input.value.strip()
                    if not text:
                        output_area.set_content("Please enter a prompt.")
                        return

                    if mode.value == 'plan':
                        # multi-agent brief with citations (markdown)
                        response_md = await run_plan_execute(text)
                        output_area.set_content(response_md)
                    else:
                        # original single-agent path
                        response = await run_prompt(text)
                        output_area.set_content(response)
                
        ui.separator()
        with ui.card_actions().classes('w-full items-center justify-between gap-4 p-4'):

            # ⬇️ Tiny mode switch; default is your current behaviour
            mode = ui.toggle(
                options={
                    'simple': 'Simple',
                    'plan': 'Complex',
                },
                value='plan',
            ).props('padding="xs sm"').classes('border')

            ui.button("Ask", on_click=on_submit).props('padding="xs md"').classes('ml-auto')

ui.run(title="NiceGUI + OpenAI Agents Demo")
