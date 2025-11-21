import pytest
from good_agent import Agent, Conversation
from good_agent.messages import SystemMessage
from good_agent.content import TextContentPart

class MockModel:
    def create_message(self, *args, **kwargs):
        role = kwargs.get("role", "user")
        content_parts = kwargs.get("content_parts", [])
        if not content_parts and args:
            content_parts = list(args)
        
        return SystemMessage(
            role=role,
            content_parts=content_parts,
            citations=kwargs.get("citations"),
        )

@pytest.mark.asyncio
async def test_conversation_context_injection():
    """Test that system messages are injected with context in group chats."""
    # Setup 3 agents
    agent1 = Agent(name="Agent1")
    agent2 = Agent(name="Agent2")
    agent3 = Agent(name="Agent3")
    
    # Set initial system messages
    agent1.set_system_message("Base prompt 1")
    agent2.set_system_message("Base prompt 2")
    agent3.set_system_message("Base prompt 3")
    
    # Use mock model to avoid actual LLM calls
    agent1._language_model = MockModel()
    agent2._language_model = MockModel()
    agent3._language_model = MockModel()
    
    # Verify initial state
    assert len(agent1.system[0].content_parts) == 1
    assert "Base prompt 1" in str(agent1.system[0].content_parts[0])
    
    # Enter conversation context
    async with Conversation(agent1, agent2, agent3) as convo:
        # Verify injection happened
        assert len(agent1.system[0].content_parts) == 2
        suffix = str(agent1.system[0].content_parts[1])
        
        assert "You are @Agent1" in suffix
        assert "@Agent2" in suffix
        assert "@Agent3" in suffix
        assert "round-robin" in suffix
        
    # Verify restoration after exit
    assert len(agent1.system[0].content_parts) == 1
    assert "Base prompt 1" in str(agent1.system[0].content_parts[0])
    assert "You are @Agent1" not in str(agent1.system[0].content_parts[0])

@pytest.mark.asyncio
async def test_conversation_no_injection_for_pairs():
    """Test that injection is skipped for 2-agent conversations."""
    agent1 = Agent(name="Agent1")
    agent2 = Agent(name="Agent2")
    
    agent1.set_system_message("Base prompt 1")
    agent2.set_system_message("Base prompt 2")
    
    async with Conversation(agent1, agent2) as convo:
        # Should be unchanged
        assert len(agent1.system[0].content_parts) == 1
        assert "Base prompt 1" in str(agent1.system[0].content_parts[0])
