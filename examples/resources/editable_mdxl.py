"""Use EditableMDXL tools to append or insert elements."""

from __future__ import annotations

import asyncio

from good_agent.core.mdxl import MDXL
from good_agent.resources.editable_mdxl import EditableMDXL


async def main() -> None:
    document = MDXL("<timeline><event>Kickoff</event></timeline>")
    editor = EditableMDXL(document)
    await editor.initialize()

    await editor.append_child(
        parent_xpath="//timeline",
        element_tag="event",
        text_content="Launch",
    )

    await editor.insert(
        reference_xpath="//event[1]",
        element_tag="event",
        position="after",
        text_content="Retrospective",
    )

    print(await editor.read())


if __name__ == "__main__":
    asyncio.run(main())
