"""Barebones NiceGUI page that triggers an OpenAI Agent run."""

from __future__ import annotations

from nicegui import ui

from agent_service import run_plan_execute

ui.colors(primary="#000000")
ui.button.default_props('unelevated')
ui.card.default_props('flat bordered')

with ui.column().classes(
    'min-h-screen w-full items-center justify-center px-4 py-16 box-border'
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

                    stream = run_plan_execute(text)

                    chunks: list[str] = []
                    try:
                        async for chunk in stream:
                            if chunk:
                                chunks.append(chunk)
                                output_area.set_content("".join(chunks))
                    except Exception as e:
                        output_area.set_content(f"Error: {e}")
                    finally:
                        ask_button.enable()

                    if not chunks:
                        output_area.set_content("(no response)")

        ui.separator()
        with ui.card_actions().classes('w-full items-center justify-between gap-4 p-4'):

            ask_button = ui.button("Ask", on_click=on_submit).props('padding="xs md"').classes('ml-auto')

    with ui.card().tight().classes('w-full max-w-xl mt-6'):
        with ui.card_section().classes('w-full'):
            ui.label("Response").classes('font-medium')
            output_area = ui.markdown("Waiting for a question…").classes('w-full min-h-[10rem]')

ui.run(title="NiceGUI + OpenAI Agents Demo")
