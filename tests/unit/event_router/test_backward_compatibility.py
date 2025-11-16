from __future__ import annotations

import good_agent.core.event_router as event_router_module
from good_agent.core.event_router import EventContext, EventRouter, on


def test_package_import_path_exposes_public_api() -> None:
    assert hasattr(event_router_module, "EventRouter")
    assert hasattr(event_router_module, "EventContext")


class SampleComponent(EventRouter):
    def __init__(self) -> None:
        super().__init__()

    @on("component:test")
    def auto_registered(self, ctx: EventContext) -> None:
        ctx.output = "auto-works"


def test_auto_registration_still_occurs() -> None:
    component = SampleComponent()
    ctx = component.apply_sync("component:test")
    assert ctx.output == "auto-works"
