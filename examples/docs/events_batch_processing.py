"""Batch related events for efficiency."""

import asyncio

from good_agent import Agent, AgentComponent
from good_agent.events import AgentEvents


class BatchProcessor(AgentComponent):
    """Component that batches message processing."""

    def __init__(self, batch_size: int = 10):
        super().__init__()
        self.batch_size = batch_size
        self.message_buffer: list = []

    async def install(self, agent):
        await super().install(agent)

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def buffer_message(ctx):
            self.message_buffer.append(ctx.parameters["message"])

            if len(self.message_buffer) >= self.batch_size:
                self.process_batch()

    def process_batch(self):
        """Process messages in batches for efficiency."""
        messages = self.message_buffer.copy()
        self.message_buffer.clear()

        # Batch processing logic
        print(f"Processing batch of {len(messages)} messages")


async def main():
    """Demonstrate batch event processing."""
    processor = BatchProcessor(batch_size=3)
    async with Agent("Assistant", extensions=[processor]) as agent:
        # Add messages to trigger batching
        for i in range(5):
            agent.append(f"Message {i + 1}")

        print("Messages added, batches processed automatically")


if __name__ == "__main__":
    asyncio.run(main())
