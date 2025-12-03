from collections.abc import MutableMapping
from typing import Any, Protocol, cast

import markdown
from good_agent.core.markdown import CitationManager, CitationPreprocessor


class _MarkdownReferences(Protocol):
    references: MutableMapping[str, Any]


def test_citation_preprocessor_converts_numeric_references():
    preprocessor = CitationPreprocessor(markdown.Markdown())
    processed = preprocessor.run(
        ["[1] https://example.com"],
    )
    assert processed == ["[1]: https://example.com"]


def test_superscript_citation_processor_renders_anchor():
    md = markdown.Markdown(extensions=[CitationManager(format_superscript=True)])
    html = md.convert("See [1] for details.")
    assert "<sup>" in html
    assert '<a href="#1">[1]</a>' in html


def test_citation_manager_can_register_both_features():
    md = markdown.Markdown(
        extensions=[CitationManager(fix_citations=True, format_superscript=True)]
    )
    html = md.convert("[1] https://example.com\n\nReference [1].")
    assert '<a href="#1">[1]</a>' in html
    # The converted footnote reference should exist in md.references
    reference_entry = cast(_MarkdownReferences, md).references.get("1")
    assert reference_entry is not None
    if isinstance(reference_entry, tuple):
        reference_entry = reference_entry[0]
    assert reference_entry == "https://example.com"
