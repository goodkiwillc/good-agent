import warnings

import pytest

from good_agent import Agent


class TestAgentPublicApiSurface:
    @pytest.mark.asyncio
    async def test_agent_public_attribute_guard(self) -> None:
        """Agent exposes only the documented public attribute set."""

        async with Agent("surface guard test") as agent:
            with warnings.catch_warnings(record=True):
                public = [name for name in dir(agent) if not name.startswith("_")]

        assert len(public) == len(Agent.public_attribute_names())
        assert set(public) == set(Agent.public_attribute_names())


__all__ = ["TestAgentPublicApiSurface"]
