from good_agent.core.mdxl import MDXL
from good_agent.core.text import StringFormatter


def test_string_formatter_splits_and_combines_paragraphs():
    formatter = StringFormatter()
    text = "Paragraph one\n\nParagraph two\n\n\nParagraph three"
    paragraphs = formatter.split_into_paragraphs(text)
    assert paragraphs[1][0] == 1  # one newline before second paragraph
    recombined = formatter.combine_paragraphs(paragraphs)
    assert "Paragraph two" in recombined


def test_string_formatter_grouping_and_cleaners():
    formatter = StringFormatter()
    broken = "The big fox\nwalks here.\n\n○ point one\ncontinued"
    grouped = formatter.group_broken_paragraphs(broken)
    assert "The big fox walks here." in grouped
    assert "point one" in grouped
    assert formatter.clean_bullets("• hello").startswith("hello")
    assert formatter.format_encoding_str("ISO_8859_6_I") == "iso-8859-6"


def test_mdxl_detects_legacy_and_handles_attributes():
    mdxl = MDXL("<section private></section>", convert_legacy=False)
    section = mdxl.select("./section")
    assert section.attributes["private"] is True
    assert mdxl._should_convert_legacy("[1] Missing definition") is True
    assert mdxl._should_convert_legacy('<?mdxl version="2"?>\n<root></root>') is False


def test_mdxl_references_and_sort_children():
    content = """\
<section>
[1]: https://example.com
<link url=\"https://two.com\"/>
</section>
"""
    mdxl = MDXL(content, convert_legacy=False)
    refs = mdxl.references
    assert "https://example.com" in refs
    assert "https://two.com" in refs

    sortable = MDXL(
        """\
<items>
  <item date=\"2024-01-02\" />
  <item date=\"2024-01-01\" />
</items>
""",
        convert_legacy=False,
    )
    items = sortable.select("./items")
    items.sort_children("date")
    dates = [child.get("date") for child in items._root]
    assert dates == sorted(dates)
