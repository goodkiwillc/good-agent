import asyncio
import json
from pathlib import Path

from good_agent import Agent


class PersistentAgent(Agent):
    def __init__(self, state_file: str, **config):
        super().__init__(**config)
        self.state_file = Path(state_file)

    async def __aenter__(self):
        agent = await super().__aenter__()
        await self._load_state()
        return agent

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._save_state()
        return await super().__aexit__(exc_type, exc_val, exc_tb)

    async def _load_state(self):
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    content = f.read()
                    if not content.strip():
                        return  # Empty file, nothing to load
                    data = json.loads(content)
                    # Reconstruct messages from saved data
                    # Simplified loading logic for example
                    # In real usage, use self._restore_message or similar logic
                    print(f"Loaded {len(data.get('messages', []))} messages from state")
            except json.JSONDecodeError:
                print(f"Warning: Could not decode state file {self.state_file}")

    async def _save_state(self):
        # Explicitly convert ULID to string since default json serializer doesn't handle it
        # Also use mode="json" in model_dump() to handle datetime serialization
        data = {
            "session_id": str(self.session_id),
            "messages": [
                # msg.model_dump(mode="json") ensures dates are strings
                {**msg.model_dump(mode="json"), "id": str(msg.id)}
                for msg in self.messages
            ],
        }
        with open(self.state_file, "w") as f:
            json.dump(data, f, indent=2)
            print("State saved")


async def main():
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        state_path = tmp.name

    try:
        async with PersistentAgent(state_path, model="gpt-4o-mini") as agent:
            agent.append("Hello!")

    finally:
        if os.path.exists(state_path):
            os.unlink(state_path)


if __name__ == "__main__":
    asyncio.run(main())
