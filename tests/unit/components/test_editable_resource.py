"""
Tests for EditableResource class.

Following TDD Red/Green/Refactor process.
"""

import pytest
from good_agent import Agent


class TestEditableResource:
    """Test suite for EditableResource class."""

    @pytest.mark.asyncio
    async def test_editable_resource_exists(self):
        """Test that EditableResource class exists and is importable."""
        from good_agent.resources import EditableResource

        assert EditableResource is not None

    @pytest.mark.asyncio
    async def test_editable_resource_inherits_from_stateful(self):
        """Test that EditableResource inherits from StatefulResource."""
        from good_agent.resources import EditableResource, StatefulResource

        assert issubclass(EditableResource, StatefulResource)

    @pytest.mark.asyncio
    async def test_editable_resource_initialization(self):
        """Test EditableResource can be initialized with content and name."""
        from good_agent.resources import EditableResource

        resource = EditableResource(content="Hello world", name="test_doc")

        assert resource.name == "test_doc"
        assert resource._initial_content == "Hello world"
        assert resource._modified is False

    @pytest.mark.asyncio
    async def test_editable_resource_initialize_sets_state(self):
        """Test that initialize() sets the state to initial content."""
        from good_agent.resources import EditableResource

        resource = EditableResource("Initial content", name="doc")
        await resource.initialize()

        assert resource.state == "Initial content"

    @pytest.mark.asyncio
    async def test_editable_resource_persist_clears_modified_flag(self):
        """Test that persist() clears the modified flag."""
        from good_agent.resources import EditableResource

        resource = EditableResource("Content", name="doc")
        await resource.initialize()
        resource._modified = True

        await resource.persist()

        assert resource._modified is False

    @pytest.mark.asyncio
    async def test_editable_resource_provides_basic_tools(self):
        """Test that EditableResource provides basic editing tools."""
        from good_agent.resources import EditableResource

        resource = EditableResource("Content", name="doc")
        tools = resource.get_tools()

        # Should provide basic editing tools
        assert "read" in tools
        assert "replace" in tools
        assert "edit_line" in tools
        assert "insert" in tools
        assert "save" in tools

    @pytest.mark.asyncio
    async def test_read_tool_works(self):
        """Test that the read tool returns content with line numbers."""
        from good_agent.resources import EditableResource

        content = "Line 1\nLine 2\nLine 3"
        resource = EditableResource(content, name="doc")
        await resource.initialize()

        tools = resource.get_tools()
        read_tool = tools["read"]

        # Read all lines
        result = await read_tool()
        assert "   1: Line 1" in result.response
        assert "   2: Line 2" in result.response
        assert "   3: Line 3" in result.response

        # Read with start_line
        result = await read_tool(start_line=2)
        assert "Line 1" not in result.response
        assert "   2: Line 2" in result.response
        assert "   3: Line 3" in result.response

        # Read with start_line and num_lines
        result = await read_tool(start_line=2, num_lines=1)
        assert "Line 1" not in result.response
        assert "   2: Line 2" in result.response
        assert "Line 3" not in result.response

    @pytest.mark.asyncio
    async def test_replace_tool_works(self):
        """Test that the replace tool modifies content."""
        from good_agent.resources import EditableResource

        resource = EditableResource("Hello world", name="doc")
        await resource.initialize()

        tools = resource.get_tools()
        replace_tool = tools["replace"]

        # Single replacement
        result = await replace_tool(old_text="world", new_text="universe")
        assert "Replaced 1 occurrence(s)" in result.response
        assert resource.state == "Hello universe"
        assert resource._modified is True

        # No match
        resource._modified = False
        result = await replace_tool(old_text="galaxy", new_text="cosmos")
        assert "No matches found" in result.response
        assert resource._modified is False

        # Replace all occurrences
        resource.state = "foo bar foo baz foo"
        result = await replace_tool(
            old_text="foo", new_text="qux", all_occurrences=True
        )
        assert "Replaced 3 occurrence(s)" in result.response
        assert resource.state == "qux bar qux baz qux"

    @pytest.mark.asyncio
    async def test_edit_line_tool_works(self):
        """Test that edit_line tool modifies specific lines."""
        from good_agent.resources import EditableResource

        content = "Line 1\nLine 2\nLine 3"
        resource = EditableResource(content, name="doc")
        await resource.initialize()

        tools = resource.get_tools()
        edit_tool = tools["edit_line"]

        # Edit valid line
        result = await edit_tool(line_number=2, new_content="Modified Line 2")
        assert "Updated line 2" in result.response
        assert resource.state == "Line 1\nModified Line 2\nLine 3"
        assert resource._modified is True

        # Invalid line number (too high)
        result = await edit_tool(line_number=10, new_content="Invalid")
        assert "Invalid line number: 10" in result.response

        # Invalid line number (too low)
        result = await edit_tool(line_number=0, new_content="Invalid")
        assert "Invalid line number: 0" in result.response

    @pytest.mark.asyncio
    async def test_insert_tool_works(self):
        """Test that insert tool adds content after specified line."""
        from good_agent.resources import EditableResource

        content = "Line 1\nLine 2\nLine 3"
        resource = EditableResource(content, name="doc")
        await resource.initialize()

        tools = resource.get_tools()
        insert_tool = tools["insert"]

        # Insert after line 1
        result = await insert_tool(after_line=1, content="New Line")
        assert "Inserted 1 line(s)" in result.response
        assert resource.state == "Line 1\nNew Line\nLine 2\nLine 3"
        assert resource._modified is True

        # Insert at beginning (after line 0)
        resource.state = "Line 1\nLine 2"
        result = await insert_tool(after_line=0, content="First Line")
        assert "Inserted 1 line(s)" in result.response
        assert resource.state == "First Line\nLine 1\nLine 2"

        # Insert multiple lines
        result = await insert_tool(after_line=1, content="A\nB\nC")
        assert "Inserted 3 line(s)" in result.response
        lines = resource.state.split("\n")
        assert lines[0] == "First Line"
        assert lines[1] == "A"
        assert lines[2] == "B"
        assert lines[3] == "C"

        # Invalid line number
        result = await insert_tool(after_line=-1, content="Invalid")
        assert "Invalid line number: -1" in result.response

    @pytest.mark.asyncio
    async def test_save_tool_persists_and_signals_exit(self):
        """Test that save tool calls persist."""
        from good_agent.resources import EditableResource

        resource = EditableResource("Content", name="doc")
        await resource.initialize()
        resource._modified = True

        tools = resource.get_tools()
        save_tool = tools["save"]

        result = await save_tool()
        assert "Saved doc" in result.response
        assert resource._modified is False

    @pytest.mark.asyncio
    async def test_editable_resource_with_agent_integration(self):
        """Test EditableResource integration with Agent."""
        from good_agent.resources import EditableResource

        resource = EditableResource("Hello world", name="doc")

        async with Agent("Test editor") as agent:
            # Original tools
            original_tool_count = len(agent.tools)

            async with resource(agent):
                # Should have editing tools
                assert "read" in agent.tools
                assert "replace" in agent.tools
                assert "save" in agent.tools

                # Test using a tool
                replace_tool = agent.tools["replace"]
                result = await replace_tool(
                    _agent=agent, old_text="world", new_text="universe"
                )
                assert result.response == "Replaced 1 occurrence(s)"
                assert resource.state == "Hello universe"

            # Tools should be restored
            assert len(agent.tools) == original_tool_count

    @pytest.mark.asyncio
    async def test_editable_resource_default_name(self):
        """Test that EditableResource has a default name."""
        from good_agent.resources import EditableResource

        # Without specifying name
        resource = EditableResource("Content")
        assert resource.name == "document"
