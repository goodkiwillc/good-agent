import asyncio
from good_agent import Agent, tool
from good_agent.agent.core import ensure_ready

class DataAnalyst(Agent):
    def __init__(self, **config):
        super().__init__(
            "You are a data analyst expert.",
            # tools=[self.analyze_data, self.create_chart], # Cannot use instance methods in init like this easily before self is fully init
            **config
        )
        # Register tools after init or use class-based tool pattern properly
        # For simplicity in example, we'll just register them manually or pass them if they were static
        # But instance methods need 'self' which is tricky in __init__ call to super
        
        # Better pattern for instance methods as tools:
        self.tools.register_tool(self.analyze_data)
        self.tools.register_tool(self.create_chart)
    
    @tool
    async def analyze_data(self, data: list[dict]) -> dict:
        """Analyze structured data."""
        if not data:
            return {"mean": 0}
        return {"mean": sum(d["value"] for d in data) / len(data)}
    
    @tool 
    async def create_chart(self, data: dict) -> str:
        """Generate a chart description."""
        return f"Chart showing mean value: {data.get('mean', 0)}"
    
    @ensure_ready
    async def analyze(self, data: list[dict]) -> str:
        """High-level analysis method."""
        self.append(f"Please analyze this data: {data}")
        response = await self.call()
        return response.content

async def main():
    async with DataAnalyst() as analyst:
        result = await analyst.analyze([{"value": 10}, {"value": 20}])
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
