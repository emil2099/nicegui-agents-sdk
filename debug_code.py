import asyncio
from dotenv import load_dotenv
from agents import Agent, Runner, CodeInterpreterTool, AgentHooks, RunContextWrapper, ModelResponse, Tool

# Load env vars
load_dotenv()

class InspectionHook(AgentHooks):
    async def on_llm_end(self, context: RunContextWrapper, agent: Agent, response: ModelResponse) -> None:
        print(f"\n[HOOK] on_llm_end")
        if hasattr(response, 'output'):
            for item in response.output:
                if hasattr(item, 'type') and item.type == 'code_interpreter_call':
                    print(f"  Code Interpreter Call found:")
                    print(f"  Code: {item.code[:50]}...")
                    print(f"  Outputs in on_llm_end: {item.outputs}")

    async def on_tool_end(self, context: RunContextWrapper, agent: Agent, tool: Tool, result: str) -> None:
        print(f"\n[HOOK] on_tool_end")
        print(f"  Tool: {tool.name}")
        print(f"  Result type: {type(result)}")
        print(f"  Result: {str(result)[:100]}...")

async def run_debug():
    print("--- Starting Code Interpreter Debug ---")
    
    # Configure tool with a dummy sandbox if needed, or rely on default if it works
    # Assuming CodeInterpreterTool works out of the box with API key
    tools = [CodeInterpreterTool(tool_config={'code_interpreter': {'enabled': True}})]
    
    agent = Agent(
        name="Coder",
        instructions="You are a python coder. Calculate 123 * 456 and print the result.",
        model="gpt-4o",
        tools=tools
    )
    
    agent.hooks = InspectionHook()
    
    print("\n--- Running Code Task ---")
    await Runner.run(agent, "Calculate 123 * 456 using python.")

if __name__ == "__main__":
    asyncio.run(run_debug())
