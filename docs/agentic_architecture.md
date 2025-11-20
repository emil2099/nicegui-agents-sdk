# Decipher: Agentic architecture

## 1. Purpose and Objectives

This document defines the architectural standards for developing AI agents and workflows within Decipher. The objective is to establish a scalable, type-safe pattern for building agentic capabilities using the OpenAI Agents SDK.

**Key Objectives:**

- **Decoupling:** Ensure tools and agents are loosely coupled from the application infrastructure.
- **Flexibility:** Support a wide range of use cases delivered through rapid development with minimal boilerplate.
- **Reuse:** Support reuse ‘Lego blocks’ model for proven and standard functionality.
- **Observability:** Standardise event emission and output streaming across all workflows.

## 2. System Architecture

The architecture follows a **Functional Workflow** pattern. Logic is encapsulated in async functions rather than stateful manager classes. This is done to reduce boilerplate and avoid over-encapsulation.

### Architectural Layers

1. **Workflow Layer:** The orchestration entry points. These are functions that assemble contexts, initialise custom (templated) agents, and manage the execution loop.
2. **Agent Layer:**
    - **Library Agents:** Reusable, code-defined agents for specific repeatable tasks (e.g., Planning, Writing).
    - **Dynamic Agents:** Runtime instances constructed using Templates for core business logic.
3. **Capability Layer (Tools):** Pure functions providing specific capabilities (Search, RAG, Calculation).
4. **Core Utilities:** Shared helpers for event handling, streaming, and basic types.

## 3. Directory Structure

Implementation follows a domain-oriented structure separating logic (agentic) from infrastructure (services).

```
  /agents
     /core
        events.py         # Event publishing helpers & Hook definitions
        utils.py          # Stream processing utilities
     
     /tools               # Shared capabilities
        search.py         # Defines 'HasSearchDB' protocol locally
        rag.py            
     
     /library             # Reusable, static library agent definitions
        planner.py        # Exports 'planner_agent' instance & schemas
        coder.py
     
     /workflows           # Business Logic (Entry Points)
        research.py       # Defines 'DeepResearchContext' & workflow function
        chat.py
```

## 4. Tool Definition & Protocols

Tools are pure Python functions decorated with @function_tool. To ensure portability, tools must not rely on a global context class. Instead, they define **Local Protocols** specifying exactly what infrastructure they require.

### Implementation Standards

1. **Local Protocols:** Define dependencies (e.g., HasDB) inside the tool file.
2. **Dependency Injection:** Access services via ctx.context, validated by the Protocol.
3. **Custom Events:** Use emit_event for internal telemetry (e.g., search hit counts).

**Example: agents/tools/search.py**

```python
from typing import Protocol, Any, Optional
from agents import function_tool, RunContextWrapper
from agentic.core.events import emit_event

# 1. Define Local Protocol
class HasSearchDB(Protocol):
    db_service: Any
    event_publisher: Optional[Any]

# 2. Implement Tool
@function_tool
async def semantic_search(ctx: RunContextWrapper[HasSearchDB], query: str):
    """Performs a semantic search against the vector database."""
    
    # Safe custom event emission
    await emit_event(ctx, "tool_start", tool="semantic_search", query=query)

    # Type-safe access to DB via Protocol
    results = ctx.context.db_service.query_similar_text(query)

    return results
```

## 5. Agent Definitions

We utilise two distinct patterns for defining agents.

### A. Standard Library Agents

These are specialised library agents that are re-usable across use cases and workflows. They are defined statically in code.

**Key Requirements:**

- Define instructions as a constant variable for readability.
- Export the Agent instance for direct use in workflows.
- Export the agent .as_tool() if it needs to be called by other agents (e.g., a Supervisor).
- All agents must include the EventPublishingHook to ensure they emit events to the workflow context.

**File:** agents/library/planner.py

**Exports:** The Agent instance and its Output Schema.

```python
from agents import Agent
from pydantic import BaseModel
from agents.core.events import EventPublishingHook

# 1. Define Output Schema
class Plan(BaseModel):
    steps: list[str]

# 2. Define System Prompt
PLANNER_INSTRUCTIONS = """
You are a planning algorithm.
Break the user request into logical execution steps.
Return the result strictly as a list of strings.
"""

# 3. Define Agent Instance
planner_agent = Agent(
    name="Planner",
    model="gpt-4o", 
    instructions=PLANNER_INSTRUCTIONS,
    output_type=Plan,
    # 4. Attach Observability (Mandatory)
    # This ensures the agent uses the context's publisher to log events
    hooks=EventPublishingHook() 
)

# 5. Export as Tool (For Sub-Agent Usage)
# This allows a 'Manager' agent to call the planner as a function
planner_tool = planner_agent.as_tool(
    tool_name="create_plan",
    tool_description="Generates a structured execution plan for a complex task."
)
```

### B. Dynamic Business Agents

These agents handle core business use cases where prompts, models, and personas are managed via the LLMTemplate service. These agents are **constructed at runtime** inside the workflow.

*Note: No specific file definition exists for these. They are assembled programmatically.*

## 6. Workflow Implementation

A Workflow is an async function that orchestrates the process. It is responsible for:

1. Defining the Workflow-Specific Context (Dataclass).
2. Handling pre-processing logic.
3. Instantiating Dynamic Agents using Templates.
4. Executing the Runner and streaming output.

### Context Management

Each workflow defines its own Context Dataclass. This acts as the bridge between Global Services (passed in) and Tool Protocols (consumed).

### Streaming Utility

To maintain clean workflow code, use a utility function to strip raw events and yield only final text tokens.

