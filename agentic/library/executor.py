from agents import Agent, ModelSettings, WebSearchTool, CodeInterpreterTool
from openai.types.responses.web_search_tool_param import UserLocation
from agentic.core.hooks import EventPublishingHook

DEFAULT_MODEL = 'gpt-5.1'
DEFAULT_MODEL_SETTINGS = ModelSettings(tool_choice="auto")

BASE_TOOLS = [
    WebSearchTool(user_location=UserLocation(country='GB', type='approximate')),
    CodeInterpreterTool(
        tool_config={
            "type": "code_interpreter",
            "container": {"type": "auto"},
        }
    ),
]

executor_agent = Agent(
    name="Executor",
    instructions=(
        "Execute provided task. Use tools if helpful. "
        "For web results, include reputable sources with titles and URLs. "
        "For code, print concise, human-readable outputs."
    ),
    model=DEFAULT_MODEL,
    model_settings=DEFAULT_MODEL_SETTINGS,
    tools=BASE_TOOLS,
    hooks=EventPublishingHook(),
)

executor_tool = executor_agent.as_tool(
    tool_name="execute_step",
    tool_description=(
        "Use this to run a single research or analysis step. "
        "Pass the specific instructions and any context gathered so far."
    )
)
