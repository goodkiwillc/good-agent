# Built-In Agents

Good Agent ships with two reference agents you can launch immediately. They double as living examples of how to wire tools, prompts, and configuration.

## `good-agent-agent`

Purpose: act as a documentation concierge that can browse local docs and scaffold new agents.

- **Prompt summary**: a helper that answers Good Agent questions and creates boilerplate agents on demand.
- **Tools**:
  - `create_agent_file(name, system_prompt, file_path)` – generates a Python file from a template.
  - `read_documentation_file(relative_path)` – reads files under `docs/`.
  - `list_documentation_files()` – enumerates documentation assets.
- **Default model**: `gpt-4o`.

Usage examples:

```bash
good-agent run good-agent
```

```python
from good_agent.agents.meta import agent as good_agent_agent
```

## `research-agent`

Purpose: perform lightweight web research with simple search and scraping helpers.

- **Prompt summary**: gather facts from the web, cite URLs in answers.
- **Tools**:
  - `search_web(query)` – DuckDuckGo text search (via `duckduckgo-search`).
  - `visit_page(url)` – fetch and clean page text with `httpx` + `beautifulsoup4`.
- **Default model**: `gpt-4o`.

!!! warning "Optional dependencies"
    Install `duckduckgo-search`, `httpx`, and `beautifulsoup4` to unlock the web tools:
    ```bash
    pip install duckduckgo-search httpx beautifulsoup4
    ```

Usage examples:

```bash
good-agent run research "latest llm advances"
```

```python
from good_agent.agents.research import agent as research_agent
```

## CLI alias reference

| Alias | Expands to |
| ----- | ---------- |
| `good-agent` | `good_agent.agents.meta:agent` |
| `good-agent-agent` | `good_agent.agents.meta:agent` |
| `research` | `good_agent.agents.research:agent` |
| `research-agent` | `good_agent.agents.research:agent` |

Use these aliases with [`good-agent run`](../cli/run.md) to explore without writing import strings.
