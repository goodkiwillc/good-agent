No, the LLMCoordinator does not actually support streaming responses, despite what the
docstring claims.

Current state:

1. LLMCoordinator: The docstring says it handles "streaming" but the only method
    (llm_call) doesn't implement it - it always calls model.complete() with no streaming
    and waits for the full response.

2. Streaming exists at the model layer: LanguageModel has a stream() method that delegates
    to StreamingHandler for token-by-token streaming, but this isn't exposed through
    LLMCoordinator.

3. Agent-level streaming is incomplete:
    •  Agent.execute() has a streaming parameter that's never actually used
    •  Agent.chat() has a stream parameter but raises NotImplementedError

How to use streaming today:

You'd need to bypass LLMCoordinator and call the model directly:

python
    async for chunk in agent.model.stream(messages):
        if chunk.content:
            print(chunk.content, end='', flush=True)

Should the docstring be fixed? The LLMCoordinator docstring is misleading and should
either be updated to remove "streaming" or the class should implement streaming methods.
