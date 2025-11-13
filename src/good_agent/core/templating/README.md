# GoodIntel Core Templating

High‑level templating utilities and conventions built on Jinja2, designed for configuration‑friendly environments, safe defaults, easy registry‑based templates, and a small set of useful extensions and filters.

## Overview
- Primary entry point: `create_environment(config: dict | None = None, loader: BaseLoader | None = None) -> Environment`
- Registry loader: `TemplateRegistry` with a global `TEMPLATE_REGISTRY`
- Convenience render: `render_template(template, context=None, environment=None, environment_config=None, environment_loader=None)`
- Base class for class‑based templates: `AbstractTemplate`
- Decorators to register Jinja filters/functions: `register_filter`, `register_function`
- Built‑in extensions: `SectionExtension`, `MultiLineInclude`
- Custom line statements: `!#` (line statements) and `!##` (line comments) to avoid conflicts with Markdown headings

Defaults used by `create_environment` (can be overridden via `config`):
- `autoescape=False`
- `trim_blocks=True`, `lstrip_blocks=True`, `keep_trailing_newline=False`
- `line_statement_prefix='!#'`, `line_comment_prefix='!##'`
- Extensions: `SectionExtension` and `MultiLineInclude`

## Quick start
```python
from good_agent.core.templating import create_environment

env = create_environment()
tmpl = env.from_string("Hello {{ name }}")
print(tmpl.render(name="World"))  # -> Hello World
```

## Custom line statements and comments
`create_environment` enables Jinja line statements with `!#` and line comments with `!##`.

```jinja
!# set title = "Dynamic Title"
!# section "header"
<h1>{{ title }}</h1>
!# end section

!## This entire line is a comment and will not render
```

You can freely mix line‑statement syntax with regular block syntax:

```jinja
!# section "line-section"
Line content
{% section "tag-section" %}
Tag content
{% end section %}
!# end section
```

## Template registry (in‑memory loader)
Use the global registry as a loader and add named templates programmatically:

```python
from good_agent.core.templating import (
    create_environment,
    add_named_template,
    get_named_template,
    TEMPLATE_REGISTRY,
)

add_named_template("greeting", "Hello {{ who }}!\n")

env = create_environment(loader=TEMPLATE_REGISTRY)
tmpl = env.get_template("greeting")  # via loader
print(tmpl.render(who="GI"))

# Or fetch the raw string from registry
source = get_named_template("greeting")
```

Layered/temporary contexts are supported via `TemplateRegistry.new_context({...})` and `reset()`.

## Rendering convenience
`render_template` accepts strings, bytes, or `AbstractTemplate` instances and will construct an environment if none is provided.

```python
from good_agent.core.templating import render_template

rendered = render_template("Value: {{ x }}", {"x": 42})
```

On syntax errors it raises a `RuntimeError` with a helpful context snippet.

## Class‑based templates
Subclass `AbstractTemplate` and implement `render()` or provide a `__template__` class variable.

```python
from good_agent.core.templating import AbstractTemplate

class Hello(AbstractTemplate):
    __template__ = "Hello {{ name }}"

    def render(self, name="World") -> str:
        # Optionally delegate to env rendering if you need filters/functions
        return self.get_template().replace("{{ name }}", name)

print(str(Hello()))              # -> Hello World
print(Hello().render(name="GI"))  # -> Hello GI
```

You can also render class‑based templates from within Jinja using the built‑in `render` filter:

```jinja
{{ my_template_instance | render(foo="bar") }}
```

## Registering filters and functions
Decorators attach callables to the global dependency registry that’s automatically applied to all environments constructed via `create_environment`.

```python
from good_agent.core.templating import register_filter, register_function

@register_filter("shout", deprecated_aliases=["loud"], pass_context=None)
def shout(s: str) -> str:
    return str(s).upper()

@register_function("now", pass_context=True)
def now(context) -> str:
    # `pass_context=True` provides the Jinja context as first argument
    return "…"

@register_function("with_env", pass_context="env")
def with_env(env) -> str:
    # `pass_context='env'` provides the Environment
    return env.line_statement_prefix
```

`pass_context` options:
- `True`: Jinja `Context`
- `'eval'`: `EvalContext`
- `'env'`: `Environment`
- `False`/`None`: no implicit argument

Deprecated aliases are supported and emit a `DeprecationWarning` when used, while the primary name remains warning‑free.

## Built‑in extensions
### SectionExtension
Indent‑aware block wrapper that renders structured tags while preserving indentation of the `{% section %}` opening line.

```jinja
{% section "instructions" type="div" class="box" %}
Step 1
Step 2
{% end section %}
```

Renders to:

```html
<instructions type="div" class="box">
Step 1
Step 2
</instructions>
```

You can also use the `section` filter: `{{ content | section('div', class='x') }}`.

### MultiLineInclude
Indented include helper using `indent content`:

```jinja
    {% include 'snippet.txt' indent content %}
```

The included content is indented to match the call site. Misuse (non‑whitespace before the statement) raises a `TemplateSyntaxError` with a helpful message.

## Security
`autoescape=False` by default. If rendering untrusted HTML, enable autoescape via:

```python
env = create_environment(config={"autoescape": True})
```

## Notes
- Internals: `_compose_environment` is the internal environment builder used by `create_environment` (handles config layering and extension de‑duplication). Prefer `create_environment` in application code.
- All registered filters/functions are applied to any environment built through these APIs.
