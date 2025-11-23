# Global Configuration Store & Profiles

## Overview

This feature adds a persistent global configuration store to `good-agent`, allowing users to save API keys and other settings across sessions. It replaces the reliance solely on environment variables, although environment variables will retain higher precedence. It also introduces "profiles" to manage different sets of configurations (e.g., `dev`, `prod`, `personal`).

## Requirements

### 1. Storage
- Configuration MUST be stored in `~/.good-agent/config.toml`.
- The file format MUST be TOML.
- Permissions on the directory and file SHOULD be restricted (e.g., 0600) to protect sensitive keys.

### 2. Configuration Precedence
The agent MUST resolve configuration values in the following order (highest to lowest):
1.  **Environment Variables** (e.g., `export OPENAI_API_KEY=...`)
2.  **Active Profile Configuration** (if a profile is selected)
3.  **Default Global Configuration** (the `[default]` section or root of config file)

### 3. Profiles
- Users can define multiple named profiles.
- A "default" profile exists implicitly.
- Users can select a profile via a CLI flag (e.g., `--profile personal`).

### 4. CLI Commands
The following commands MUST be implemented under a `config` subcommand:

- `good-agent config set [key] [value]`
    - Sets a value in the configuration.
    - Supports `--profile [name]` flag.
- `good-agent config get [key]`
    - Gets a value (resolving precedence).
    - Supports `--profile [name]` flag.
- `good-agent config list`
    - Lists all set values for the current context.
    - Hides/Masks sensitive values (like keys starting with `sk-`).
- `good-agent config profile use [name]` (Optional/Future) or just rely on `--profile` flag for runtime.
    - *Decision*: For now, we will rely on `--profile` flag for execution, but maybe store a "current_profile" setting in a separate state file if needed. For this MVP, `--profile` flag or `GOOD_AGENT_PROFILE` env var is sufficient.

### 5. Key Mapping
- To support user-friendly keys like `open-ai` mapping to `OPENAI_API_KEY`, the system SHOULD maintain a mapping of common aliases.
- If a key is not a known alias, it is treated as an Environment Variable name directly (or auto-uppercased).

## Implementation Details

### Data Model (TOML Structure)

```toml
# ~/.good-agent/config.toml

# Global/Default settings
[default]
OPENAI_API_KEY = "sk-..."
ANTHROPIC_API_KEY = "sk-..."
model = "gpt-4o"

# 'personal' profile
[profile.personal]
OPENAI_API_KEY = "sk-personal-..."

# 'work' profile
[profile.work]
OPENAI_API_KEY = "sk-work-..."
model = "claude-3-sonnet"
```

### Integration Logic

1.  **Initialization**:
    - In `good_agent.cli.main` (or a new `good_agent.config.global` module), before the agent is built.
    - Load `~/.good-agent/config.toml`.
    - Determine active profile (from `--profile` arg or `GOOD_AGENT_PROFILE` env var, defaulting to `default`).
    - Merge configs: `Default` -> `Profile`.

2.  **Environment Injection**:
    - Iterate through the merged config.
    - For each Key/Value:
        - If `os.environ` does NOT contain the Key:
            - Set `os.environ[Key] = Value`.
    - This ensures `litellm` and other libraries (like `instructor`) that look for specific env vars find them, while respecting existing env vars (Requirement #2).

### CLI UX

#### Setting a key
```bash
$ good-agent config set open-ai sk-12345
# Maps 'open-ai' -> 'OPENAI_API_KEY' automatically
# Saves to [default] section
> Set OPENAI_API_KEY in default profile.
```

#### Setting with profile
```bash
$ good-agent config set anthropic sk-98765 --profile work
# Maps 'anthropic' -> 'ANTHROPIC_API_KEY'
# Saves to [profile.work] section
> Set ANTHROPIC_API_KEY in 'work' profile.
```

#### Running with profile
```bash
$ good-agent run --profile work "Analyze this"
# Loads [default], overlays [profile.work], injects into env, runs agent.
```

## Proposed Alias Mapping
| User Input | Env Var |
| :--- | :--- |
| `openai` / `open-ai` | `OPENAI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |
| `openrouter` / `open-router` | `OPENROUTER_API_KEY` |
| `gemini` / `google` | `GEMINI_API_KEY` |

## Todo List

1.  [ ] Create `src/good_agent/cli/config.py` to handle loading/saving TOML.
2.  [ ] Implement `GlobalConfig` class with `load`, `save`, `get`, `set` methods.
3.  [ ] Implement Alias Mapping logic.
4.  [ ] Add `config` command group to `src/good_agent/cli/main.py`.
5.  [ ] Add `--profile` global option to `src/good_agent/cli/main.py`.
6.  [ ] Inject config into `os.environ` in `run` and `serve` commands.
7.  [ ] Add tests for config loading, saving, and precedence logic.
