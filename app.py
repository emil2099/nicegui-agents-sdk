"""Barebones NiceGUI page that triggers an OpenAI Agent run."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from nicegui import ui

from agents import Agent, Runner

# Load environment variables (expects OPENAI_API_KEY inside .env)
load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Create it in your .env or export it before running the app."
    )

# Define a minimal single-agent workflow that uses GPT-5 mini.
assistant = Agent(
    name="NiceGUI helper",
    instructions="Answer succinctly and mention one follow-up idea when helpful.",
    model_config={"model": "gpt-5-mini"},
)


async def ask_agent(prompt: str) -> str:
    """Run the agent and return its final output, or a fallback message."""
    if not prompt.strip():
        return "Please enter a question first."

    result = await Runner.run(assistant, prompt)
    return result.final_output or "The agent finished without returning text."


with ui.card():
    ui.label("Ask the GPT-5 mini agent")
    prompt_input = ui.textarea(
        label="Prompt",
        placeholder="e.g. Summarize the first three laws of motion.",
        value="",
    ).props("autogrow")
    output_area = ui.markdown("Waiting for a question…")

    async def on_submit() -> None:
        output_area.set_text("Thinking…")
        response = await ask_agent(prompt_input.value)
        output_area.set_text(response)

    ui.button("Ask", on_click=on_submit).props("color=primary")


ui.run(title="NiceGUI + OpenAI Agents Demo")
