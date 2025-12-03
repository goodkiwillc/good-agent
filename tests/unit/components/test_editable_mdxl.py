import pytest
from good_agent import Agent


class TestEditableMDXL:
    """Test suite for enhanced EditableMDXL."""

    @pytest.mark.asyncio
    async def test_available_tools(self):
        """Test that we have all the expected tools."""
        from good_agent.core.mdxl import MDXL
        from good_agent.resources.editable_mdxl import EditableMDXL

        mdxl = MDXL("<doc><title>Test</title></doc>")
        resource = EditableMDXL(mdxl)

        tools = resource.get_tools()

        # Should have these tools
        expected_tools = {
            "read",
            "update",
            "replace_text",
            "insert",  # Unified insert tool replaces insert_before/insert_after
            "append_child",
            "delete",
            # "move" tool has been removed
        }
        # Tools are now a list, extract names
        tool_names = {tool.name for tool in tools}
        assert tool_names == expected_tools

    @pytest.mark.asyncio
    async def test_read_filters_content(self):
        """Test that read shows the entire document filtered for LLM."""
        from good_agent.core.mdxl import MDXL
        from good_agent.resources.editable_mdxl import EditableMDXL

        # Document with private elements and references
        mdxl = MDXL("""
        <doc>
            <title>Public Title</title>
            <content>Public content that LLM should see</content>
            <private>Secret info LLM should not see</private>
            <note private="true">Another private note</note>
            <references>
                <ref>Some reference</ref>
            </references>
            <citations>
                <citation>A citation</citation>
            </citations>
        </doc>
        """)

        resource = EditableMDXL(mdxl)
        await resource.initialize()

        tools = resource.get_tools()
        read_tool = next(tool for tool in tools if tool.name == "read")
        result = await read_tool()

        # Extract the response string from ToolResponse
        content = result.response if hasattr(result, "response") else str(result)

        # Should show public content
        assert "Public Title" in content
        assert "Public content that LLM should see" in content

        # Should NOT show private, references, or citations
        assert "Secret info" not in content
        assert "Another private note" not in content
        assert "Some reference" not in content
        assert "A citation" not in content

    @pytest.mark.asyncio
    async def test_xpath_cleanup(self):
        """Test that XPath selectors are cleaned up properly."""
        from good_agent.core.mdxl import MDXL
        from good_agent.resources.editable_mdxl import EditableMDXL

        mdxl = MDXL("""
        <doc>
            <person name="John">John Doe</person>
        </doc>
        """)

        resource = EditableMDXL(mdxl)
        await resource.initialize()

        # Test /text() removal
        cleaned = resource._clean_xpath("//person/text()")
        assert cleaned == "//person"

        # Test local-name() simplification - also converts / to //
        cleaned = resource._clean_xpath("/*[local-name()='person']")
        assert cleaned == "//person"

    @pytest.mark.asyncio
    async def test_update_text_content(self):
        """Test updating text content of elements."""
        from good_agent.core.mdxl import MDXL
        from good_agent.resources.editable_mdxl import EditableMDXL

        mdxl = MDXL("""
        <doc>
            <title>Original Title</title>
            <content>Original content</content>
        </doc>
        """)

        resource = EditableMDXL(mdxl)
        await resource.initialize()

        tools = resource.get_tools()
        update_tool = next(tool for tool in tools if tool.name == "update")

        # Update title using // syntax
        result = await update_tool(xpath="//title", text_content="New Title")
        response = result.response if hasattr(result, "response") else str(result)
        assert "Updated text content at //title" in response

        # Verify change persisted
        assert "New Title" in resource.state.outer
        assert "Original Title" not in resource.state.outer

    @pytest.mark.asyncio
    async def test_update_attributes_dict(self):
        """Test updating element attributes with dict format."""
        from good_agent.core.mdxl import MDXL
        from good_agent.resources.editable_mdxl import EditableMDXL

        mdxl = MDXL("""
        <doc>
            <section id="intro" class="normal">
                <content>Test content</content>
            </section>
        </doc>
        """)

        resource = EditableMDXL(mdxl)
        await resource.initialize()

        tools = resource.get_tools()
        update_tool = next(tool for tool in tools if tool.name == "update")

        # Update using dict format
        result = await update_tool(
            xpath="//section", attributes={"class": "important", "priority": "high"}
        )

        response = result.response if hasattr(result, "response") else str(result)
        assert "set class='important'" in response
        assert "set priority='high'" in response

        # Verify in state
        state_xml = resource.state.outer
        assert 'class="important"' in state_xml
        assert 'priority="high"' in state_xml

        # Remove an attribute (None value)
        result = await update_tool(xpath="//section", attributes={"priority": None})
        response = result.response if hasattr(result, "response") else str(result)
        assert "removed 'priority'" in response
        assert "priority=" not in resource.state.outer

    @pytest.mark.asyncio
    async def test_replace_text(self):
        """Test replacing text within elements."""
        from good_agent.core.mdxl import MDXL
        from good_agent.resources.editable_mdxl import EditableMDXL

        mdxl = MDXL("""
        <doc>
            <content>The quick brown fox jumps over the lazy dog.</content>
        </doc>
        """)

        resource = EditableMDXL(mdxl)
        await resource.initialize()

        tools = resource.get_tools()
        replace_tool = next(tool for tool in tools if tool.name == "replace_text")

        # Replace single occurrence
        result = await replace_tool(xpath="//content", old_text="brown", new_text="red")
        response = result.response if hasattr(result, "response") else str(result)
        assert "Replaced 1 occurrence(s)" in response
        assert "red fox" in resource.state.outer
        assert "brown fox" not in resource.state.outer

        # Test replacing all occurrences
        mdxl2 = MDXL("<doc><text>foo bar foo baz foo</text></doc>")
        resource2 = EditableMDXL(mdxl2)
        await resource2.initialize()
        tools2 = resource2.get_tools()
        replace_tool2 = next(tool for tool in tools2 if tool.name == "replace_text")

        result = await replace_tool2(
            xpath="//text", old_text="foo", new_text="qux", all_occurrences=True
        )
        response = result.response if hasattr(result, "response") else str(result)
        assert "Replaced 3 occurrence(s)" in response
        assert resource2.state.outer.count("qux") == 3
        assert "foo" not in resource2.state.outer

    @pytest.mark.asyncio
    async def test_insert_after(self):
        """Test inserting elements after a reference."""
        from good_agent.core.mdxl import MDXL
        from good_agent.resources.editable_mdxl import EditableMDXL

        mdxl = MDXL("""
        <doc>
            <item id="1">First</item>
            <item id="3">Third</item>
        </doc>
        """)

        resource = EditableMDXL(mdxl)
        await resource.initialize()

        tools = resource.get_tools()
        insert_tool = next(tool for tool in tools if tool.name == "insert")

        # Insert after first item
        result = await insert_tool(
            reference_xpath="//item[@id='1']",
            element_tag="item",
            position="after",
            text_content="Second",
            attributes={"id": "2"},
        )
        response = result.response if hasattr(result, "response") else str(result)
        assert "Inserted <item> after" in response

        # Verify order
        content = resource.state.outer
        first_pos = content.index("First")
        second_pos = content.index("Second")
        third_pos = content.index("Third")
        assert first_pos < second_pos < third_pos

    @pytest.mark.asyncio
    async def test_insert_before(self):
        """Test inserting elements before a reference."""
        from good_agent.core.mdxl import MDXL
        from good_agent.resources.editable_mdxl import EditableMDXL

        mdxl = MDXL("""
        <doc>
            <item id="2">Second</item>
            <item id="3">Third</item>
        </doc>
        """)

        resource = EditableMDXL(mdxl)
        await resource.initialize()

        tools = resource.get_tools()
        insert_tool = next(tool for tool in tools if tool.name == "insert")

        # Insert before second item
        result = await insert_tool(
            reference_xpath="//item[@id='2']",
            element_tag="item",
            position="before",
            text_content="First",
            attributes={"id": "1"},
        )
        response = result.response if hasattr(result, "response") else str(result)
        assert "Inserted <item> before" in response

        # Verify order
        content = resource.state.outer
        first_pos = content.index("First")
        second_pos = content.index("Second")
        assert first_pos < second_pos

    @pytest.mark.asyncio
    async def test_append_child(self):
        """Test appending child elements."""
        from good_agent.core.mdxl import MDXL
        from good_agent.resources.editable_mdxl import EditableMDXL

        mdxl = MDXL("""
        <doc>
            <entities>
                <person>John</person>
            </entities>
        </doc>
        """)

        resource = EditableMDXL(mdxl)
        await resource.initialize()

        tools = resource.get_tools()
        append_tool = next(tool for tool in tools if tool.name == "append_child")

        # Append a new person
        result = await append_tool(
            parent_xpath="//entities",
            element_tag="person",
            text_content="Jane",
            attributes={"role": "candidate"},
        )
        response = result.response if hasattr(result, "response") else str(result)
        assert "Appended <person> as child" in response
        assert "Jane" in resource.state.outer
        assert 'role="candidate"' in resource.state.outer

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting elements."""
        from good_agent.core.mdxl import MDXL
        from good_agent.resources.editable_mdxl import EditableMDXL

        mdxl = MDXL("""
        <doc>
            <item>Keep this</item>
            <item class="delete">Remove this</item>
            <item>Keep this too</item>
        </doc>
        """)

        resource = EditableMDXL(mdxl)
        await resource.initialize()

        tools = resource.get_tools()
        delete_tool = next(tool for tool in tools if tool.name == "delete")

        # Delete item with class="delete"
        result = await delete_tool(xpath="//item[@class='delete']")
        response = result.response if hasattr(result, "response") else str(result)
        assert "Deleted 1 element(s)" in response
        assert "Remove this" not in resource.state.outer
        assert "Keep this" in resource.state.outer
        assert "Keep this too" in resource.state.outer

    @pytest.mark.asyncio
    async def test_agent_integration(self):
        """Test integration with Agent."""
        from good_agent.core.mdxl import MDXL
        from good_agent.resources.editable_mdxl import EditableMDXL

        mdxl = MDXL("""
        <document>
            <title>Test Document</title>
            <content status="draft">Initial content here</content>
        </document>
        """)

        resource = EditableMDXL(mdxl)

        async with Agent("Document editor") as agent, resource(agent) as r:
            # Should have all tools
            assert "read" in agent.tools
            assert "update" in agent.tools
            assert "replace_text" in agent.tools
            assert "insert" in agent.tools  # Unified insert tool
            assert "append_child" in agent.tools
            assert "delete" in agent.tools

            # Read the document - find the tool by name
            read_tool = agent.tools["read"]
            result = await read_tool(_agent=agent)
            response = result.response if hasattr(result, "response") else str(result)
            assert "Test Document" in response

            # Update with dict attributes - find the tool by name
            update_result = await r.update(
                xpath="//content",
                text_content="Updated content",
                attributes={"status": "reviewed", "version": "2"},
            )
            update_response = (
                update_result.response if hasattr(update_result, "response") else str(update_result)
            )
            assert "text content" in update_response
            assert "set status='reviewed'" in update_response

        # Verify changes persisted
        assert "Updated content" in resource.state.outer
        assert 'status="reviewed"' in resource.state.outer
        assert 'version="2"' in resource.state.outer
