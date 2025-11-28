


Agent:

  - execute()
    - resolve_pending_tool_calls()

    - call_llm()

    - resolve_pending_tool_calls()

        -> call "switch_mode":

            -> enter "mode":

                : configuration | prompt changes

                    tool invocations

                    direct llm calls (i.e. `call()`)

        <----------- yield

    - call_llm()

    - resolve_pending_tool_calls() - this would be based on the available tools from the "entered context

                     mode function has control again

                : run cleanup tasks, tool calls, etc

            <-- exit "mode"
