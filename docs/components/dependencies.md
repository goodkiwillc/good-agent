# Component Dependencies

Components can declare dependencies on other components:

```python
class DatabaseComponent(AgentComponent):
    """Component that provides database access."""
    
    @tool
    async def query_db(self, sql: str) -> list[dict]:
        """Execute a database query."""
        return await self._execute_query(sql)

class AnalyticsComponent(AgentComponent):
    """Component that depends on DatabaseComponent."""
    
    __depends__ = ["DatabaseComponent"]  # Declare dependency
    
    async def install(self, agent: Agent):
        await super().install(agent)
        
        # Access dependency
        db_component = self.get_dependency(DatabaseComponent)
        if db_component:
            print("Database component available")
        else:
            raise RuntimeError("DatabaseComponent required but not found")
    
    @tool
    async def analyze_data(self, table: str) -> dict:
        """Analyze data from a database table."""
        db = self.get_dependency(DatabaseComponent)
        
        if not db:
            return {"error": "Database component not available"}
        
        # Use dependency's tools
        data = await db.query_db(f"SELECT * FROM {table}")
        return self._analyze(data)

# Usage - order matters when dependencies exist
agent = Agent(
    "Data analyst",
    extensions=[
        DatabaseComponent(),      # Must come first
        AnalyticsComponent()      # Depends on DatabaseComponent
    ]
)
```

# State Management

## Enable/Disable Components

```python
class ToggleableComponent(AgentComponent):
    
    @tool
    def process_data(self, data: str) -> str:
        """Process data if component is enabled."""
        if not self.enabled:
            return "Component is disabled"
        
        return f"Processed: {data.upper()}"

# Usage
component = ToggleableComponent()
agent = Agent("Assistant", extensions=[component])
await agent.initialize()

# Tools are available when enabled
result = await agent.tools["process_data"](_agent=agent, data="test")
print(result.response)  # "Processed: TEST"

# Disable component - tools become unavailable
component.enabled = False
print(f"Tool available: {'process_data' in agent.tools}")  # False

# Re-enable component
component.enabled = True
print(f"Tool available: {'process_data' in agent.tools}")  # True
```

## Component Cloning

Components support cloning for creating independent instances:

```python
class StatefulComponent(AgentComponent):
    def __init__(self, initial_value: int = 0):
        super().__init__()
        self.value = initial_value
    
    def _clone_init_args(self) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Provide arguments for clone construction."""
        return (), {"initial_value": self.value}
    
    @tool
    def increment(self) -> int:
        """Increment the component's value."""
        self.value += 1
        return self.value

# Create and clone component
original = StatefulComponent(initial_value=10)
clone = original.clone()

# Clone is independent
original.value = 20
print(f"Original: {original.value}, Clone: {clone.value}")  # Original: 20, Clone: 10
```
