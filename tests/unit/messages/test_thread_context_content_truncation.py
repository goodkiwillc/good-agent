import pytest
from good_agent import Agent, tool
from good_agent.content.parts import TextContentPart
from good_agent.messages import AssistantMessage


class TestThreadContextContentTruncation:
    """Test ThreadContext with message content truncation/condensing."""

    @pytest.mark.asyncio
    async def test_thread_context_truncates_message_content(self):
        """Test replacing verbose messages with condensed versions in ThreadContext."""
        agent = Agent("You are a helpful assistant")
        await agent.ready()

        # Build conversation with verbose content
        agent.append("Search for information about Python")

        # Add a verbose assistant response (simulating tool output)
        verbose_response = """I found extensive information about Python:
        
        Python is a high-level, interpreted programming language known for its simplicity 
        and readability. It was created by Guido van Rossum and first released in 1991.
        
        Key Features:
        - Dynamic typing and automatic memory management
        - Extensive standard library
        - Support for multiple programming paradigms
        - Cross-platform compatibility
        - Large ecosystem of third-party packages
        
        Popular Use Cases:
        1. Web Development (Django, Flask, FastAPI)
        2. Data Science and Machine Learning (NumPy, Pandas, Scikit-learn, TensorFlow)
        3. Automation and Scripting
        4. Scientific Computing
        5. Game Development
        
        ... [10 more paragraphs of detailed information] ...
        
        Total results: 1,247 articles found across 50 sources."""

        agent.append(verbose_response, role="assistant")
        agent.append("Can you give me more specific information about web frameworks?")

        # Capture original messages
        [msg for msg in agent.messages]
        original_verbose_content = str(agent.messages[2])  # The verbose response

        # Use ThreadContext to work with condensed versions
        async with agent.context_manager.thread_context() as ctx:
            # Replace verbose message with condensed version
            # This simulates what an agent might do to save context window space
            condensed_msg = AssistantMessage(
                content_parts=[
                    TextContentPart(
                        text="[CONDENSED] Found 1,247 articles about Python covering: "
                        "features, use cases (web, data science, automation), "
                        "and ecosystem. Key points: interpreted, readable, extensive libraries."
                    )
                ]
            )

            # Replace the verbose message
            ctx.messages[2] = condensed_msg

            # Verify replacement in context
            assert "[CONDENSED]" in str(ctx.messages[2])
            assert len(str(ctx.messages[2])) < len(original_verbose_content)

            # Add new messages with condensed context
            # The LLM would see the condensed version, saving tokens
            ctx.append(
                "Based on the condensed context, tell me about Flask specifically"
            )
            ctx.append(
                "Flask is a lightweight Python web framework...", role="assistant"
            )

            # Context has condensed version + new messages
            assert len(ctx.messages) == 6  # system + user + condensed + user + 2 new

        # After context: original verbose message is restored
        assert len(agent.messages) == 6  # originals + 2 new

        # Original verbose message is intact
        assert str(agent.messages[2]) == original_verbose_content
        assert "10 more paragraphs" in str(agent.messages[2])

        # New messages were added
        assert "Flask specifically" in str(agent.messages[4])
        assert "Flask is a lightweight" in str(agent.messages[5])

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_thread_context_condense_multiple_tool_responses(self):
        """Test condensing multiple tool responses to save context."""

        @tool
        def search_web(query: str) -> str:
            """Search the web for information."""
            # Simulate verbose tool response
            return f"""
            Searching for: {query}
            
            Result 1: [500 words of content about {query}]
            Result 2: [500 words of content about {query}]
            Result 3: [500 words of content about {query}]
            ... 
            Total: 25 results from 10 sources
            Processing time: 2.3 seconds
            Confidence: 0.95
            """

        agent = Agent("You are a research assistant", tools=[search_web])
        await agent.ready()

        # Simulate multiple tool calls with verbose responses
        agent.append("Search for machine learning basics")

        # Manually add tool response (simulating what execute would do)
        tool_response_1 = await agent.tool_calls.invoke(
            "search_web", query="machine learning basics"
        )
        agent.append(str(tool_response_1), role="assistant")

        agent.append("Now search for neural networks")
        tool_response_2 = await agent.tool_calls.invoke("search_web", query="neural networks")
        agent.append(str(tool_response_2), role="assistant")

        agent.append("Finally, search for deep learning")
        tool_response_3 = await agent.tool_calls.invoke("search_web", query="deep learning")
        agent.append(str(tool_response_3), role="assistant")

        # Original messages are verbose
        original_total_length = sum(len(str(msg)) for msg in agent.messages)

        # Use ThreadContext to condense tool responses
        async with agent.context_manager.thread_context() as ctx:
            # Find and replace tool responses with condensed versions
            for i, msg in enumerate(ctx.messages):
                if isinstance(msg, AssistantMessage) and "Result 1:" in str(msg):
                    # Extract key info and condense
                    str(msg)

                    # Create condensed version
                    condensed = AssistantMessage(
                        content_parts=[
                            TextContentPart(
                                text="[CONDENSED SEARCH] 25 results found, high confidence"
                            )
                        ]
                    )
                    ctx.messages[i] = condensed

            # Verify condensing worked
            condensed_total_length = sum(len(str(msg)) for msg in ctx.messages)
            assert condensed_total_length < original_total_length

            # Add synthesis based on condensed context
            ctx.append("Based on all searches, provide a summary")
            ctx.append(
                "Summary: ML basics -> Neural Networks -> Deep Learning progression",
                role="assistant",
            )

        # After context: original verbose responses restored
        final_total_length = sum(len(str(msg)) for msg in agent.messages[:-2])
        assert final_total_length >= original_total_length  # Originals preserved

        # New summary messages added
        assert "provide a summary" in str(agent.messages[-2])
        assert "ML basics -> Neural Networks" in str(agent.messages[-1])

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_fork_context_with_aggressive_truncation(self):
        """Test using ForkContext for aggressive truncation without affecting original."""
        agent = Agent()
        await agent.ready()

        # Build a conversation with mixed content
        agent.append("Tell me about the history of computing")

        # Long historical response
        agent.append(
            """
        The history of computing spans several millennia, from ancient counting devices
        to modern quantum computers. Key milestones include:
        
        [5000 words of detailed history including:]
        - Abacus (2700 BCE)
        - Antikythera mechanism (100 BCE)
        - Charles Babbage's Analytical Engine (1837)
        - Alan Turing's theoretical work (1936)
        - ENIAC (1945)
        - Transistor invention (1947)
        - Integrated circuits (1958)
        - Personal computers (1970s)
        - Internet (1969-1990s)
        - Smartphones (2007)
        - Quantum computing (2019)
        
        [Detailed descriptions of each era...]
        """,
            role="assistant",
        )

        agent.append("What about modern AI?")
        agent.append("[2000 words about modern AI...]", role="assistant")

        original_messages = list(agent.messages)

        # Use ForkContext for aggressive truncation
        async with agent.context_manager.fork_context() as fork:
            # In fork, replace everything with bullet points
            for i, msg in enumerate(fork.messages):
                if isinstance(msg, AssistantMessage):
                    # Aggressively truncate to bullet points
                    content = str(msg)
                    if "history of computing" in content:
                        fork.messages[i] = AssistantMessage(
                            content_parts=[
                                TextContentPart(
                                    text="• Computing: Abacus→Babbage→Turing→ENIAC→PC→Internet→Quantum"
                                )
                            ]
                        )
                    elif "modern AI" in content:
                        fork.messages[i] = AssistantMessage(
                            content_parts=[
                                TextContentPart(
                                    text="• AI: Neural nets→Deep learning→Transformers→GPT→AGI research"
                                )
                            ]
                        )

            # Work with ultra-condensed version in fork
            fork.append("Based on this timeline, what's next?")
            fork.append(
                "• Next: Quantum AI, neuromorphic computing, AGI", role="assistant"
            )

            # Fork has condensed conversation
            sum(len(str(msg)) for msg in fork.messages)

        # Original is completely unchanged - still has full verbose history
        assert len(agent.messages) == len(original_messages)
        for i, msg in enumerate(original_messages):
            assert agent.messages[i].id == msg.id
            assert str(agent.messages[i]) == str(msg)

        # Original retains all verbose content
        assert "5000 words" in str(agent.messages[1])
        assert "2000 words" in str(agent.messages[3])

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_nested_contexts_with_progressive_truncation(self):
        """Test nested contexts with progressive levels of truncation."""
        agent = Agent()
        await agent.ready()

        # Original verbose message
        agent.append("Explain quantum computing")
        agent.append(
            "Quantum computing is... [10,000 character explanation]", role="assistant"
        )

        original_response = str(agent.messages[1])

        # First level context - moderate truncation
        async with agent.context_manager.thread_context() as ctx1:
            # Moderately condense
            ctx1.messages[1] = AssistantMessage(
                content_parts=[
                    TextContentPart(
                        text="Quantum computing uses qubits for parallel computation. "
                        "[1,000 character summary]"
                    )
                ]
            )

            moderate_length = len(str(ctx1.messages[1]))

            # Nested context - aggressive truncation
            async with ctx1.thread_context() as ctx2:
                # Aggressively condense
                ctx2.messages[1] = AssistantMessage(
                    content_parts=[
                        TextContentPart(text="QC: qubits enable exponential speedup")
                    ]
                )

                len(str(ctx2.messages[1]))

                # Work with ultra-condensed version
                ctx2.append("Applications?")
                ctx2.append("Crypto, drug discovery, optimization", role="assistant")

            # Back in ctx1 - has moderate version + nested additions
            assert len(str(ctx1.messages[1])) == moderate_length
            assert "1,000 character summary" in str(ctx1.messages[1])
            assert "Applications?" in str(ctx1.messages[-2])

        # Back in main - has original verbose version + additions
        assert str(agent.messages[1]) == original_response
        assert "10,000 character explanation" in str(agent.messages[1])
        assert "Applications?" in str(agent.messages[-2])
        assert "Crypto, drug discovery" in str(agent.messages[-1])

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_revert_after_truncation(self):
        """Test that reverting versions works correctly with truncated messages."""
        agent = Agent()
        await agent.ready()

        # Build conversation
        agent.append("Question 1")
        agent.append("Verbose answer 1 with lots of details...", role="assistant")
        version_after_q1 = agent._version_manager.version_count

        agent.append("Question 2")
        agent.append("Verbose answer 2 with even more details...", role="assistant")

        # Use context to work with truncated versions
        async with agent.context_manager.thread_context() as ctx:
            # Truncate both answers
            ctx.messages[1] = AssistantMessage(
                content_parts=[TextContentPart(text="[A1-condensed]")]
            )
            ctx.messages[3] = AssistantMessage(
                content_parts=[TextContentPart(text="[A2-condensed]")]
            )

            # Add based on condensed context
            ctx.append("Question 3 based on condensed context")
            ctx.append("[A3]", role="assistant")

        # Messages include additions
        assert len(agent.messages) == 6

        # Revert to state after Q1 (should have verbose, not condensed)
        agent.revert_to_version(version_after_q1 - 1)

        # Should have original verbose answer, not condensed version
        assert len(agent.messages) == 2
        assert "Verbose answer 1 with lots of details" in str(agent.messages[1])
        assert "[A1-condensed]" not in str(agent.messages[1])

        await agent.events.async_close()
