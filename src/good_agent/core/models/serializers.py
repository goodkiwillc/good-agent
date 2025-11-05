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
