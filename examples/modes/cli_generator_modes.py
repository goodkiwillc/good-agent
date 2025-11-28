"""Generator modes demo with setup/cleanup lifecycle for CLI testing.

Run interactively: good-agent run examples/modes/cli_generator_modes.py
Run demo: python examples/modes/cli_generator_modes.py

Demonstrates:
- Generator mode handlers (yield-based)
- Setup phase (before yield)
- Cleanup phase (after yield)
- Resource management patterns
- Using agent.console for rich CLI output
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from good_agent import Agent, tool

# Suppress noisy LiteLLM logs
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Router").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Proxy").setLevel(logging.WARNING)


# Simulated resource
class MockDatabase:
    """Simulated database connection for demo purposes."""

    def __init__(self, console):
        self.connected = False
        self.queries: list[str] = []
        self.console = console

    def connect(self) -> None:
        self.connected = True
        self.console.success("[DB] Connection established")

    def disconnect(self) -> None:
        query_count = len(self.queries)
        self.connected = False
        self.queries = []
        self.console.info(f"[DB] Connection closed ({query_count} queries)")

    def query(self, sql: str) -> list[dict[str, Any]]:
        if not self.connected:
            raise RuntimeError("Database not connected")
        self.queries.append(sql)
        self.console.info(f"[DB] Query: {sql[:50]}...")
        return [{"id": 1, "result": "mock_data"}]


# Shared resources (initialized per-agent)
db: MockDatabase | None = None
session_data: dict[str, Any] = {}


# Define tools
@tool
async def execute_query(query: str, agent: Agent) -> str:
    """Execute a database query (simulated).

    Args:
        query: SQL query to execute
    """
    if not agent.mode.state.get("db_connected") and not agent.mode.state.get(
        "db_available"
    ):
        agent.console.warning("Database not available")
        return "Database not available. Enter 'database' or 'analysis' mode first."

    try:
        global db
        if db:
            result = db.query(query)
            agent.mode.state["query_count"] = agent.mode.state.get("query_count", 0) + 1
            return f"Query executed successfully. Results: {result}"
        return "Database not initialized"
    except Exception as e:
        agent.console.error(f"Query failed: {e}")
        return f"Query failed: {e}"


@tool
async def track_topic(topic: str, agent: Agent) -> str:
    """Add a topic to the session tracking.

    Args:
        topic: Topic being discussed
    """
    topics = agent.mode.state.get("topics", [])
    if topic not in topics:
        topics.append(topic)
        agent.mode.state["topics"] = topics
        agent.console.info(f"Topic tracked: {topic}")
        return f"Topic '{topic}' added to tracking."
    return f"Topic '{topic}' already tracked."


@tool
async def add_finding(finding: str, agent: Agent) -> str:
    """Record an analysis finding.

    Args:
        finding: The finding to record
    """
    if agent.mode.name != "analysis":
        return "Can only add findings in analysis mode."

    findings = agent.mode.state.get("findings", [])
    findings.append({"text": finding, "timestamp": datetime.now().isoformat()})
    agent.mode.state["findings"] = findings
    agent.console.success(f"Finding: {finding[:50]}...")
    return f"Finding recorded: {finding}"


@tool
async def exit_mode(agent: Agent) -> str:
    """Exit the current mode (triggers cleanup)."""
    if not agent.mode.name:
        return "Not in any mode."

    mode_name = agent.mode.name
    agent.console.info(f"Exiting {mode_name} mode...")
    agent.modes.schedule_mode_exit()
    return f"Exiting {mode_name} mode. Cleanup will run automatically."


@tool
async def mode_info(agent: Agent) -> str:
    """Show current mode information and state."""
    if not agent.mode.name:
        return "Not in any specialized mode."

    agent.console.data(
        {
            "Mode": agent.mode.name,
            "Stack": agent.mode.stack,
            "Duration": f"{agent.mode.duration.total_seconds():.1f}s",
        },
        title="Mode Info",
    )

    state_data = {
        k: (v.isoformat() if isinstance(v, datetime) else v)
        for k, v in agent.mode.state.items()
        if not k.startswith("_")
    }
    if state_data:
        agent.console.data(state_data, title="Mode State")

    return (
        f"Mode: {agent.mode.name}, Duration: {agent.mode.duration.total_seconds():.1f}s"
    )


# Create agent
agent = Agent(
    "You are a data analyst assistant with database access. "
    "You can enter specialized modes:\n"
    "- 'database' mode: Connect to database for queries\n"
    "- 'session' mode: Track conversation metrics\n"
    "- 'analysis' mode: Perform structured analysis\n\n"
    "These modes handle setup and cleanup automatically.",
    model="gpt-4o",
    tools=[execute_query, track_topic, add_finding, exit_mode, mode_info],
    name="Data Analyst",
)


# Database mode with connection lifecycle
@agent.modes("database", invokable=True)
async def database_mode(agent: Agent):
    """Enter database mode with automatic connection management."""
    global db
    # SETUP PHASE
    agent.console.section("DATABASE MODE: Setup", style="cyan")
    db = MockDatabase(agent.console)
    db.connect()
    agent.mode.state["db_connected"] = True
    agent.mode.state["query_count"] = 0

    agent.prompt.append(
        "\n[DATABASE MODE]\n"
        "Database connection established.\n"
        "Use 'execute_query' to run queries.\n"
        "Use 'exit_mode' when done."
    )

    yield agent  # Mode is now active

    # CLEANUP PHASE
    agent.console.section("DATABASE MODE: Cleanup", style="cyan")
    query_count = agent.mode.state.get("query_count", 0)
    if db:
        db.disconnect()
    agent.console.success(f"Database mode complete. Queries: {query_count}")


# Session tracking mode
@agent.modes("session", invokable=True)
async def session_mode(agent: Agent):
    """Enter session tracking mode for conversation metrics."""
    global session_data
    # SETUP PHASE
    agent.console.section("SESSION MODE: Setup", style="magenta")
    start_time = datetime.now()
    agent.mode.state["session_start"] = start_time
    agent.mode.state["message_count"] = 0
    agent.mode.state["topics"] = []

    agent.prompt.append(
        "\n[SESSION TRACKING MODE]\n"
        "Session metrics are being tracked.\n"
        "Use 'track_topic' to log topics."
    )

    yield agent  # Mode is now active

    # CLEANUP PHASE
    agent.console.section("SESSION MODE: Cleanup", style="magenta")
    duration = datetime.now() - start_time
    topics = agent.mode.state.get("topics", [])

    agent.console.data(
        {
            "Duration": f"{duration.total_seconds():.1f}s",
            "Topics": ", ".join(topics) if topics else "none",
        },
        title="Session Summary",
    )

    session_data["last_session"] = {
        "duration_seconds": duration.total_seconds(),
        "topics": topics,
    }


# Analysis mode
@agent.modes("analysis", invokable=True)
async def analysis_mode(agent: Agent):
    """Enter analysis mode with full resource access."""
    global db
    # SETUP PHASE
    agent.console.section("ANALYSIS MODE: Setup", style="yellow")
    db = MockDatabase(agent.console)
    db.connect()
    start_time = datetime.now()

    agent.mode.state["analysis_start"] = start_time
    agent.mode.state["findings"] = []
    agent.mode.state["db_available"] = True

    agent.prompt.append(
        "\n[ANALYSIS MODE]\n"
        "Database connected. Use 'execute_query' for data.\n"
        "Use 'add_finding' to record findings."
    )

    yield agent  # Mode is now active

    # CLEANUP PHASE
    agent.console.section("ANALYSIS MODE: Cleanup", style="yellow")
    duration = datetime.now() - start_time
    findings = agent.mode.state.get("findings", [])
    if db:
        db.disconnect()

    agent.console.success(
        f"Analysis complete in {duration.total_seconds():.1f}s, {len(findings)} findings"
    )


# Demo prompts
DEMO_PROMPTS = [
    "I need to analyze some user data. Let's enter database mode.",
    "Run a query: SELECT * FROM users WHERE created_at > '2024-01-01'",
    "What's the current mode status?",
    "Exit database mode and let's start a full analysis session.",
    "Query for revenue: SELECT SUM(amount) FROM transactions",
    "Record finding: User growth is 15% month-over-month",
    "Exit analysis mode and summarize what we learned.",
]


async def run_demo(output_format: str = "rich"):
    """Run the demo with predefined prompts."""
    from _cli_utils import configure_console

    configure_console(agent, output_format)  # type: ignore[arg-type]

    async with agent:
        agent.console.section("GENERATOR MODES DEMO", style="bold cyan")
        agent.console.info(f"Agent: {agent.name}")
        agent.console.info("Demonstrating setup/cleanup lifecycle with yield")
        agent.console.rule()

        for i, prompt in enumerate(DEMO_PROMPTS, 1):
            agent.console.newline()
            agent.console.step(f"Prompt: {prompt}", step=i, total=len(DEMO_PROMPTS))
            agent.console.rule()

            response = await agent.call(prompt)

            agent.console.panel(
                str(response.content),
                title="Assistant Response",
                style="green",
                markdown=True,
            )

            if agent.mode.name:
                agent.console.info(f"Mode: {agent.mode.name}")

        agent.console.newline()
        agent.console.section("Demo Complete", style="bold green")
        if session_data:
            agent.console.data(session_data, title="Session Data Captured")


if __name__ == "__main__":
    from _cli_utils import parse_output_format

    asyncio.run(run_demo(parse_output_format()))
