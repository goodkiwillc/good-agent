import pytest
from good_agent import Agent, AgentComponent


class ComponentA(AgentComponent):
    """Component with no dependencies."""

    pass


class ComponentB(AgentComponent):
    """Component that depends on ComponentA."""

    __depends__ = ["ComponentA"]


class ComponentC(AgentComponent):
    """Component that depends on ComponentB."""

    __depends__ = ["ComponentB"]


class ComponentWithMissingDep(AgentComponent):
    """Component with a dependency that won't be satisfied."""

    __depends__ = ["NonExistentComponent"]


class ComponentWithMultipleDeps(AgentComponent):
    """Component with multiple dependencies."""

    __depends__ = ["ComponentA", "ComponentB"]


class ExtendedComponentA(ComponentA):
    """Subclass of ComponentA."""

    pass


class ComponentDependsOnBase(AgentComponent):
    """Component that depends on ComponentA (satisfied by ExtendedComponentA)."""

    __depends__ = ["ComponentA"]


class TestComponentDependencies:
    """Test component dependency validation."""

    @pytest.mark.asyncio
    async def test_no_dependencies(self):
        """Test that components with no dependencies work fine."""
        comp_a = ComponentA()

        async with Agent("Test system", extensions=[comp_a]) as agent:
            # Should initialize without issues
            assert agent[ComponentA] is comp_a

    @pytest.mark.asyncio
    async def test_satisfied_dependency(self):
        """Test that satisfied dependencies work correctly."""
        comp_a = ComponentA()
        comp_b = ComponentB()  # Depends on ComponentA

        async with Agent("Test system", extensions=[comp_a, comp_b]) as agent:
            # Both components should be available
            assert agent[ComponentA] is comp_a
            assert agent[ComponentB] is comp_b

    @pytest.mark.asyncio
    async def test_missing_dependency_raises_error(self):
        """Test that missing dependencies cause initialization to fail."""
        comp = ComponentWithMissingDep()

        with pytest.raises(ValueError) as exc_info:
            async with Agent("Test system", extensions=[comp]) as agent:
                pass  # Should not reach here

        assert "Component dependency validation failed" in str(exc_info.value)
        assert "ComponentWithMissingDep requires NonExistentComponent" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_transitive_dependencies(self):
        """Test that transitive dependencies work correctly."""
        comp_a = ComponentA()
        comp_b = ComponentB()  # Depends on ComponentA
        comp_c = ComponentC()  # Depends on ComponentB

        async with Agent("Test system", extensions=[comp_a, comp_b, comp_c]) as agent:
            # All components should be available
            assert agent[ComponentA] is comp_a
            assert agent[ComponentB] is comp_b
            assert agent[ComponentC] is comp_c

    @pytest.mark.asyncio
    async def test_order_doesnt_matter(self):
        """Test that the order of component registration doesn't matter."""
        comp_a = ComponentA()
        comp_b = ComponentB()  # Depends on ComponentA

        # Register in reverse dependency order
        async with Agent("Test system", extensions=[comp_b, comp_a]) as agent:
            # Both should still work
            assert agent[ComponentA] is comp_a
            assert agent[ComponentB] is comp_b

    @pytest.mark.asyncio
    async def test_multiple_dependencies(self):
        """Test components with multiple dependencies."""
        comp_a = ComponentA()
        comp_b = ComponentB()
        comp_multi = ComponentWithMultipleDeps()  # Depends on both A and B

        async with Agent(
            "Test system", extensions=[comp_a, comp_b, comp_multi]
        ) as agent:
            # All should be available
            assert agent[ComponentA] is comp_a
            assert agent[ComponentB] is comp_b
            assert agent[ComponentWithMultipleDeps] is comp_multi

    @pytest.mark.asyncio
    async def test_partially_missing_dependencies(self):
        """Test that partially satisfied dependencies still fail."""
        comp_a = ComponentA()
        comp_multi = (
            ComponentWithMultipleDeps()
        )  # Depends on both A and B, but B is missing

        with pytest.raises(ValueError) as exc_info:
            async with Agent("Test system", extensions=[comp_a, comp_multi]) as agent:
                pass

        assert "ComponentWithMultipleDeps requires ComponentB" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_dependency_satisfied_by_subclass(self):
        """Test that dependencies can be satisfied by subclasses."""
        extended_a = ExtendedComponentA()  # Subclass of ComponentA
        comp_depends = ComponentDependsOnBase()  # Depends on ComponentA

        async with Agent("Test system", extensions=[extended_a, comp_depends]) as agent:
            # Should work because ExtendedComponentA is a subclass of ComponentA
            assert agent[ExtendedComponentA] is extended_a
            assert agent[ComponentDependsOnBase] is comp_depends
            # The base class should also resolve to the extended instance
            assert agent[ComponentA] is extended_a

    @pytest.mark.asyncio
    async def test_multiple_missing_dependencies_all_reported(self):
        """Test that all missing dependencies are reported in the error."""
        comp1 = ComponentWithMissingDep()
        comp2 = ComponentB()  # Depends on ComponentA which is missing

        with pytest.raises(ValueError) as exc_info:
            async with Agent("Test system", extensions=[comp1, comp2]) as agent:
                pass

        error_msg = str(exc_info.value)
        assert "Component dependency validation failed" in error_msg
        # Both missing dependencies should be reported
        assert "ComponentWithMissingDep requires NonExistentComponent" in error_msg
        assert "ComponentB requires ComponentA" in error_msg

    @pytest.mark.asyncio
    async def test_empty_depends_list(self):
        """Test that empty __depends__ list works correctly."""

        class ComponentWithEmptyDeps(AgentComponent):
            __depends__ = []

        comp = ComponentWithEmptyDeps()

        async with Agent("Test system", extensions=[comp]) as agent:
            # Should work fine with empty dependencies
            assert agent[ComponentWithEmptyDeps] is comp
