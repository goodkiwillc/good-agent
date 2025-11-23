# `good-agent config`

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

Manage global configuration and profiles for Good Agent. Configuration values are stored in `~/.good-agent/config.toml`.

## Overview

The `config` command allows you to persistently store settings, such as API keys, so you don't have to set environment variables for every session. It also supports "profiles" for switching between different environments (e.g., dev, prod, personal).

!!! note "Command synopsis"
    ```bash
    good-agent config [COMMAND] [ARGS]...
    ```

## Managing Keys

Store API keys securely. The system automatically aliases common key names to their expected environment variable counterparts (e.g., `openai` -> `OPENAI_API_KEY`).

```bash
# Set API keys
good-agent config set openai sk-xxxxxx              # Sets OPENAI_API_KEY
good-agent config set anthropic sk-ant-xxxxxx       # Sets ANTHROPIC_API_KEY
good-agent config set openrouter sk-or-xxxxxx       # Sets OPENROUTER_API_KEY
good-agent config set gemini AIza-xxxxxx            # Sets GEMINI_API_KEY
```

## Profiles

Profiles allow you to group configurations.

### Setting values in a profile

Use the global `--profile` flag (available on the root command) to target a specific profile.

```bash
# Set a key in the 'dev' profile
good-agent config set openai sk-dev-key --profile dev
```

### Using a profile

When running an agent, specify the profile to load its configuration.

```bash
# Run with 'dev' profile settings
good-agent run --profile dev my_agent.py
```

### Listing configuration

View the current configuration for a profile. Secrets are masked by default.

```bash
# List default configuration
good-agent config list

# List 'dev' profile configuration
good-agent config list --profile dev

# Show secrets (use with caution)
good-agent config list --show-secrets
```

## Configuration Precedence

When an agent runs, configuration is resolved in the following order (highest priority first):

1.  **Environment Variables**: Values set in the shell (e.g., `export OPENAI_API_KEY=...`) always take precedence.
2.  **Active Profile**: Values set in the profile specified by `--profile`.
3.  **Default Configuration**: Values set in the default profile (using `config set` without `--profile`).