**Example: src/agentic/workflows/research.py**

```python
from dataclasses import dataclass
from typing import AsyncIterator, Any
from agents import Runner, Agent

from agentic.tools.search import semantic_search, enrich_query
from agentic.core.utils import stream_final_text
from agentic.core.events import EventPublishingHook

# 1. Define Workflow-Specific Context
@dataclass
class DeepResearchContext:
    db_service: Any             # Satisfies HasSearchDB
    event_publisher: Any        # Satisfies HasEvents
    template: Any               # The resolved LLMTemplate
    obligation_doc_id: str      # Workflow-specific state

# 2. Define Workflow Function
async def deep_research_workflow(
    user_query: str, 
    context: DeepResearchContext
) -> AsyncIterator[str]:
    
    current_query = user_query

    # Logic: Conditional Pre-processing
    if context.obligation_doc_id:
        enriched = await enrich_query(context, user_query)
        current_query = enriched or user_query

    # Logic: Dynamic Agent Construction
    # We map the Template directly to the Agent, explicitly adding tools
    researcher = Agent(
        name=context.template.name,
        model=context.template.model_name,
        instructions=context.template.compose_system_prompt(),
        tools=[semantic_search],
        hooks=EventPublishingHook() # Attach standard observability hooks
    )

    # Logic: Execution
    # Pass session_id if conversation history is required
    result_stream = Runner.run_streamed(
        researcher, 
        input=current_query, 
        context=context
    )

    # Use utility to stream only text tokens to the caller
    async for token in stream_final_text(result_stream):
        yield token
```

## 7. Event Handling & Observability

Observability is managed via an event bus pattern. This requires coordination between the **Workflow Context** (which holds the transport) and the **Agent** (which generates the signals).

### A. Infrastructure Requirements

The core event infrastructure resides in src/agents/core/events.py. This includes:

1. EventPublisher: The class responsible for dispatching events to the UI/Client.
2. EventPublishingHook: A specific implementation of the SDK's AgentHooks that intercepts lifecycle methods (Start, End, Tool Call) and forwards them to the publisher.

### B. Workflow Implementation Guide

To enable observability, developers must explicitly wire the publisher into the context and attach the hook to the agent.

**1. Receive and Store the Publisher**

The event_publisher is injected into the workflow from the external service layer. It must be stored in the Workflow Context, which must satisfy the HasEvents protocol.

```python
@dataclass
class ResearchContext:
    # ... other fields ...
    event_publisher: Any  # REQUIRED: Must match HasEvents protocol
```

**2. Attach the Hook to Agents**

When instantiating an Agent—whether it is a **Standard Stable Agent** or a **Dynamic Agent**—you must attach the EventPublishingHook. The hook is responsible for extracting the publisher from the context at runtime.

*For Dynamic Agents (in Workflow):*

```python
from agents.core.events import EventPublishingHook

researcher = Agent(
    name=template.name,
    # ... model/instructions ...
    hooks=EventPublishingHook()  # <--- MANDATORY for observability
)
```

*For Standard Agents (in Library):*

```python
planner_agent = Agent(
    name="Planner",
    # ...
    hooks=EventPublishingHook()  # <--- Defined once, applies everywhere
)
```

### C. Custom Tool Events

While the Hook handles standard lifecycle events (Agent Start, Tool Call Start), specific tool logic (e.g., "Search found 0 results") requires manual emission.

Tools must use the emit_event helper. This helper inspects the context, verifies the presence of the event_publisher, and safely dispatches the event.

```python
# Inside a tool function
from agents.core.events import emit_event

await emit_event(ctx, "tool_custom_status", msg="Filtering 500 records...")
```

## 8. Session Management

Conversation history and state persistence are managed natively by the OpenAI Agents SDK via the Runner. The architecture decouples the **storage mechanism** (Redis, Postgres, File) from the **workflow logic**.

### A. Principles

- **Stateless Workflows:** Workflow functions themselves are stateless. They receive state (History) via the session_id.
- **Automatic Persistence:** When a session_id is provided, the Runner automatically loads prior messages, appends the new user query, executes the agent, and saves the resulting tool calls and responses back to storage.
- **Infrastructure Configuration:** The actual persistence layer (e.g., FileStore, RedisStore) is configured at the Application entry point (main.py or services/), not within the workflow files.

*For deep dives on storage backend configuration, refer to the [**OpenAI Agents SDK - Persistence Documentation**](https://www.google.com/url?sa=E&q=https%3A%2F%2Fgithub.com%2Fopenai%2Fopenai-agents-python).*

### B. Implementation in Workflows

To enable conversational memory, the workflow function must accept a session_id argument and pass it to the Runner.

**Example: src/agents/workflows/chat.py**

```python
from typing import AsyncIterator, Optional
from agents import Runner, Agent
from agentic.core.utils import stream_final_text

async def chat_workflow(
    user_query: str, 
    context: ChatContext,
    session_id: Optional[str] = None # <--- 1. Accept Session ID
) -> AsyncIterator[str]:
    
    # Construct the agent (Standard or Dynamic)
    agent = Agent(
        name=context.template.name,
        model=context.template.model_name,
        instructions=context.template.compose_system_prompt(),
        hooks=EventPublishingHook()
    )

    # Execute with History
    # If session_id is provided, the Runner loads previous context.
    # If None, it runs as a stateless, single-turn interaction.
    result_stream = Runner.run_streamed(
        agent, 
        input=user_query, 
        context=context,
        session_id=session_id  # <--- 2. Pass to Runner
    )

    async for token in stream_final_text(result_stream):
        yield token
```