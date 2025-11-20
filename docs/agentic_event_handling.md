# Agentic Event Handling

This document details the event-driven architecture used to provide observability into the agent's execution lifecycle.

## Core Components

The system relies on three main components defined in `agentic/core/events.py` and `agentic/core/hooks.py`:

1.  **`AgentEvent`**: The data object representing a single event.
2.  **`EventPublisher`**: The mechanism for dispatching events to subscribers.
3.  **`EventPublishingHook`**: An agent hook that intercepts lifecycle methods and publishes them as events.

### 1. AgentEvent

The `AgentEvent` is a Pydantic model that standardizes the structure of all events.

```python
class AgentEvent(BaseModel):
    timestamp: datetime      # UTC timestamp of the event
    event_type: str          # Unique identifier for the event type
    source: str              # Name of the agent or component generating the event
    span_id: Optional[str]   # Tracing span ID (if available)
    data: Dict[str, Any]     # Flexible payload containing event-specific data
```

### 2. EventPublisher

The `EventPublisher` manages a list of subscribers and broadcasts events to them. It supports both synchronous and asynchronous subscribers.

```python
# Subscriber signature
EventSubscriber = Callable[[AgentEvent], Awaitable[None]]

# Usage
async def my_subscriber(event: AgentEvent):
    print(f"Received: {event.event_type}")

publisher = EventPublisher(subscribers=[my_subscriber])
await publisher.publish_event(event)
```

### 3. EventPublishingHook

The `EventPublishingHook` connects the OpenAI Agents SDK's internal lifecycle to our event system. It implements the `AgentHooks` interface and automatically emits events during agent execution.

**Key Lifecycle Events:**

*   **`agent_started_stream_event`**: Agent begins execution.
*   **`llm_started_stream_event`**: LLM inference starts (includes system prompt).
*   **`llm_ended_stream_event`**: LLM inference completes (includes response).
*   **`tool_started_stream_event`**: Tool execution begins.
*   **`tool_ended_stream_event`**: Tool execution completes.
*   **`agent_ended_stream_event`**: Agent finishes execution.

**Specialized Tool Events:**

The hook also inspects `ModelResponse` objects to emit high-level events for specific hosted tools:

*   **`tool_web_search_event`**: Emitted when a web search tool call is detected. Includes `query` and `sources`.
*   **`tool_code_interpreter_event`**: Emitted when code execution is detected. Includes `code` and `outputs`.

## Integration Flow

1.  **Workflow Setup**: An `EventPublisher` is created in the application layer (e.g., `app.py`) and passed into the workflow context.
2.  **Agent Configuration**: Agents are initialized with `EventPublishingHook()`.
3.  **Execution**: As the agent runs, the hook intercepts calls and uses the publisher from the context to emit `AgentEvent`s.
4.  **Consumption**: Subscribers (like `AgentStepper` or `AgentLogger`) receive these events and update the UI.
