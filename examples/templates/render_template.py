"""Render inline templates and deferred Template objects."""

from __future__ import annotations

from good_agent.extensions.template_manager.core import Template, TemplateManager


def main() -> None:
    manager = TemplateManager(enable_file_templates=False)

    greeting = manager.render("Hello {{ name }}!", {"name": "Chris"})
    print(greeting)

    template = Template("{{ product }} v{{ version }} ships {{ date }}", strict=False)
    print(template.render({"product": "good-agent", "version": "0.3", "date": "soon"}))


if __name__ == "__main__":
    main()
