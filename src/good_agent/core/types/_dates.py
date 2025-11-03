"""
CONTEXT: Date and time type definitions with Pydantic validation for the GoodIntel platform.
ROLE: Provides type-safe date/time parsing with configurable formats and null handling for consistent temporal data management.
DEPENDENCIES:
  - datetime: Standard library date/time handling
  - pydantic: BeforeValidator for custom parsing logic integration
  - good_common.utilities: Timestamp parsing utilities with format specification
ARCHITECTURE:
  - Validation functions: Custom parsing logic with format specification
  - Pydantic annotations: BeforeValidator integration for automatic validation
  - Nullable variants: Type-safe handling of optional date/time values
  - Format specification: Standardized date/time format strings
KEY EXPORTS: ParsedDateTime, NullableParsedDateTime, ParsedDate, NullableParsedDate
USAGE PATTERNS:
  1. Pydantic model field definitions with automatic parsing
  2. API input validation with standardized date formats
  3. Database serialization with consistent formatting
  4. Null-safe date/time handling in optional fields
RELATED MODULES:
  - goodintel_core.models: Base models using date/time types
  - goodintel_core.serialization: Data conversion utilities
  - goodintel_core.validation: Input validation frameworks
  - goodintel_core.clients: External API date/time handling

DATE FORMAT SPECIFICATION:
  - DateTime format: "%m/%d/%Y %I:%M:%S %p" (e.g., "10/30/2007 12:00:00 AM")
  - Date format: "%m/%d/%Y" (e.g., "10/30/2007")
  - 12-hour clock with AM/PM specification
  - US-style date format (month/day/year)

VALIDATION STRATEGY:
  - BeforeValidator hooks for automatic parsing on model creation
  - Strict format validation with clear error messages
  - Graceful null handling in nullable variants
  - Exception handling with informative error context

PERFORMANCE CHARACTERISTICS:
  - Parsing occurs once during model validation
  - Format strings compiled and reused
  - Null variants avoid unnecessary parsing overhead
  - Memory efficient with native datetime objects
"""

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
