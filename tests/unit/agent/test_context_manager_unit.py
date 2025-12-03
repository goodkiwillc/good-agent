from types import SimpleNamespace

from good_agent.agent.context import ContextManager


class StubMessage:
    def __init__(self, content: str):
        self.content = content
        self._agent = None
        self.id = content

    def model_copy(self):
        return StubMessage(self.content)

    def _set_agent(self, agent):
        self._agent = agent


class StubAgent:
    def __init__(self, **config):
        self._config = config
        self.config = SimpleNamespace(as_dict=lambda: self._config.copy())
        self._component_registry = SimpleNamespace(
            clone_extensions_for_config=lambda cfg, overrides: None
        )
        self.template = SimpleNamespace(context_provider=lambda name: f"provider:{name}")
        self._messages: list[StubMessage] = []
        self.system: list[StubMessage] = []
        self.append_calls: list[StubMessage] = []
        self.set_system_calls: list[StubMessage] = []

    def append(self, message: StubMessage):
        self.append_calls.append(message)
        self._messages.append(message)
        return message

    def set_system_message(self, message: StubMessage) -> None:
        self.set_system_calls.append(message)
        self.system = [message]


def test_context_manager_copy_includes_messages():
    agent = StubAgent(mode="source")
    agent._messages = [StubMessage("hello")]

    manager = ContextManager(agent)
    copied = manager.copy(include_messages=True, mode="copy")

    assert isinstance(copied, StubAgent)
    assert copied._config["mode"] == "copy"
    assert len(copied._messages) == 1
    assert copied._messages[0] is not agent._messages[0]
    assert copied._messages[0]._agent is copied


def test_context_manager_copy_preserves_system_without_messages():
    agent = StubAgent(mode="source")
    agent.system = [StubMessage("system")]  # type: ignore[list-item]

    manager = ContextManager(agent)
    copied = manager.copy(include_messages=False, mode="bare")

    assert copied._config["mode"] == "bare"
    assert copied.set_system_calls[0].content == "system"
    assert copied._messages == []


def test_context_manager_context_provider_delegates():
    agent = StubAgent()
    manager = ContextManager(agent)
    provider = manager.context_provider("user")
    assert provider == "provider:user"
