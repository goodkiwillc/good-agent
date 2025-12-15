import re
import xml.etree.ElementTree as etree
from re import Match

from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor
from markdown.preprocessors import Preprocessor
from markdown.util import AtomicString


class CitationPreprocessor(Preprocessor):
    def run(self, lines):
        new_lines = []
        for line in lines:
            # Convert [1] citation format to [1]: format
            match = re.match(r"^\s*\[(\d+)\]\s+(https?://\S+)$", line)
            if match:
                new_lines.append(f"[{match.group(1)}]: {match.group(2)}")
            else:
                new_lines.append(line)
        return new_lines


class SuperscriptCitationProcessor(InlineProcessor):
    def handleMatch(  # type: ignore[override]
        self, m: Match[str], data: str
    ) -> tuple[etree.Element, int, int]:
        el = etree.Element("sup")
        link = etree.SubElement(el, "a")
        link.set("href", f"#{m.group(1)}")
        link.text = AtomicString(f"[{m.group(1)}]")
        return el, m.start(0), m.end(0)


class CitationManager(Extension):
    def __init__(
        self,
        fix_citations=False,
        format_superscript=False,
        **kwargs,
    ):
        self.enable_citation_preprocessor = fix_citations
        self.enable_superscript_citation = format_superscript
        super().__init__(**kwargs)

    def extendMarkdown(self, md):
        # Add the citation preprocessor if enabled
        if self.enable_citation_preprocessor:
            md.preprocessors.register(CitationPreprocessor(md), "citation_preprocessor", 175)

        # Add the superscript citation processor if enabled
        if self.enable_superscript_citation:
            CITATION_PATTERN = r"\[(\d+)\]"
            md.inlinePatterns.register(
                SuperscriptCitationProcessor(CITATION_PATTERN, md),
                "superscript_citation",
                175,
            )
