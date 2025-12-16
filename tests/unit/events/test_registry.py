from __future__ import annotations

from good_agent.events import (
    EVENT_PARAMS,
    EVENT_SEMANTICS,
    AgentEvents,
    EventSemantics,
    MessageAppendBeforeParams,
    MessageAppendParams,
    ToolCallBeforeParams,
    get_event_semantics,
    get_params_type,
)


def test_get_params_type_supports_enum_and_string() -> None:
    assert get_params_type(AgentEvents.TOOL_CALL_BEFORE) is ToolCallBeforeParams
    assert get_params_type("message:append:before") is MessageAppendBeforeParams
    assert get_params_type(AgentEvents.MESSAGE_APPEND_AFTER) is MessageAppendParams
    assert get_params_type("unknown:event") is None


def test_get_event_semantics_classification() -> None:
    assert get_event_semantics(AgentEvents.TOOL_CALL_BEFORE) == EventSemantics.INTERCEPTABLE

    append_after_semantics = get_event_semantics(AgentEvents.MESSAGE_APPEND_AFTER)
    assert append_after_semantics is not None
    assert EventSemantics.SIGNAL in append_after_semantics


def test_registries_cover_all_events() -> None:
    assert set(EVENT_PARAMS) == set(AgentEvents)
    assert set(EVENT_SEMANTICS) == set(AgentEvents)


def test_get_event_semantics_accepts_string() -> None:
    assert get_event_semantics("tool:call:before") == EventSemantics.INTERCEPTABLE
    assert get_event_semantics("unknown:event") is None
