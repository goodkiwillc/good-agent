## ADDED Requirements
### Requirement: Mode entry uses singular accessor
Agent instances SHALL expose a callable `agent.mode(name, **params)` that returns the async context manager for a registered mode, while the plural manager (`agent.modes`) remains dedicated to registering and inspecting modes.

#### Scenario: Entering a registered mode via `agent.mode`
- **GIVEN** an agent with a mode registered through `@agent.modes("research")`
- **WHEN** a consumer executes `async with agent.mode("research", topic="ai")`
- **THEN** the `research` handler MUST run with `agent.mode.name == "research"`
- **AND** the provided parameters MUST be available via `agent.mode.state` during the mode's execution

#### Scenario: Legacy plural indexer is unavailable for entry
- **GIVEN** the same registered mode
- **WHEN** a consumer attempts to enter it via `agent.modes["research"]`
- **THEN** the library MUST raise an error explaining that mode entry now uses `agent.mode()` and MUST NOT silently alias the plural indexer
