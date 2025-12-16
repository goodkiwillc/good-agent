from __future__ import annotations

from enum import Flag, auto

from good_agent.events.agent import AgentEvents


class EventSemantics(Flag):
    INTERCEPTABLE = auto()
    SIGNAL = auto()


_BOTH = EventSemantics.INTERCEPTABLE | EventSemantics.SIGNAL


EVENT_SEMANTICS: dict[AgentEvents, EventSemantics] = {
    # Agent lifecycle
    AgentEvents.AGENT_INIT_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.AGENT_INIT_AFTER: EventSemantics.SIGNAL,
    AgentEvents.AGENT_CLOSE_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.AGENT_CLOSE_AFTER: EventSemantics.SIGNAL,
    AgentEvents.AGENT_STATE_CHANGE: EventSemantics.SIGNAL,
    AgentEvents.AGENT_FORK_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.AGENT_FORK_AFTER: EventSemantics.SIGNAL,
    AgentEvents.AGENT_MERGE_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.AGENT_MERGE_AFTER: EventSemantics.SIGNAL,
    AgentEvents.AGENT_VERSION_CHANGE: EventSemantics.SIGNAL,

    # Extension lifecycle
    AgentEvents.EXTENSION_INSTALL_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.EXTENSION_INSTALL: EventSemantics.SIGNAL,
    AgentEvents.EXTENSION_INSTALL_AFTER: EventSemantics.SIGNAL,
    AgentEvents.EXTENSION_ERROR: EventSemantics.SIGNAL,

    # Messages
    AgentEvents.MESSAGE_CREATE_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.MESSAGE_CREATE_AFTER: EventSemantics.SIGNAL,
    AgentEvents.MESSAGE_APPEND_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.MESSAGE_APPEND_AFTER: EventSemantics.SIGNAL,
    AgentEvents.MESSAGE_REPLACE_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.MESSAGE_REPLACE_AFTER: EventSemantics.SIGNAL,
    AgentEvents.MESSAGE_SET_SYSTEM_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.MESSAGE_SET_SYSTEM_AFTER: EventSemantics.SIGNAL,
    AgentEvents.MESSAGE_RENDER_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.MESSAGE_RENDER_AFTER: EventSemantics.SIGNAL,
    AgentEvents.MESSAGE_PART_RENDER: EventSemantics.INTERCEPTABLE,

    # LLM
    AgentEvents.LLM_COMPLETE_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.LLM_COMPLETE_AFTER: _BOTH,
    AgentEvents.LLM_COMPLETE_ERROR: EventSemantics.SIGNAL,
    AgentEvents.LLM_EXTRACT_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.LLM_EXTRACT_AFTER: EventSemantics.SIGNAL,
    AgentEvents.LLM_EXTRACT_ERROR: EventSemantics.SIGNAL,
    AgentEvents.LLM_STREAM_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.LLM_STREAM_AFTER: EventSemantics.SIGNAL,
    AgentEvents.LLM_STREAM_CHUNK: EventSemantics.SIGNAL,
    AgentEvents.LLM_STREAM_ERROR: EventSemantics.SIGNAL,
    AgentEvents.LLM_ERROR: EventSemantics.SIGNAL,
    AgentEvents.TOOLS_PROVIDE: EventSemantics.INTERCEPTABLE,
    AgentEvents.TOOLS_GENERATE_SIGNATURE: EventSemantics.INTERCEPTABLE,

    # Tools
    AgentEvents.TOOL_CALL_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.TOOL_CALL_AFTER: EventSemantics.SIGNAL,
    AgentEvents.TOOL_CALL_ERROR: _BOTH,

    # Execution
    AgentEvents.EXECUTE_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.EXECUTE_AFTER: EventSemantics.SIGNAL,
    AgentEvents.EXECUTE_ERROR: EventSemantics.INTERCEPTABLE,
    AgentEvents.EXECUTE_ITERATION_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.EXECUTE_ITERATION_AFTER: EventSemantics.SIGNAL,
    AgentEvents.EXECUTE_ITERATION_ERROR: EventSemantics.INTERCEPTABLE,

    # Context and templates
    AgentEvents.CONTEXT_PROVIDER_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.CONTEXT_PROVIDER_AFTER: _BOTH,
    AgentEvents.CONTEXT_PROVIDER_ERROR: EventSemantics.INTERCEPTABLE,
    AgentEvents.TEMPLATE_COMPILE_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.TEMPLATE_COMPILE_AFTER: _BOTH,
    AgentEvents.TEMPLATE_COMPILE_ERROR: EventSemantics.INTERCEPTABLE,

    # Storage
    AgentEvents.STORAGE_SAVE_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.STORAGE_SAVE_AFTER: EventSemantics.SIGNAL,
    AgentEvents.STORAGE_SAVE_ERROR: EventSemantics.INTERCEPTABLE,
    AgentEvents.STORAGE_LOAD_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.STORAGE_LOAD_AFTER: EventSemantics.SIGNAL,
    AgentEvents.STORAGE_LOAD_ERROR: EventSemantics.INTERCEPTABLE,

    # Cache
    AgentEvents.CACHE_HIT: EventSemantics.SIGNAL,
    AgentEvents.CACHE_MISS: EventSemantics.SIGNAL,
    AgentEvents.CACHE_SET: EventSemantics.SIGNAL,
    AgentEvents.CACHE_INVALIDATE: EventSemantics.SIGNAL,

    # Validation
    AgentEvents.VALIDATION_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.VALIDATION_AFTER: EventSemantics.SIGNAL,
    AgentEvents.VALIDATION_ERROR: EventSemantics.INTERCEPTABLE,

    # Modes
    AgentEvents.MODE_ENTERING: EventSemantics.SIGNAL,
    AgentEvents.MODE_ENTERED: EventSemantics.SIGNAL,
    AgentEvents.MODE_EXITING: EventSemantics.SIGNAL,
    AgentEvents.MODE_EXITED: EventSemantics.SIGNAL,
    AgentEvents.MODE_ERROR: EventSemantics.SIGNAL,
    AgentEvents.MODE_TRANSITION: EventSemantics.SIGNAL,

    # Citations
    AgentEvents.CITATIONS_EXTRACTED: EventSemantics.SIGNAL,
    AgentEvents.CITATIONS_UPDATED: EventSemantics.SIGNAL,

    # Web fetcher
    AgentEvents.FETCH_URL_REQUESTED: EventSemantics.SIGNAL,
    AgentEvents.FETCH_URL_STARTED: EventSemantics.SIGNAL,
    AgentEvents.FETCH_URL_COMPLETED: EventSemantics.SIGNAL,
    AgentEvents.FETCH_URL_ERROR: EventSemantics.SIGNAL,
    AgentEvents.CITATION_CONTENT_REQUESTED: EventSemantics.SIGNAL,
    AgentEvents.CITATION_CONTENT_RESOLVED: EventSemantics.SIGNAL,

    # Summary generation
    AgentEvents.SUMMARY_GENERATE_BEFORE: EventSemantics.INTERCEPTABLE,
    AgentEvents.SUMMARY_GENERATE_AFTER: EventSemantics.SIGNAL,
    AgentEvents.SUMMARY_GENERATE_ERROR: EventSemantics.INTERCEPTABLE,
}


def get_event_semantics(event: AgentEvents | str) -> EventSemantics | None:
    """Return the semantics classification for a given event."""

    try:
        key = AgentEvents(event)
    except ValueError:
        return None
    return EVENT_SEMANTICS.get(key)


__all__ = [
    "EventSemantics",
    "EVENT_SEMANTICS",
    "get_event_semantics",
]
