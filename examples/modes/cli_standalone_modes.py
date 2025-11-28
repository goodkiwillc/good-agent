"""Standalone modes demo for CLI testing.

Run interactively: good-agent run examples/modes/cli_standalone_modes.py
Run demo: python examples/modes/cli_standalone_modes.py

Demonstrates:
- @mode() decorator for defining modes outside agents
- Registering standalone modes with agents
- Reusable mode definitions
- Using agent.console for rich CLI output
"""

import asyncio
import logging

from good_agent import Agent, tool
from good_agent.agent.modes import mode

# Suppress noisy LiteLLM logs
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Router").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Proxy").setLevel(logging.WARNING)


# =============================================================================
# STANDALONE MODE DEFINITIONS (reusable across agents)
# =============================================================================


@mode("teacher", invokable=True)
async def teacher_mode(agent: Agent):
    """Enter teacher mode for educational explanations."""
    agent.console.mode_enter("teacher", agent.mode.stack + ["teacher"])
    agent.prompt.append(
        "\n[TEACHER MODE]\n"
        "Break down concepts into simple steps.\n"
        "Use analogies and examples."
    )
    agent.mode.state["role"] = "teacher"
    agent.mode.state["concepts_explained"] = []


@mode("student", invokable=True)
async def student_mode(agent: Agent):
    """Enter student mode for learning and asking questions."""
    agent.console.mode_enter("student", agent.mode.stack + ["student"])
    agent.prompt.append(
        "\n[STUDENT MODE]\nAsk clarifying questions.\nSeek to understand deeply."
    )
    agent.mode.state["role"] = "student"
    agent.mode.state["questions_asked"] = []


@mode("tutor", invokable=True, isolation="thread")
async def tutor_mode(agent: Agent):
    """Enter tutoring mode with thread isolation."""
    agent.console.mode_enter("tutor", agent.mode.stack + ["tutor"])
    agent.console.info("Thread isolation - session isolated from main conversation")
    agent.prompt.append(
        "\n[TUTOR MODE - Thread Isolated]\n"
        "Assess the student's level.\n"
        "Provide targeted instruction."
    )
    agent.mode.state["role"] = "tutor"
    agent.mode.state["feedback_given"] = []

    yield agent

    # Cleanup
    feedback = agent.mode.state.get("feedback_given", [])
    agent.console.success(f"Tutor session ended. {len(feedback)} feedback items.")


@mode("examiner", invokable=True, isolation="fork")
async def examiner_mode(agent: Agent):
    """Enter examiner mode with fork isolation (practice tests)."""
    agent.console.mode_enter("examiner", agent.mode.stack + ["examiner"])
    agent.console.warning("Fork isolation - exam results won't persist!")
    agent.prompt.append(
        "\n[EXAMINER MODE - Fork Isolated]\n"
        "Test understanding with questions.\n"
        "This is practice - results won't persist."
    )
    agent.mode.state["role"] = "examiner"
    agent.mode.state["questions"] = []
    agent.mode.state["score"] = 0

    yield agent

    # Cleanup
    score = agent.mode.state.get("score", 0)
    questions = agent.mode.state.get("questions", [])
    total = len(questions) if questions else 1
    agent.console.success(f"Practice exam complete. Score: {score}/{total}")


# =============================================================================
# TOOLS
# =============================================================================


@tool
async def mark_concept_explained(concept: str, agent: Agent) -> str:
    """Mark a concept as explained (teacher mode).

    Args:
        concept: The concept that was explained
    """
    concepts = agent.mode.state.get("concepts_explained", [])
    concepts.append(concept)
    agent.mode.state["concepts_explained"] = concepts
    agent.console.success(f"Concept explained: {concept}")
    return f"Marked '{concept}' as explained. Total: {len(concepts)}"


@tool
async def ask_question(question: str, agent: Agent) -> str:
    """Record a question asked (student mode).

    Args:
        question: The question being asked
    """
    questions = agent.mode.state.get("questions_asked", [])
    questions.append(question)
    agent.mode.state["questions_asked"] = questions
    agent.console.info(f"Question: {question[:50]}...")
    return f"Question recorded. Total: {len(questions)}"


