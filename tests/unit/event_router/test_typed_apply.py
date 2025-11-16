from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

import pytest

from good_agent.core.event_router import EventContext, EventRouter


@dataclass
class SumParams:
    left: int
    right: int


@dataclass
class SumResult:
    total: int


class LoginParams(TypedDict):
    username: str
    password: str


@dataclass
class LoginResult:
    token: str
    success: bool


def test_apply_typed_sync_instantiates_parameter_type() -> None:
    router = EventRouter()

    @router.on("typed:sum")
    def handler(ctx: EventContext[SumParams, SumResult]) -> SumResult:
        assert isinstance(ctx.parameters, SumParams)
        return SumResult(total=ctx.parameters.left + ctx.parameters.right)

    ctx = router.apply_typed_sync(
        "typed:sum", SumParams, SumResult, left=2, right=3
    )

    assert isinstance(ctx.parameters, SumParams)
    assert ctx.parameters.left == 2
    assert isinstance(ctx.output, SumResult)
    assert ctx.output.total == 5


@pytest.mark.asyncio
async def test_typed_apply_preserves_parameter_mapping_and_output_type() -> None:
    router = EventRouter()

    @router.on("typed:login")
    async def handler(ctx: EventContext[LoginParams, LoginResult]) -> LoginResult:
        assert isinstance(ctx.parameters, dict)
        return LoginResult(token=f"{ctx.parameters['username']}-token", success=True)

    typed_login = router.typed(LoginParams, LoginResult)

    ctx = await typed_login.apply(
        "typed:login", username="neo", password="trinity"
    )

    assert ctx.parameters["username"] == "neo"
    assert isinstance(ctx.output, LoginResult)
    assert ctx.output.token == "neo-token"
