# Feedback Vision: Calm, Clear, and Honest

This UI should feel like a great teammate: it tells you what it’s doing, why, and when it’s done—without noise.

## What Users See
- One spinner whose label updates as work evolves.
- One compact log that reads like a story, not a trace.
- Clear tool usage (“Searching the web… done”).
- A final answer (or an honest error) without guesswork.

## Three States Are Enough
- Thinking: an agent is planning or composing.
- Using a tool: a concrete step is in progress.
- Delivering: the system is stitching results into a response.

Everything else lives behind “Show details”.

## Map Events → States
- agent_started → Thinking
- llm_started → Thinking (refresh label)
- llm_ended with tool calls → Using a tool (show tool name immediately)
- tool_started → Using a tool (confirm)
- tool_ended → Delivering (or remain Using a tool if more calls follow)
- agent_ended → Final (stop spinner, show answer)

De-duplication: key on `{agent}:{phase}:{call_id or turn_id}` and overwrite repeat entries.

## Minimal Path to MVP
- State machine with labels `"Thinking" | "Using <tool>" | "Delivering"`.
- Log only on state change or new content (first 140 chars for tool output).
- Parse tool intents from `llm_ended.response.output` and merge with `tool_started/ended` by `call_id`.
- Errors raise an error banner and stop the spinner.

## Build It Simply
- Normalizer: convert each incoming event to `{ts, agent, kind, payload}`.
- Turn tracker: keep `{active_agent, turn_id, last_phase, last_call_id}` per agent.
- Upserter: write or update a log row by the de-dup key.
- Debug toggle: collapsible raw payload snippets when needed.

## Why This Works
It captures the real rhythm (Think → Do → Deliver), stays honest about waiting and errors, and avoids drowning users in mechanics.

## Later
- Visual timeline of handoffs (Manager → Executor → Manager).
- Usage/token counters next to each state.
- Persisted history for shareable transcripts.
