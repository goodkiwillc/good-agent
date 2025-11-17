"""Show how `Context` layers temporary overrides on top of agent config data."""

from __future__ import annotations

from good_agent.agent.config import AgentConfigManager, Context


def main() -> None:
    agent_config = AgentConfigManager()
    agent_config.context = {"product": "good-agent", "team": "research"}

    context = Context(agent_config=agent_config, environment="staging")
    print("base context:", context.as_dict())

    with context(role="planner", environment="prod"):
        print("override context:", context.as_dict())

    print("restored context:", context.as_dict())


if __name__ == "__main__":
    main()
