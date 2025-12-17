# Changelog

All notable changes to the good-agent library will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.3] - 2025-12-17

- TODO: Document release notes.


### BREAKING CHANGES
- **Singular mode entry API**: Enter modes with `agent.mode("name", **params)`.
  The legacy `agent.modes["name"]` indexer now raises an error to prevent
  accidental use of the removed API.

### Changed
- `agent.mode` is callable and returns the mode context manager, keeping
  `agent.modes` focused on registration/inspection APIs.
- Documentation, examples, and tests now demonstrate the updated mode entry
  syntax.

## [0.6.2] - 2025-12-15

- TODO: Document release notes.


### BREAKING CHANGES
- **Mode handlers must now yield**: All mode handlers must be async generators that yield exactly once.
  Simple async functions (without yield) are no longer supported. This provides cleaner setup/cleanup lifecycle.
  
  ```python
  # OLD (no longer works):
  @agent.modes("research")
  async def research_mode(agent: Agent):
      return await agent.call()
  
  # NEW (required):
  @agent.modes("research")
  async def research_mode(agent: Agent):
      # setup code here
      yield agent
      # cleanup code here (optional)
  ```
  
- **Invokable tool names changed**: Default tool names changed from `enter_{name}_mode` to `enter_{name}`.
  For example, `enter_research_mode` is now `enter_research`.

### Added
- **Parameterized Mode Entry**: Pass parameters when entering modes:
  ```python
  async with agent.mode("research", topic="quantum", depth=3):
      print(agent.mode.state["topic"])  # "quantum"
  ```
- **Mode-Aware System Prompt**: Invokable modes automatically inject awareness into the system prompt,
  showing current mode, stack, and available modes to the LLM.
- **Mode History Tracking**:
  - `agent.mode.history` - List of all modes entered this session
  - `agent.mode.previous` - Previously active mode name
  - `agent.mode.return_to_previous()` - Create transition to previous mode
- **Additional Mode Events**:
  - `MODE_ENTERING` - Before setup runs
  - `MODE_EXITING` - Before cleanup runs
  - `MODE_ERROR` - Exception in handler (includes phase: setup/cleanup)
  - `MODE_TRANSITION` - Handler requested transition (includes from/to modes)
- **Improved Invokable Tool Responses**: Rich responses showing mode purpose and guidelines
- **Already Active Check**: Mode tools now check if already in mode and return early
- **ModeHandlerError**: New exception for invalid mode handler definitions

## [0.6.1] - 2025-11-28

- TODO: Document release notes.


## [0.6.0] - 2025-11-27

- TODO: Document release notes.


### Added
- **Agent Modes v2 API**: New agent-centric mode handler signature `async def handler(agent: Agent)`
  - `agent.mode.name` - Current mode name
  - `agent.mode.stack` - Active mode stack
  - `agent.mode.state` - Mode state dictionary
  - `agent.mode.switch(name)` - Request mode transition
  - `agent.mode.exit()` - Request mode exit
  - `agent.mode.in_mode(name)` - Check if mode is active
- **SystemPromptManager** (`agent.prompt`) for dynamic system prompt composition
  - `agent.prompt.append(msg)` / `agent.prompt.prepend(msg)` - Add to prompt
  - `agent.prompt.sections[name]` - Named prompt sections
  - `agent.prompt.render()` - Get composed prompt
  - Auto-restore on mode exit (unless `persist=True`)
- **Isolation Levels**: `none`, `config`, `thread`, `fork` for mode isolation
- **Invokable Modes**: Generate tools for agent self-switching with `invokable=True`
- **Standalone Modes**: `@mode()` decorator for reusable mode definitions
- **Generator Mode Handlers**: Async generator support for setup/cleanup lifecycle
  - Use `yield` to separate setup (before) and cleanup (after) phases
  - Cleanup guaranteed via try/finally, even on exceptions
  - Exception handling via `try/except` around yield
  - `agent.mode.set_exit_behavior()` to control post-exit LLM behavior
- **ModeExitBehavior**: Enum to control execute loop behavior after mode exit
  - `CONTINUE` - Always call LLM after mode exit
  - `STOP` - Don't call LLM, return control immediately
  - `AUTO` - Call LLM only if conversation is pending (default)
- **Mode Transition Handling**: Mode changes triggered by tools apply immediately within same execute() call

### Deprecated
- `ModeContext` signature - Use `agent: Agent` parameter instead

## [0.5.2] - 2025-11-26

- TODO: Document release notes.


## [0.5.1] - 2025-11-26

- TODO: Document release notes.


## [0.5.0] - 2025-11-26

- TODO: Document release notes.


## [0.4.2] - 2025-11-22

- TODO: Document release notes.


## [0.4.1] - 2025-11-22

- TODO: Document release notes.


## [0.4.0] - 2025-11-22

- TODO: Document release notes.


## [0.3.3] - 2025-11-22

- TODO: Document release notes.


## [0.3.2] - 2025-11-21

- TODO: Document release notes.


## [0.3.1] - 2025-11-21

- TODO: Document release notes.


## [0.3.0] - 2025-11-21

- TODO: Document release notes.
