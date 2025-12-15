from typing import TypeAlias

JSONData: TypeAlias = "None | bool | int | float | str | list[JSONData] | dict[str, JSONData]"
