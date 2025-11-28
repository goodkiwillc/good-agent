# Changelog

All notable changes to the good-agent library will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
