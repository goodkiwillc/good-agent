from pathlib import Path

from good_agent.agent.core import Agent
from good_agent.tools import tool

# Template for new agents
AGENT_TEMPLATE = """from good_agent import Agent

agent = Agent(
    \"\"\"
{system_prompt}
\"\"\",
    name="{name}",
    model="gpt-4o",
)
"""


@tool
def create_agent_file(name: str, system_prompt: str, file_path: str) -> str:
    """
    Creates a new agent file with the given name and system prompt.

    Args:
        name: The name of the agent.
        system_prompt: The system prompt for the agent.
        file_path: The path where the agent file should be saved (e.g., 'my_agent.py').
    """
    content = AGENT_TEMPLATE.format(name=name, system_prompt=system_prompt)
    path = Path(file_path)

    if path.exists():
        return f"Error: File {file_path} already exists."

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return f"Successfully created agent '{name}' at {file_path}."


@tool
def read_documentation_file(relative_path: str) -> str:
    """
    Reads a documentation file from the project's docs directory.

    Args:
        relative_path: The path relative to the 'docs' directory (e.g., 'getting-started/index.md').
    """
    # This assumes the agent is running from the project root
    docs_root = Path("docs")
    if not docs_root.exists():
        return "Error: 'docs' directory not found in current working directory."

    file_path = docs_root / relative_path

    # specialized handling for listing files
    if not file_path.suffix and file_path.exists() and file_path.is_dir():
        return "\n".join(
            [str(p.relative_to(docs_root)) for p in file_path.rglob("*") if p.is_file()]
        )

    if not file_path.exists():
        return f"Error: File {relative_path} not found in docs directory."

    return file_path.read_text()


@tool
def list_documentation_files() -> str:
    """
    Lists all files in the 'docs' directory.
    """
    docs_root = Path("docs")
    if not docs_root.exists():
        return "Error: 'docs' directory not found."

    files = [str(p.relative_to(docs_root)) for p in docs_root.rglob("*") if p.is_file()]
    return "\n".join(files)


agent = Agent(
    """
    You are the 'good-agent-agent', a helpful assistant for the Good Agent library.
    Your goal is to help users understand how to use Good Agent and to help them generate new agents.

    You have access to the Good Agent documentation via the `read_documentation_file` and `list_documentation_files` tools.
    You can also create new agent files using the `create_agent_file` tool.

    When asked to create an agent, ask for the agent's name and what it should do, then draft a system prompt and creating the file.
    If the user asks about Good Agent features, look up the documentation.
    """,
    name="good-agent-agent",
    model="gpt-4o",  # Or whatever default model
    tools=[create_agent_file, read_documentation_file, list_documentation_files],
)
