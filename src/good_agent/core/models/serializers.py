"""
CONTEXT: Custom pydantic serializers for data transformation and normalization.
ROLE: Provide serializers for datetime normalization and other data transformations
      to ensure consistent data representation across goodintel_core models.
DEPENDENCIES: good_common.utilities for datetime conversion, pydantic for serialization framework.
ARCHITECTURE: Pydantic serializer functions and annotated type aliases for model field decoration.
KEY EXPORTS: DateTimeSerializedUTC
USAGE PATTERNS:
  1) Use DateTimeSerializedUTC for automatic UTC conversion in model fields
  2) Apply as field annotation: created_at: DateTimeSerializedUTC
  3) Extend with additional serializers for custom data transformations
RELATED MODULES: .base (base model classes), .entities (entity models with datetime fields)
"""

import datetime
from typing import Annotated

from good_common.utilities import any_datetime_to_utc
from pydantic import SerializerFunctionWrapHandler
from pydantic.functional_serializers import WrapSerializer


def _datetime_to_utc_serializer(
    value: datetime.datetime, nxt: SerializerFunctionWrapHandler
):
    return nxt(any_datetime_to_utc(value))


DateTimeSerializedUTC = Annotated[
    datetime.datetime, WrapSerializer(_datetime_to_utc_serializer)
]
