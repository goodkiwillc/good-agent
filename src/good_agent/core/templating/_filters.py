import datetime
import textwrap

from good_common.utilities import filter_nulls, yaml_dumps

from good_agent.core.templating._core import register_filter


@register_filter("yaml", deprecated_aliases=["to_yaml"])
def to_yaml(value):
    """Serialize a Python value to YAML."""
    return yaml_dumps(value)


@register_filter("strftime", deprecated_aliases=["fmt_datetime"])
def format_datetime(value: datetime.datetime | datetime.date, fmt: str = "%Y-%m-%d %H:%M:%S"):
    """Format datetime/date with strftime; ISO when no format provided."""
    if not value:
        return ""

    # Handle both datetime and date objects
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        # Convert date to datetime for strftime
        value = datetime.datetime.combine(value, datetime.time.min)

    if fmt:
        return value.strftime(fmt)
    return value.isoformat()


@register_filter("as_date", deprecated_aliases=["fmt_date"])
def format_date(value: datetime.datetime | datetime.date | str, fmt: str | None = None):
    """Coerce value to date; optionally format; accepts ISO strings."""
    if not value:
        return ""

    # Parse string dates
    if isinstance(value, str):
        try:
            # Try to parse as datetime first
            parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            value = parsed.date()
        except (ValueError, AttributeError):
            try:
                # Try to parse as date
                if isinstance(value, str):
                    value = datetime.datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                # If all parsing fails, return the string as-is
                return value

    # Convert datetime to date
    if isinstance(value, datetime.datetime):
        value = value.date()

    # If no format specified, return the date object (for chaining with strftime)
    if fmt is None:
        return value

    # Otherwise format and return string
    return value.strftime(fmt)


@register_filter("filter_nulls")
def _filter_nulls(value):
    return filter_nulls(value)


@register_filter("curly")
def curly(value):
    """Return template syntax as literal string."""
    # The curly filter should return the string as-is
    # The purpose is to output template syntax literally
    return str(value)


@register_filter("dedent")
def dedent(value):
    """Dedent a string, removing common leading whitespace."""
    # First use textwrap.dedent to remove common leading whitespace
    dedented = textwrap.dedent(str(value))

    # If there's still indentation on non-first lines, remove it
    # This handles cases where the text has mixed indentation
    lines = dedented.split("\n")
    if len(lines) > 1:
        # Find if any lines still have leading whitespace
        result_lines = []
        for _i, line in enumerate(lines):
            if line.strip():  # Non-empty line
                result_lines.append(line.lstrip())
            else:
                result_lines.append(line)
        dedented = "\n".join(result_lines)

    return dedented.strip()


@register_filter("renderable")
def renderable(value, format=None):
    """Render a Renderable object with optional format."""
    if hasattr(value, "render"):
        if format is not None:
            return value.render(format=format)
        else:
            return value.render()
    return str(value)
