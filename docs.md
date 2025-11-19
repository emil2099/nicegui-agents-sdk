# AgentStepper Component Documentation

The `AgentStepper` is a NiceGUI component designed to visualize the execution flow of an AI agent. It provides a linear, timeline-style view of the agent's actions, including thinking processes, tool usage, and final results.

## Features

- **Linear Visualization**: Flattens complex, nested agent events into a simple, easy-to-follow timeline.
- **Real-time Updates**: Reacts to `AgentEvent` streams to update the UI dynamically.
- **Customizable Tool Names**: Supports a mapping dictionary to convert technical tool names into user-friendly titles.
- **Extensible Rendering**: Uses a protocol-based renderer system (`StepRenderer`) to handle different step types.
- **Minimalist Design**: Adheres to a clean "rail" design aesthetic with shimmer effects for active states.

## Usage

### Basic Instantiation

```python
from ui_components.agent_stepper import AgentStepper

# Create the stepper
stepper = AgentStepper()

# Add it to your UI
with ui.card():
    stepper.render() # (It renders itself on __init__)
```

### Custom Tool Titles

You can provide a `tool_title_map` to customize how tool names appear in the UI.

```python
tool_map = {
    "search_web": "Searching the Internet",
    "calculator": "Crunching Numbers",
    "read_file": "Reading Document"
}

stepper = AgentStepper(tool_title_map=tool_map)
```

### Handling Events

The component exposes an async `handle_event` method that should be connected to your event stream.

```python
async def on_agent_event(event: AgentEvent):
    await stepper.handle_event(event)
```

## Architecture

### `AgentStepper` (Orchestrator)
The main UI component inheriting from `ui.list`. It manages the overall container, the header status, and delegates step logic to `StepManager`.

### `StepManager` (Logic)
A pure Python class responsible for:
- Processing `AgentEvent`s.
- Maintaining the list of `Step` objects.
- Determining the state of each step (PENDING, RUNNING, COMPLETED).
- Flattening nested events (e.g., ignoring sub-agent events unless relevant).

### `Step` (Data Model)
A dataclass representing a single unit of work:
- `type`: THINKING, TOOL, MESSAGE, FINISHED.
- `title`: Display text.
- `status`: Current state.
- `data`: Associated event data (e.g., tool inputs/outputs).

### `StepRenderer` (UI Protocol)
Defines how each `StepType` is rendered.
- `ThinkingRenderer`: Handles "Thinking..." steps.
- `ToolRenderer`: Handles tool execution and results (with truncation and tooltips).
- `FinishedRenderer`: Handles the final completion step.

## Extension

To add a new step type:
1. Add the type to `StepType` enum.
2. Update `StepManager` to create steps of this type from events.
3. Create a new `Renderer` class implementing `StepRenderer`.
4. Register the new renderer in `AgentStepper._render_step_content`.
