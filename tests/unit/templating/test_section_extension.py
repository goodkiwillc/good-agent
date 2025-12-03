import pytest
from good_agent.core.templating._extensions import MultiLineInclude, SectionExtension
from jinja2 import DictLoader, Environment, TemplateSyntaxError


def _render(template: str) -> str:
    env = Environment(extensions=[SectionExtension])
    return env.from_string(template).render().strip()


def test_section_extension_respects_indentation_and_attributes():
    template = """\
{% section 'article' class='intro' %}
  Line
{% endsection %}
"""
    rendered = _render(template)
    assert rendered.splitlines()[0] == '<article class="intro">'
    assert rendered.splitlines()[1].strip() == "Line"
    assert rendered.splitlines()[-1] == "</article>"


def test_section_extension_raises_for_invalid_identifier():
    env = Environment(extensions=[SectionExtension])
    template = "{% section foo-bar %}{% endsection %}"
    with pytest.raises(TemplateSyntaxError):
        env.from_string(template).render()


def test_section_filter_wraps_content_with_default_indentation():
    env = Environment(extensions=[SectionExtension])
    section_ext = next(  # the extension instance is registered on the environment
        ext for ext in env.extensions.values() if isinstance(ext, SectionExtension)
    )
    rendered = section_ext.section_filter("Line", tag_name="aside", role="note")
    assert rendered.splitlines()[0] == '<aside role="note">'
    assert rendered.splitlines()[1] == "    Line"
    assert rendered.splitlines()[2] == "</aside>"


def test_multi_line_include_preserves_indentation():
    loader = DictLoader(
        {
            "main.html": """<div>\n    {% include 'snippet.html' indent content %}\n</div>""",
            "snippet.html": "<p>One</p>\n<p>Two</p>",
        }
    )
    env = Environment(loader=loader, extensions=[MultiLineInclude])
    rendered = env.get_template("main.html").render()
    lines = [line for line in rendered.splitlines() if line.strip()]
    assert lines[0] == "<div>"
    assert lines[1].startswith("    <p>One")
    assert lines[2].startswith("    <p>Two")
    assert lines[-1] == "</div>"


def test_section_extension_nested_sections_preserve_indentation():
    template = """\
{% section content %}
    {% section 'span' class='highlight' %}
        Inner line
    {% endsection %}
{% endsection %}
"""
    rendered = _render(template)
    lines = [line.rstrip("\n") for line in rendered.splitlines() if line.strip()]
    assert lines[0] == "<content>"
    assert lines[1] == '        <span class="highlight">'
    assert lines[2].strip() == "Inner line"
    assert lines[3].strip() == "</span>"
    assert lines[3].startswith("    ")
    assert lines[4] == "</content>"


def test_multi_line_include_requires_whitespace_before_statement():
    loader = DictLoader(
        {
            "invalid.html": "<div>{% include 'snippet.html' indent content %}</div>",
            "snippet.html": "<p>Test</p>",
        }
    )
    env = Environment(loader=loader, extensions=[MultiLineInclude])
    with pytest.raises(TemplateSyntaxError, match="non-whitespace"):
        env.get_template("invalid.html").render()
