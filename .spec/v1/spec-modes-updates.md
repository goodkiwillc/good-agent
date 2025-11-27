Make a plan for improving the "agent modes" feature

Task 1: review the current implementation and documentation, as well as original spec docs in .spec/v1/features

New Feature #1: agent-invoked mode switching - right now, modes must be declaratively invoked

I want the agent to be able to switch between modes (as well as stack modes that are stackable) on its own. we should explore a few different ways of doing this. the easiest would be via tool calls, but it might also be worth exploring some kind of text based shortcode or prompt insert that could be used to trigger a mode.

We need to think carefully through the control flow and design of modes. Let's review what modes are supposed to be:
- functionally defined configuration overrides that can change agent configuration, prompt history, available tools, etc
- maintain some degree of state isolation (it is unclear how this is currently implemented and how it works vs the fork_context, thread_context, config and context methods )
- the original idea (which seems to have gotten lost in at least in the documentation if not the implementation itself) was that a mode could also orchestrate specific actions like modifying or replacing the system prompt, run specific prompt calls, make declarative tool invocations -- then yield control back to the parent agent process (which is either the root agent or another mode), so that this behavior could be "stacked" on top of one another.

For example:

```python

agent = Agent()

@agent.modes('planning')
async def planning_mode(agent: Agent):
    # we need to clean up the api for manipulating the system prompt with clear semantics for prepend/append/replace/etc
    agent.set_system_prompt_suffix(
        'Additional instructions for this mode'
    )

    # declaratively invoke tool (name alias)
    await agent.invoke('list_research_resources')

    # note - the tool_choice parameter working with Tool instances like this is not yet implemented - but just for illustration
    await agent.call('make a research plan and create a todo list', tool_choice=agent[TaskManager].create)

    # yield control back while maintaining configuration overrides
    yield agent

    # forces model to call the todo list update tool
    await agent.call(tool_choice=agent[TaskManager].update)


```

### State Isolation

We need to come up with a consistent design to how we do state isolation in the agent library. we have various different methods for temporarily overring certain configuration parameters via thread_context, fork_context, context and config (do we need to unify any of those? how are they different?)

In the case of modes, right now we have it set up that the agent is passed through (note: some documentation still says that modes should get "AgentContext" or "ModeContext" - but the mode decorated function should work like any other tool or dependency-injection supported function where we can inject the Agent instance or other Context() supported parameters like AgentComponents)

Do we want automatic state isolation in agent modes? fork_context creates a completely isolated copy of the prior agent state while thread_context can temporarily modify the conversation history before returning to the original state after the context manager.

How do we want modes to work? perhaps there should be a default and then a parameter that can be set in the decorator itself - i.e. `agent.modes('researcher', isolated=True)` or something

How will state isolation work with stacked modes? because the mode can yield the agent object back to the parent with all its overrides in place, it means that at least inherent to the design there's no reason why you couldn't stack modes on top of each other for interesting functionality. How would state isolation work in this use case? we'd probably need pretty strict rules about state inheritence or we'd need to make it configurable.

Remember the main goals of modes are:
 - Provide a different set of tools, model selection or configuration, system prompt (or system prompt edits)
 - Declaratively orchestrate specific llm calls, tool invocations or prompts either before or after the agent takes actions (for instance, mandate a review step or mandage that a coding agent run a test suite after its made a bunch of file edits)
 - State and context isolation - with an isolated thread history, the mode could be free to truncate or summarize the context up into that point - or at the end of the mode context, it could decide to only keep the final assistant message and remove token-expensive content like tool call responses


Open Questions:
 - How does behavior differ between declarative invocation of mode `async with agent.modes['mode-name']` vs agent-invoked. Say we use the tool-call based switching - when a agent calls the "enter_mode/select_mode" tool with the relevant name, does it just run that function (and whatever invocations follow)? Do we also want it to be able to call with specific instructions or parameters? Or perhaps that's a different thing - for instance, you could combine normal tools and modes so that you could have a tool, with the agent injected into the tool function, with a particular mode preselect (for instance it could be a cheaper model and it could do some truncation of prior context) - but then that tool also receives a prompt from the main agent branch - but the actual tool invocation has the prior context, for instance:


 ```python

@tool
async def person_researcher(
    instructions: str,
    agent: Agent = Context(mode='person_researcher')
):
    async with agent.config(
        tools=[web_search, social_search]
    ):
        return agent.call(instructions)



agent = Agent(tools=[person_researcher])

@agent.modes('person_researcher')
async def person_researcher_mode(agent: Agent):

    async with agent.thread_context(
        truncate_tool_calls=True
    ):

        agent.replace_system_prompt(
            'You are a person researcher agent - you are also provided'
            'the previous context of the agent that calls you so you have their context'
        )

        yield agent


```

Ok this example raised another question - can modes be defined outside of a specifc agent instance? In this case here we have a problem in that typically modes have been defined via @agent.modes decorator - but we have a little bit of a potential order of operation issue (although not necessarily) in that the tool is referencing a mode that isn't registered yet. do we need to be able to define modes independently from agents (like we do tools)?
