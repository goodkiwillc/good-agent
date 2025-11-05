import datetime
from typing import Annotated

from good_common.utilities import parse_timestamp
from pydantic import BeforeValidator

# 1/29/2001 12:00:00 AM
# STRFTIME = "%m/%d/%Y %I:%M:%S %p"

# 10/30/2007 12:00:00 AM
STRFTIME = "%m/%d/%Y %I:%M:%S %p"


def _validate_timestamp(value: str) -> datetime.datetime:
    return parse_timestamp(value, "%m/%d/%Y %I:%M:%S %p", raise_error=True)


def _validate_timestamp_nullable(value: str | None) -> datetime.datetime | None:
    if value is None:
        return None
    try:
        # logger.info(value)
        return parse_timestamp(value, "%m/%d/%Y %I:%M:%S %p", raise_error=True)
    except ValueError:
        # logger.error(f"Error parsing {value} - {e}")
        return None


def _validate_date(value: str) -> datetime.date:
    return parse_timestamp(value, "%m/%d/%Y", raise_error=True)


def _validate_date_nullable(value: str | None) -> datetime.date | None:
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    elif isinstance(value, datetime.date):
        return value
    try:
        return parse_timestamp(value, "%m/%d/%Y", raise_error=True)
    except ValueError:
        # logger.error(f"Error parsing {value} - {e}")
        return None


ParsedDateTime = Annotated[
    datetime.datetime,
    BeforeValidator(_validate_timestamp),
]

NullableParsedDateTime = Annotated[
    datetime.datetime | None,
    BeforeValidator(_validate_timestamp_nullable),
]


ParsedDate = Annotated[
    datetime.date,
    BeforeValidator(_validate_date),
]

NullableParsedDate = Annotated[
    datetime.date | None,
    BeforeValidator(_validate_date_nullable),
]
