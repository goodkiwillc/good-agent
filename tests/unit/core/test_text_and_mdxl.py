import pytest
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
    dates: list[str] = []
    for child in items._root:
        date = child.get("date")
        assert date is not None
        dates.append(date)
    assert dates == sorted(dates)


def test_mdxl_version_yaml_and_templates():
    content = """<?mdxl version=\"2\"?>
    <doc>
      <data yaml>
      foo: bar
      </data>
      <templates>
        <template name=\"greeting\">Hello</template>
      </templates>
    </doc>
    """
    mdxl = MDXL(content, convert_legacy=False)

    assert mdxl.version == "2"
    data_elem = mdxl.select("./doc/data")
    assert data_elem.attributes["yaml"] is True
    box_data = data_elem.data
    assert box_data["foo"] == "bar"

    assert mdxl.select("./doc").templates == {"greeting": "Hello"}


def test_mdxl_select_behaviour_and_children():
    content = """<doc>
      <item id=\"a\" />
      <item id=\"b\" />
    </doc>"""
    mdxl = MDXL(content, convert_legacy=False)

    assert len(mdxl) == 1  # auto-wrapped root contains a single <doc> element
    doc = mdxl[0]
    assert doc.tag == "doc"
    assert len(doc.children) == 2
    assert doc.children[0].get("id") == "a"

    with pytest.raises(IndexError):
        _ = doc[5]

    with pytest.raises(ValueError):
        doc.select("./missing")

    assert doc.select("./missing", raise_if_none=False) is None


def test_mdxl_data_setter_updates_text():
    mdxl = MDXL("<root></root>", convert_legacy=False)
    mdxl.data = {"answer": 42}
    assert mdxl.get("yaml") == "yaml"
    assert "answer" in mdxl.text
    # Updating through Box should persist
    data_box = mdxl.data
    data_box["answer"] = 84
    assert "84" in mdxl.text


def test_string_formatter_auto_groupers_and_cleaning():
    formatter = StringFormatter()
    dense = "Line one\nLine two\nLine three"
    assert formatter.auto_paragraph_grouper(dense).count("\n\n") == 2

    sparse = "Paragraph one\n\nParagraph two\n\n\nParagraph three"
    grouped = formatter.auto_paragraph_grouper(sparse)
    assert grouped.count("\n\n") >= 2

    cleaned = formatter.clean(
        "Item 1.     BUSINESS-",
        extra_whitespace=True,
        dashes=True,
        trailing_punctuation=True,
    )
    assert cleaned == "Item 1. BUSINESS"

    quoted = formatter.replace_unicode_quotes("\x93Test\x94")
    assert quoted == "“Test”"


def test_string_formatter_bytes_and_index_adjustment():
    formatter = StringFormatter()
    converted = formatter.bytes_string_to_string("ABC")
    assert converted == "ABC"

    cleaned, indices = formatter.clean_extra_whitespace_with_index_run("Hello   world")
    assert cleaned == "Hello world"
    adjusted = StringFormatter.index_adjustment_after_clean_extra_whitespace(5, indices)
    assert adjusted <= 5
