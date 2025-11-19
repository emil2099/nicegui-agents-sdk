import asyncio
import json
import os
from typing import Any

from dotenv import load_dotenv
from agents import Agent, Runner, WebSearchTool, CodeInterpreterTool
from agents import ModelSettings

# Load env vars
load_dotenv()

async def run_research():
    print("--- Starting Research ---")
    
    # Define a simple agent with the tools
    tools = [
        WebSearchTool(),
        CodeInterpreterTool(
            tool_config={
                "type": "code_interpreter",
                "container": {"type": "auto"},
            }
        )
    ]
    
    agent = Agent(
        name="Researcher",
        instructions="You are a researcher. Use tools when asked.",
        model="gpt-4o", # Using a capable model
        tools=tools
    )

    # Test 1: Web Search
    print("\n\n--- Test 1: Web Search (Weather in London) ---")
    result = await Runner.run(agent, "What is the weather in London right now?")
    
    # Inspect the final response object to find tool calls
    # We need to look at the chat history or the raw response if accessible.
    # Runner.run returns the final output string usually, but let's check if we can get more info.
    # Actually, let's use the hook approach to capture the raw data, as that's what we'll use in prod.
    
    from agents import AgentHooks, RunContextWrapper, ModelResponse
    
    class InspectionHook(AgentHooks):
        async def on_llm_end(self, context: RunContextWrapper, agent: Agent, response: ModelResponse) -> None:
            print(f"\n[HOOK] on_llm_end triggered for agent: {agent.name}")
            print("Response type:", type(response))
            print("Response dir:", dir(response))
            print("Response repr:", repr(response))
            
            # Inspect output items
            if hasattr(response, 'output'):
                for item in response.output:
                    print(f"\nItem type: {type(item)}")
                    print(f"Item dir: {dir(item)}")
                    if hasattr(item, 'type') and item.type == 'web_search_call':
                        print("--- Web Search Call Details ---")
                        print(f"Action: {item.action}")
                        if hasattr(item.action, 'sources'):
                             print(f"Action Sources: {item.action.sources}")
                        
                        # Check for outputs or results
                        if hasattr(item, 'outputs'):
                             print(f"Outputs: {item.outputs}")
                        
                        # Dump dict if possible
                        if hasattr(item, '__dict__'):
                             print(f"Item Dict: {item.__dict__}")
                        
            # Let's also print the full raw response to see if there's anything else
            # print(json.dumps(response.model_dump(), indent=2, default=str))

    agent.hooks = InspectionHook()
    
    # Re-run with hooks
    print("\n--- Re-running Web Search with Hooks ---")
    result = await Runner.run(agent, "What is the weather in London right now? Search for it.")
    print("Final Result:", result)

    # Test 2: Code Interpreter
    # print("\n\n--- Test 2: Code Interpreter (Fibonacci) ---")
    # result = await Runner.run(agent, "Calculate the 10th Fibonacci number using python.")
    # print("Final Result:", result)

if __name__ == "__main__":
    asyncio.run(run_research())
