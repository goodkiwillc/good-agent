import datetime
from typing import Any, cast

import pytest
from pydantic import BaseModel, ValidationError

from good_agent.core.models.serializers import DateTimeSerializedUTC
from good_agent.core.types._dates import (
    NullableParsedDate,
    NullableParsedDateTime,
    ParsedDate,
    ParsedDateTime,
)
from good_agent.core.types._uuid import UUID


class _SerializerModel(BaseModel):
    ts: DateTimeSerializedUTC


class _DateModel(BaseModel):
    timestamp: ParsedDateTime
    maybe_timestamp: NullableParsedDateTime
    date: ParsedDate
    maybe_date: NullableParsedDate


class _UUIDModel(BaseModel):
    id: UUID


def test_datetime_serializer_converts_to_utc():
    aware = datetime.datetime(
        2024, 1, 1, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=2))
    )
    model = _SerializerModel(ts=aware)
    dump = model.model_dump()
    assert dump["ts"].tzinfo == datetime.timezone.utc
    assert dump["ts"].hour == 10


def test_date_types_parse_and_allow_nulls():
    model = _DateModel(
        timestamp=cast(Any, "10/30/2007 12:00:00 AM"),
        maybe_timestamp=None,
        date=cast(Any, "10/30/2007"),
        maybe_date=cast(Any, "10/31/2007"),
    )
    assert model.timestamp.year == 2007
    assert model.maybe_timestamp is None
    assert model.date.month == 10
    assert model.maybe_date is not None
    assert model.maybe_date.day == 31


def test_nullable_date_returns_none_on_invalid_input():
    model = _DateModel(
        timestamp=cast(Any, "10/30/2007 12:00:00 AM"),
        maybe_timestamp=cast(Any, "11/01/2007 12:00:00 AM"),
        date=cast(Any, "10/30/2007"),
        maybe_date=cast(Any, "invalid"),
    )
    assert isinstance(model.maybe_timestamp, datetime.datetime)
    assert model.maybe_date is None


def test_uuid_type_accepts_multiple_inputs_and_schema_reports_format():
    created = UUID.create_v7()
    as_str = str(created)
    model = _UUIDModel(id=cast(Any, as_str))
    assert isinstance(model.id, UUID)
    from_int = _UUIDModel(id=cast(Any, created.int))
    assert from_int.id == model.id
    schema = _UUIDModel.model_json_schema()
    assert schema["properties"]["id"]["format"] == f"uuid{model.id.uuid_version}"


def test_uuid_type_rejects_invalid_value():
    with pytest.raises(ValidationError):
        _UUIDModel(id=cast(Any, "not-a-uuid"))
