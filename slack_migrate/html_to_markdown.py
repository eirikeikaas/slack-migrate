from html.parser import HTMLParser

_HEADINGS = {"h1": "# ", "h2": "## ", "h3": "### "}


class _Converter(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.list_stack = []  # "ul" / "ol" with counters
        self.href = None

    def _newline(self):
        if self.out and not self.out[-1].endswith("\n"):
            self.out.append("\n")

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in _HEADINGS:
            self._newline()
            self.out.append(_HEADINGS[tag])
        elif tag in ("ul", "ol"):
            self.list_stack.append([tag, 0])
        elif tag == "li":
            self._newline()
            kind = self.list_stack[-1] if self.list_stack else ["ul", 0]
            kind[1] += 1
            indent = "  " * max(len(self.list_stack) - 1, 0)
            marker = f"{kind[1]}. " if kind[0] == "ol" else "- "
            self.out.append(indent + marker)
        elif tag in ("b", "strong"):
            self.out.append("**")
        elif tag in ("i", "em"):
            self.out.append("_")
        elif tag == "a":
            self.href = attrs.get("href")
            self.out.append("[")
        elif tag == "br":
            self.out.append("\n")
        elif tag == "input" and attrs.get("type") == "checkbox":
            self.out.append("[x] " if "checked" in attrs else "[ ] ")
        elif tag == "p":
            self._newline()

    def handle_endtag(self, tag):
        if tag in _HEADINGS or tag in ("p", "li"):
            self._newline()
            if tag != "li":
                self.out.append("\n")
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
            if not self.list_stack:
                self.out.append("\n")
        elif tag in ("b", "strong"):
            self.out.append("**")
        elif tag in ("i", "em"):
            self.out.append("_")
        elif tag == "a":
            self.out.append(f"]({self.href})" if self.href else "]")
            self.href = None

    def handle_data(self, data):
        text = data.replace("\n", " ")
        if not text.strip():
            if self.out and not self.out[-1].endswith(("\n", " ")):
                self.out.append(" ")
            return
        self.out.append(text)


def html_to_markdown(html):
    """Convert Slack canvas HTML to markdown.

    Supports headings, paragraphs, bold/italic, links, ordered/unordered
    (nested) lists and checklists. Other elements degrade to plain text.
    """
    converter = _Converter()
    converter.feed(html)
    text = "".join(converter.out)
    lines = [line.rstrip() for line in text.splitlines()]
    result = "\n".join(lines)
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")
    return result.strip() + "\n"
