import datetime

from good_agent.core.templating._filters import (
    dedent,
    format_date,
    format_datetime,
    renderable,
    to_yaml,
)


class DummyRenderable:
    def __init__(self, value: str):
        self._value = value

    def render(self, format: str | None = None):  # noqa: A003  (match signature)
        if format:
            return f"{self._value}:{format}"
        return self._value


def test_to_yaml_serializes_value():
    yaml_text = to_yaml({"name": "agent", "values": [1, 2, None]})
    assert "values" in yaml_text
    assert "- 2" in yaml_text


def test_format_datetime_handles_date_and_custom_format():
    dt = datetime.datetime(2024, 1, 1, 9, 30, 0)
    assert format_datetime(dt, "%Y-%m-%d") == "2024-01-01"


def test_format_datetime_converts_date_objects():
    date_value = datetime.date(2024, 5, 5)
    assert format_datetime(date_value, "%d/%m/%Y") == "05/05/2024"


def test_format_date_parses_string_and_returns_date_when_fmt_none():
    result = format_date("2024-07-04")
    assert isinstance(result, datetime.date)
    assert result.year == 2024


def test_format_date_returns_raw_value_when_parse_fails():
    raw = "not-a-date"
    assert format_date(raw) == raw


def test_dedent_removes_indentation_and_trailing_spaces():
    text = """\
        Line one
            Line two
    """
    assert dedent(text) == "Line one\nLine two"


def test_renderable_invokes_render_method_when_available():
    dummy = DummyRenderable("value")
    assert renderable(dummy, format="json") == "value:json"
    assert renderable("plain") == "plain"
