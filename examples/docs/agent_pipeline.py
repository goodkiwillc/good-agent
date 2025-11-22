import asyncio

from good_agent import Agent


# @TODO: this is an incorrect example - it's not a pipeline it's a round robin conversation. there's pattern confusion in the docs.
async def main():
    researcher = Agent("You are a researcher. Find facts.")
    writer = Agent("You are a writer. Create content from facts.")
    editor = Agent("You are an editor. Polish the content.")

    # Pipeline composition
    async with researcher | writer | editor:
        researcher.append("Research quantum computing")

        # Each agent processes the previous agent's output
        final_result = await editor.call()
        print(f"Final result: {final_result.content}")


if __name__ == "__main__":
    asyncio.run(main())
