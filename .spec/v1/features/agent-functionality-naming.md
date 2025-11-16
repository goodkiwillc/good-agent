
# Semi-orchestration / pipeline

```python

agent = Agent(
    'system prompt',
    model='gpt-4',
    tools=[...]
)

@agent.route('/code-review')
async def code_review(
    agent: Agent
):

    code_review_toolkit = [
        BashTool(),
        FileReaderTool(),
        CodeAnalyzerTool(),
    ]

    with agent.context(
        system_message_suffix='''
        !# section mode type='code-review'
            Agent in code review mode.
            - Only read and analyze code.
            - Do not write or modify code.
            - You may write markdown or reference files as needed.
        !# section end
        ''',
        tools=code_review_toolkit
    ):

        agent.append(
            '''
            Analyze the codebase in your environment `{{cwd}}`.
            '''
        )

        async for message in agent.execute():
            match message:
                case Message(content=content, role=role):
                    logger.info(f'[{role}] {content}')

        await agent.call(
            'Make sure you have written any of your findings to a file called REVIEW.md'
        )

        return agent



with agent.switch('/code-review') as code_reviewer:
    pass
