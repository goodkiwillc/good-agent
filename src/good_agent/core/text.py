from __future__ import annotations

import os
import quopri
import re
import sys
import textwrap
import unicodedata
from typing import Final

import numpy as np

DEFAULT_WRAP_WIDTH = 70  # same as textwrap's default

UNICODE_BULLETS: Final[list[str]] = [
    "\u0095",
    "\u2022",
    "\u2023",
    "\u2043",
    "\u3164",
    "\u204c",
    "\u204d",
    "\u2219",
    "\u25cb",
    "\u25cf",
    "\u25d8",
    "\u25e6",
    "\u2619",
    "\u2765",
    "\u2767",
    "\u29be",
    "\u29bf",
    "\u002d",
    "",
    r"\*",
    "\x95",
    "·",
]
BULLETS_PATTERN = "|".join(UNICODE_BULLETS)

LINE_BREAK = r"(?<=\n)"
PARAGRAPH_PATTERN = r"\s*\n\s*"
DOUBLE_PARAGRAPH_PATTERN_RE = re.compile("(" + PARAGRAPH_PATTERN + "){2}")
E_BULLET_PATTERN = re.compile(r"^e(?=\s)", re.MULTILINE)
LINE_BREAK_RE = re.compile(LINE_BREAK)
UNICODE_BULLETS_RE = re.compile(f"(?:{BULLETS_PATTERN})(?!{BULLETS_PATTERN})")
UNICODE_BULLETS_RE_0W = re.compile(f"(?={BULLETS_PATTERN})(?<!{BULLETS_PATTERN})")
SENTENCE_PUNCT_RE = re.compile(r"[.!?]['\"]?$")


PARAGRAPH_PATTERN_RE = re.compile(
    f"((?:{BULLETS_PATTERN})|{PARAGRAPH_PATTERN})(?!{BULLETS_PATTERN}|$)",
)
DOUBLE_PARAGRAPH_PATTERN_RE = re.compile("(" + PARAGRAPH_PATTERN + "){2}")

tbl = dict.fromkeys(
    i for i in range(sys.maxunicode) if unicodedata.category(chr(i)).startswith("P")
)


