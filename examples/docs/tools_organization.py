"""Tool organization patterns: grouping related tools in components."""

import asyncio

from good_agent import Agent, AgentComponent, tool


class DatabaseTools(AgentComponent):
    """Component containing database-related tools."""

    @tool
    def create_user(self, user_data: dict) -> dict:
        """Create a new user."""
        # Simulated user creation
        new_user = {"id": "user_123", **user_data}
        return new_user

    @tool
    def get_user(self, user_id: str) -> dict:
        """Retrieve user by ID."""
        # Simulated user retrieval
        return {"id": user_id, "name": "John Doe", "email": "john@example.com"}

    @tool
    def update_user(self, user_id: str, updates: dict) -> dict:
        """Update user information."""
        # Simulated user update
        return {"id": user_id, **updates, "updated": True}


class SearchTools(AgentComponent):
    """Component containing search-related tools."""

    @tool
    def search_users(self, query: str) -> list[dict]:
        """Search for users."""
        # Simulated user search
        return [
            {"id": "1", "name": "Alice", "relevance": 0.9},
            {"id": "2", "name": "Bob", "relevance": 0.7},
        ]

    @tool
    def search_content(self, query: str) -> list[dict]:
        """Search for content."""
        # Simulated content search
        return [
            {"id": "doc_1", "title": "Introduction", "relevance": 0.85},
            {"id": "doc_2", "title": "Advanced Topics", "relevance": 0.75},
        ]


async def main():
    """Demonstrate tool organization with component classes."""
    # Create component instances
    db_tools = DatabaseTools()
    search_tools = SearchTools()

    async with Agent(
        "You are a helpful assistant.", extensions=[db_tools, search_tools]
    ) as agent:
        # Test database tools
        print("Creating user...")
        result = await agent.invoke(
            db_tools.create_user,
            user_data={"name": "Alice", "email": "alice@example.com"},
        )
        print(f"Created: {result.response}\n")

        # Test search tools
        print("Searching users...")
        result = await agent.invoke(search_tools.search_users, query="Alice")
        print(f"Search results: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
