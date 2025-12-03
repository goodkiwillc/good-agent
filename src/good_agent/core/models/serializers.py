import datetime
from typing import Annotated

from good_common.utilities import any_datetime_to_utc
from pydantic import SerializerFunctionWrapHandler
from pydantic.functional_serializers import WrapSerializer


def _datetime_to_utc_serializer(value: datetime.datetime, nxt: SerializerFunctionWrapHandler):
    normalized = any_datetime_to_utc(value)

    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=datetime.UTC)
    elif normalized.tzinfo is not datetime.UTC:
        normalized = normalized.astimezone(datetime.UTC)

    return nxt(normalized)


DateTimeSerializedUTC = Annotated[datetime.datetime, WrapSerializer(_datetime_to_utc_serializer)]