class StringFormatter:
    def __init__(self, call_behavior: str | list[str] = "unindent") -> None:
        """Initialize the StringFormatter class."""
        self._default_wrap_width = DEFAULT_WRAP_WIDTH

        self._call_behavior = call_behavior

    def __call__(self, s: str | None) -> str:
        if isinstance(self._call_behavior, str):
            _calls = [self._call_behavior]
        else:
            _calls = self._call_behavior

        for call in _calls:
            if hasattr(self, call):
                s = getattr(self, call)(s)
            else:
                raise ValueError(f"Method {call} not found in StringFormatter.")
        return s if s is not None else ""

    def unindent(self, s: str | None) -> str:
        if not s:
            return ""
        return textwrap.dedent(s).strip()

    def remove_all_indents(self, text: str, width: bool = False, strip: bool = True) -> str:
        return self.undent(text, width, strip)

    def get_indentation(self, line: str) -> str:
        return line[0 : len(line) - len(line.lstrip())]

    def split_into_paragraphs(self, text: str) -> list[tuple[int, str]]:
        """
        Split <s> into paragraphs and the number of newlines before each
        paragraph, so whitespace between paragraphs can be preserved. Ex:

        split_into_paragraphs('''a

        b


        c''')

        return [(0, 'a'), (1, 'b'), (2, 'c')].
        """
        paragraphs = []

        paragraph_lines: list[str] = []
        num_newlines_before_paragraphs = 0
        for line in text.splitlines():
            if not line.strip() and paragraph_lines:  # end of current paragraph
                paragraph = os.linesep.join(paragraph_lines)
                paragraphs.append((num_newlines_before_paragraphs, paragraph))
                paragraph_lines = []
                num_newlines_before_paragraphs = 1
            elif not line.strip():  # another empty line before the next paragraph
                num_newlines_before_paragraphs += 1
            elif (
                paragraph_lines  # new paragraph with different indentation
                and self.get_indentation(line) != self.get_indentation(paragraph_lines[-1])
            ):
                paragraph = os.linesep.join(paragraph_lines)
                paragraphs.append((num_newlines_before_paragraphs, paragraph))
                paragraph_lines = [line]
                num_newlines_before_paragraphs = 0
            else:  # a new line in the current paragraph
                paragraph_lines.append(line)

        if num_newlines_before_paragraphs or paragraph_lines:
            paragraph = os.linesep.join(paragraph_lines)
            paragraphs.append((num_newlines_before_paragraphs, paragraph))

        return paragraphs

    def combine_paragraphs(self, paragraphs: list[tuple[int, str]]) -> str:
        expanded = [(os.linesep * num_newlines_) + p for num_newlines_, p in paragraphs]
        return os.linesep.join(expanded)

    def unwrap(self, text: str) -> str:
        toks = [
            line.rstrip() if i == 0 else line.strip() for i, line in enumerate(text.splitlines())
        ]
        unwrapped = " ".join(toks).rstrip()
        return unwrapped

    def lstring_empty_lines(self, text: str) -> str:
        """
        Only strip empty lines to preserve initial indentation. Ex

        lstring_empty_lines('''


            foo
        blah''')

        returns '  foo\nblah'.
        """
        lines: list[str] = []
        for line in text.splitlines():
            if lines or line.strip():
                lines.append(line)

        text = os.linesep.join(lines)
        return text

    def undent(self, text: str, width=False, strip=True):
        text = textwrap.dedent(text)

        if strip:
            text = self.lstring_empty_lines(text)  # preserve indentation; only strip empty lines
            text = text.rstrip()

        if width is False:  # unwrap
            paragraphs = [
                (newlines, self.unwrap(p)) for newlines, p in self.split_into_paragraphs(text)
            ]
            text = self.combine_paragraphs(paragraphs)
        elif width:
            width = DEFAULT_WRAP_WIDTH if width is True else width
            paragraphs = [
                (newlines, textwrap.fill(p, width))
                for newlines, p in self.split_into_paragraphs(text)
            ]
            text = self.combine_paragraphs(paragraphs)

        return text

    def format_encoding_str(self, encoding: str) -> str:
        """Format input encoding string (e.g., `utf-8`, `iso-8859-1`, etc).
        Parameters
        ----------
        encoding
            The encoding string to be formatted (e.g., `UTF-8`, `utf_8`, `ISO-8859-1`, `iso_8859_1`,
            etc).
        """
        formatted_encoding = encoding.lower().replace("_", "-")

        # Special case for Arabic and Hebrew charsets with directional annotations
        annotated_encodings = [
            "iso-8859-6-i",
            "iso-8859-6-e",
            "iso-8859-8-i",
            "iso-8859-8-e",
        ]
        if formatted_encoding in annotated_encodings:
            formatted_encoding = formatted_encoding[:-2]  # remove the annotation

        return formatted_encoding

    def clean_non_ascii_chars(self, text) -> str:
        """Cleans non-ascii characters from unicode string.

        Example
        -------
        \x88This text contains non-ascii characters!\x88
            -> This text contains non-ascii characters!
        """
        en = text.encode("ascii", "ignore")
        return en.decode()

    def clean_bullets(self, text: str) -> str:
        """Cleans unicode bullets from a section of text.

        Example
        -------
        ●  This is an excellent point! -> This is an excellent point!
        """
        search = UNICODE_BULLETS_RE.match(text)
        if search is None:
            return text

        cleaned_text = UNICODE_BULLETS_RE.sub("", text, 1)
        return cleaned_text.strip()

    def clean_ordered_bullets(self, text) -> str:
        """Cleans the start of bulleted text sections up to three “sub-section”
        bullets accounting numeric and alphanumeric types.

        Example
        -------
        1.1 This is a very important point -> This is a very important point
        a.b This is a very important point -> This is a very important point
        """
        text_sp = text.split()
        text_cl = " ".join(text_sp[1:])
        if any(["." not in text_sp[0], ".." in text_sp[0]]):
            return text

        bullet = re.split(pattern=r"[\.]", string=text_sp[0])
        if not bullet[-1]:
            del bullet[-1]

        if len(bullet[0]) > 2:
            return text

        return text_cl

    def clean_ligatures(self, text) -> str:
        """Replaces ligatures with their most likely equivalent characters.

        Example
        -------
        The beneﬁts -> The benefits
        High quality ﬁnancial -> High quality financial
        """
        ligatures_map = {
            "æ": "ae",
            "Æ": "AE",
            "ﬀ": "ff",
            "ﬁ": "fi",
            "ﬂ": "fl",
            "ﬃ": "ffi",
            "ﬄ": "ffl",
            "ﬅ": "ft",
            "ʪ": "ls",
            "œ": "oe",
            "Œ": "OE",
            "ȹ": "qp",
            "ﬆ": "st",
            "ʦ": "ts",
        }
        cleaned_text: str = text
        for k, v in ligatures_map.items():
            cleaned_text = cleaned_text.replace(k, v)

        return cleaned_text

    def group_bullet_paragraph(self, paragraph: str) -> list:
        """Groups paragraphs with bullets that have line breaks for visual/formatting purposes.
        For example:

        '''○ The big red fox
        is walking down the lane.

        ○ At the end of the lane
        the fox met a friendly bear.'''

        Gets converted to

        '''○ The big red fox is walking down the lane.
        ○ At the end of the land the fox met a bear.'''
        """
        clean_paragraphs = []
        # pytesseract converts some bullet points to standalone "e" characters.
        # Substitute "e" with bullets since they are later used in partition_text
        # to determine list element type.
        paragraph = (re.sub(E_BULLET_PATTERN, "·", paragraph)).strip()

        bullet_paras = re.split(UNICODE_BULLETS_RE_0W, paragraph)
        for bullet in bullet_paras:
            if bullet:
                clean_paragraphs.append(re.sub(PARAGRAPH_PATTERN, " ", bullet))
        return clean_paragraphs

    def group_broken_paragraphs(
        self,
        text: str,
        line_split: re.Pattern[str] = PARAGRAPH_PATTERN_RE,
        paragraph_split: re.Pattern[str] = DOUBLE_PARAGRAPH_PATTERN_RE,
    ) -> str:
        """Groups paragraphs that have line breaks for visual/formatting purposes.
        For example:

        '''The big red fox
        is walking down the lane.

        At the end of the lane
        the fox met a bear.'''

        Gets converted to

        '''The big red fox is walking down the lane.
        At the end of the land the fox met a bear.'''
        """
        paragraphs = paragraph_split.split(text)
        clean_paragraphs = []
        for paragraph in paragraphs:
            if not paragraph.strip():
                continue
            # NOTE(robinson) - This block is to account for lines like the following that shouldn't be
            # grouped together, but aren't separated by a double line break.
            #     Apache License
            #     Version 2.0, January 2004
            #     http://www.apache.org/licenses/
            para_split = line_split.split(paragraph)
            all_lines_short = all(len(line.strip().split(" ")) < 5 for line in para_split)
            contains_sentence_punctuation = any(
                SENTENCE_PUNCT_RE.search(line.strip()) for line in para_split if line.strip()
            )
            # pytesseract converts some bullet points to standalone "e" characters
            if UNICODE_BULLETS_RE.match(paragraph.strip()) or E_BULLET_PATTERN.match(
                paragraph.strip()
            ):
                clean_paragraphs.extend(self.group_bullet_paragraph(paragraph))
            elif all_lines_short and not contains_sentence_punctuation:
                clean_paragraphs.extend([line for line in para_split if line.strip()])
            else:
                clean_paragraphs.append(re.sub(PARAGRAPH_PATTERN, " ", paragraph))

        return "\n\n".join(clean_paragraphs)

    def new_line_grouper(
        self,
        text: str,
        paragraph_split: re.Pattern[str] = LINE_BREAK_RE,
    ) -> str:
        """
        Concatenates text document that has one-line paragraph break pattern

        For example,

        Iwan Roberts
        Roberts celebrating after scoring a goal for Norwich City
        in 2004

        Will be returned as:

        Iwan Roberts\n\nRoberts celebrating after scoring a goal for Norwich City\n\nin 2004
        """
        paragraphs = paragraph_split.split(text)
        clean_paragraphs = []
        for paragraph in paragraphs:
            if not paragraph.strip():
                continue
            clean_paragraphs.append(paragraph)
        return "\n\n".join(clean_paragraphs)

    def blank_line_grouper(
        self,
        text: str,
        paragraph_split: re.Pattern = DOUBLE_PARAGRAPH_PATTERN_RE,
    ) -> str:
        """
        Concatenates text document that has blank-line paragraph break pattern

        For example,

        Vestibulum auctor dapibus neque.

        Nunc dignissim risus id metus.

        Will be returned as:

        Vestibulum auctor dapibus neque.\n\nNunc dignissim risus id metus.\n\n

        """
        return self.group_broken_paragraphs(text)

    def auto_paragraph_grouper(
        self,
        text: str,
        line_split: re.Pattern[str] = LINE_BREAK_RE,
        max_line_count: int = 2000,
        threshold: float = 0.1,
    ) -> str:
        """
        Checks the ratio of new line (\n) over the total max_line_count

        If the ratio of new line is less than the threshold,
        the document is considered a new-line grouping type
        and return the original text

        If the ratio of new line is greater than or equal to the threshold,
        the document is considered a blank-line grouping type
        and passed on to blank_line_grouper function
        """
        lines = line_split.split(text)
        max_line_count = min(len(lines), max_line_count)
        line_count, empty_line_count = 0, 0
        for line in lines[:max_line_count]:
            line_count += 1
            if not line.strip():
                empty_line_count += 1
        ratio = empty_line_count / line_count

        # NOTE(klaijan) - for ratio < threshold, we pass to new-line grouper,
        # otherwise to blank-line grouper
        if ratio < threshold:
            return self.new_line_grouper(text)
        else:
            return self.blank_line_grouper(text)

    # TODO(robinson) - There's likely a cleaner was to accomplish this and get all of the
    # unicode characters instead of just the quotes. Doing this for now since quotes are
    # an issue that are popping up in the SEC filings tests. Ideally this would be
    # replaced with a small regex-based normaliser that handles a wider variety of
    # smart punctuation.
    def replace_unicode_quotes(self, text: str) -> str:
        """Replaces unicode bullets in text with the expected character

        Example
        -------
        \x93What a lovely quote!\x94 -> “What a lovely quote!”
        """
        # NOTE(robinson) - We should probably make this something more sane like a regex
        # instead of a whole big series of replaces
        text = text.replace("\x91", "‘")
        text = text.replace("\x92", "’")
        text = text.replace("\x93", "“")
        text = text.replace("\x94", "”")
        text = text.replace("&apos;", "'")
        text = text.replace("â\x80\x99", "'")
        text = text.replace("â\x80“", "—")
        text = text.replace("â\x80”", "–")
        text = text.replace("â\x80˜", "‘")
        text = text.replace("â\x80¦", "…")
        text = text.replace("â\x80™", "’")
        text = text.replace("â\x80œ", "“")
        text = text.replace("â\x80?", "”")
        text = text.replace("â\x80ť", "”")
        text = text.replace("â\x80ś", "“")
        text = text.replace("â\x80¨", "—")
        text = text.replace("â\x80ł", "″")
        text = text.replace("â\x80Ž", "")
        text = text.replace("â\x80‚", "")
        text = text.replace("â\x80‰", "")
        text = text.replace("â\x80‹", "")
        text = text.replace("â\x80", "")
        text = text.replace("â\x80s'", "")
        return text

    def remove_punctuation(self, s: str) -> str:
        """Removes punctuation from a given string."""
        s = s.translate(tbl)
        return s

    def remove_sentence_punctuation(self, s: str, exclude_punctuation: list | None) -> str:
        tbl_new = tbl.copy()
        if exclude_punctuation:
            for punct in exclude_punctuation:
                tbl_new.pop(ord(punct), None)
        s = s.translate(tbl_new)
        return s

    def clean_extra_whitespace(self, text: str) -> str:
        """Cleans extra whitespace characters that appear between words.

        Example
        -------
        ITEM 1.     BUSINESS -> ITEM 1. BUSINESS
        """
        cleaned_text = re.sub(r"[\xa0\n]", " ", text)
        cleaned_text = re.sub(r"([ ]{2,})", " ", cleaned_text)
        return cleaned_text.strip()

    def clean_dashes(self, text: str) -> str:
        """Cleans dash characters in text.

        Example
        -------
        ITEM 1. -BUSINESS -> ITEM 1.  BUSINESS
        """
        # NOTE(Yuming): '\u2013' is the unicode string of 'EN DASH', a variation of "-"
        return re.sub(r"[-\u2013]", " ", text).strip()

    def clean_trailing_punctuation(self, text: str) -> str:
        """Clean all trailing punctuation in text

        Example
        -------
        ITEM 1.     BUSINESS. -> ITEM 1.     BUSINESS
        """
        return text.strip().rstrip(".,:;")

    def replace_mime_encodings(self, text: str, encoding: str = "utf-8") -> str:
        """Replaces MIME encodings with their equivalent characters in the specified encoding.

        Example
        -------
        5 w=E2=80-99s -> 5 w’s
        """
        formatted_encoding = self.format_encoding_str(encoding)
        return quopri.decodestring(text.encode(formatted_encoding)).decode(formatted_encoding)

    def clean_prefix(
        self, text: str, pattern: str, ignore_case: bool = False, strip: bool = True
    ) -> str:
        """Removes prefixes from a string according to the specified pattern. Strips leading
        whitespace if the strip parameter is set to True.

        Input
        -----
        text: The text to clean
        pattern: The pattern for the prefix. Can be a simple string or a regex pattern
        ignore_case: If True, ignores case in the pattern
        strip: If True, removes leading whitespace from the cleaned string.
        """
        flags = re.IGNORECASE if ignore_case else 0
        clean_text = re.sub(rf"^{pattern}", "", text, flags=flags)
        clean_text = clean_text.lstrip() if strip else clean_text
        return clean_text

    def clean_postfix(
        self, text: str, pattern: str, ignore_case: bool = False, strip: bool = True
    ) -> str:
        """Removes postfixes from a string according to the specified pattern. Strips trailing
        whitespace if the strip parameters is set to True.

        Input
        -----
        text: The text to clean
        pattern: The pattern for the postfix. Can be a simple string or a regex pattern
        ignore_case: If True, ignores case in the pattern
        strip: If True, removes trailing whitespace from the cleaned string.
        """
        flags = re.IGNORECASE if ignore_case else 0
        clean_text = re.sub(rf"{pattern}$", "", text, flags=flags)
        clean_text = clean_text.rstrip() if strip else clean_text
        return clean_text

    def clean(
        self,
        text: str,
        extra_whitespace: bool = False,
        dashes: bool = False,
        bullets: bool = False,
        trailing_punctuation: bool = False,
        lowercase: bool = False,
    ) -> str:
        """Cleans text.

        Input
        -----
        extra_whitespace: Whether to clean extra whitespace characters in text.
        dashes: Whether to clean dash characters in text.
        bullets: Whether to clean unicode bullets from a section of text.
        trailing_punctuation: Whether to clean all trailing punctuation in text.
        lowercase: Whether to return lowercase text.
        """

        cleaned_text = text.lower() if lowercase else text
        cleaned_text = (
            self.clean_trailing_punctuation(cleaned_text) if trailing_punctuation else cleaned_text
        )
        cleaned_text = self.clean_dashes(cleaned_text) if dashes else cleaned_text
        cleaned_text = (
            self.clean_extra_whitespace(cleaned_text) if extra_whitespace else cleaned_text
        )
        cleaned_text = self.clean_bullets(cleaned_text) if bullets else cleaned_text
        return cleaned_text.strip()

    def bytes_string_to_string(self, text: str, encoding: str = "utf-8"):
        """Converts a string representation of a byte string to a regular string using the
        specified encoding."""
        text_bytes = bytes([ord(char) for char in text])
        formatted_encoding = self.format_encoding_str(encoding)
        return text_bytes.decode(formatted_encoding)

    def clean_extra_whitespace_with_index_run(self, text: str) -> tuple[str, np.ndarray]:
        """Cleans extra whitespace characters that appear between words.
        Calculate distance between characters of original text and cleaned text.

        Returns cleaned text along with array of indices it has moved from original.

        Example
        -------
        ITEM 1.     BUSINESS -> ITEM 1. BUSINESS
        array([0., 0., 0., 0., 0., 0., 0., 0., 4., 4., 4., 4., 4., 4., 4., 4., 4., 4., 4., 4.]))
        """

        cleaned_text = re.sub(r"[\xa0\n]", " ", text)
        cleaned_text = re.sub(r"([ ]{2,})", " ", cleaned_text)

        cleaned_text = cleaned_text.strip()

        moved_indices = np.zeros(len(text))

        distance, original_index, cleaned_index = 0, 0, 0
        while cleaned_index < len(cleaned_text):
            if text[original_index] == cleaned_text[cleaned_index] or (
                bool(re.match("[\xa0\n]", text[original_index]))
                and bool(re.match(" ", cleaned_text[cleaned_index]))
            ):
                moved_indices[cleaned_index] = distance
                original_index += 1
                cleaned_index += 1
                continue

            distance += 1
            moved_indices[cleaned_index] = distance
            original_index += 1

        moved_indices[cleaned_index:] = distance

        return cleaned_text, moved_indices

    def index_adjustment_after_clean_extra_whitespace(index, moved_indices) -> int:
        return int(index - moved_indices[index])

    def __or__(self, other: str) -> str:
        """Format a string using the given other string as a template."""
        if not isinstance(other, str):
            raise TypeError(f"Expected a string, got {type(other).__name__}")
        return self.unindent(other)


string = StringFormatter()

unindent = string.unindent
remove_all_indents = string.remove_all_indents
undent = string.undent
clean_non_ascii_chars = string.clean_non_ascii_chars
clean_bullets = string.clean_bullets
clean_ordered_bullets = string.clean_ordered_bullets
clean_ligatures = string.clean_ligatures
group_bullet_paragraph = string.group_bullet_paragraph
group_broken_paragraphs = string.group_broken_paragraphs
auto_paragraph_grouper = string.auto_paragraph_grouper
replace_unicode_quotes = string.replace_unicode_quotes
clean_extra_whitespace = string.clean_extra_whitespace
clean_dashes = string.clean_dashes
clean_trailing_punctuation = string.clean_trailing_punctuation
replace_mime_encodings = string.replace_mime_encodings
clean_prefix = string.clean_prefix
clean_postfix = string.clean_postfix
clean = string.clean
bytes_string_to_string = string.bytes_string_to_string
clean_extra_whitespace_with_index_run = string.clean_extra_whitespace_with_index_run
index_adjustment_after_clean_extra_whitespace = string.index_adjustment_after_clean_extra_whitespace


# __all__ = ["string"]