@tool
async def give_feedback(feedback: str, agent: Agent) -> str:
    """Give feedback to student (tutor mode).

    Args:
        feedback: The feedback to give
    """
    fb_list = agent.mode.state.get("feedback_given", [])
    fb_list.append(feedback)
    agent.mode.state["feedback_given"] = fb_list
    agent.console.info(f"Feedback: {feedback[:50]}...")
    return f"Feedback given: {feedback}"


@tool
async def record_exam_answer(question: str, correct: bool, agent: Agent) -> str:
    """Record an exam question and whether it was answered correctly.

    Args:
        question: The exam question
        correct: Whether the answer was correct
    """
    questions = agent.mode.state.get("questions", [])
    questions.append({"q": question, "correct": correct})
    agent.mode.state["questions"] = questions

    if correct:
        agent.mode.state["score"] = agent.mode.state.get("score", 0) + 1
        agent.console.success(f"Correct! ({question[:30]}...)")
    else:
        agent.console.warning(f"Incorrect ({question[:30]}...)")

    score = agent.mode.state.get("score", 0)
    return f"Recorded. Score: {score}/{len(questions)}"


@tool
async def mode_status(agent: Agent) -> str:
    """Show current mode and role status."""
    if not agent.mode.name:
        return "Not in any specialized mode."

    role = agent.mode.state.get("role", "unknown")

    stats: dict[str, str | int] = {}
    if "concepts_explained" in agent.mode.state:
        stats["Concepts"] = len(agent.mode.state["concepts_explained"])
    if "questions_asked" in agent.mode.state:
        stats["Questions"] = len(agent.mode.state["questions_asked"])
    if "feedback_given" in agent.mode.state:
        stats["Feedback"] = len(agent.mode.state["feedback_given"])
    if "score" in agent.mode.state:
        q = agent.mode.state.get("questions", [])
        stats["Score"] = f"{agent.mode.state['score']}/{len(q)}"

    agent.console.data(
        {"Mode": agent.mode.name, "Role": role, **stats}, title="Mode Status"
    )
    return f"Mode: {agent.mode.name}, Role: {role}"


@tool
async def exit_mode(agent: Agent) -> str:
    """Exit the current educational mode."""
    if not agent.mode.name:
        return "No mode to exit."

    mode_name = agent.mode.name
    agent.console.mode_exit(mode_name, agent.mode.stack[:-1])
    agent.modes.schedule_mode_exit()
    return f"Exiting {mode_name} mode."


# =============================================================================
# AGENT SETUP
# =============================================================================

# Create agent with tools
agent = Agent(
    "You are an educational assistant with multiple teaching modes:\n"
    "- 'teacher': Explain concepts clearly\n"
    "- 'student': Learn and ask questions\n"
    "- 'tutor': Personalized guidance (isolated session)\n"
    "- 'examiner': Test knowledge (practice mode)\n\n"
    "Choose the appropriate mode based on user needs.",
    model="gpt-4o",
    tools=[
        mark_concept_explained,
        ask_question,
        give_feedback,
        record_exam_answer,
        mode_status,
        exit_mode,
    ],
    name="Education Assistant",
)

# Register standalone modes with the agent
agent.modes.register(teacher_mode)
agent.modes.register(student_mode)
agent.modes.register(tutor_mode)
agent.modes.register(examiner_mode)


# =============================================================================
# DEMO
# =============================================================================

DEMO_PROMPTS = [
    "I want to learn about machine learning. Can you teach me?",
    "Mark that you explained the concept of supervised learning.",
    "Check the current mode status.",
    "Now I want to take a practice quiz on what I learned.",
    "Record that I answered the classification vs regression question correctly.",
    "Check my exam score.",
    "Exit exam mode and give me a summary of my learning session.",
]


async def run_demo(output_format: str = "rich"):
    """Run the demo with predefined prompts."""
    from _cli_utils import configure_console

    configure_console(agent, output_format)  # type: ignore[arg-type]

    async with agent:
        agent.console.section("STANDALONE MODES DEMO", style="bold cyan")
        agent.console.info(f"Agent: {agent.name}")
        agent.console.info(f"Registered modes: {agent.modes.list_modes()}")
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
                role = agent.mode.state.get("role", "unknown")
                agent.console.info(f"Mode: {agent.mode.name}, Role: {role}")

        agent.console.newline()
        agent.console.section("Demo Complete", style="bold green")


if __name__ == "__main__":
    from _cli_utils import parse_output_format

    asyncio.run(run_demo(parse_output_format()))
