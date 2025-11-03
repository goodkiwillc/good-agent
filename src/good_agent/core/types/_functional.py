# from typing import Callable, Any
# from importlib import import_module
# from pydantic_core import CoreSchema, core_schema
# from pydantic import GetCoreSchemaHandler

from typing import TypeAlias

from good_common.types import PythonImportableObject

FuncRef: TypeAlias = PythonImportableObject

# class FuncRef(str):
#     def __new__(cls, func: str | Callable):
#         # if
#         if callable(func):
#             func = f"{func.__module__}:{func.__name__}"
#         instance = super().__new__(cls, func)
#         if ":" in func:
#             instance._path, instance._func = func.rsplit(":", 1)
#         else:
#             instance._path, instance._func = func.rsplit(".", 1)
#         return instance

#     def resolve(self) -> Callable:
#         module = import_module(self._path)
#         return getattr(module, self._func)

#     @classmethod
#     def __get_pydantic_core_schema__(
#         cls, source_type: Any, handler: GetCoreSchemaHandler
#     ) -> CoreSchema:
#         return core_schema.no_info_after_validator_function(cls, handler(str))
