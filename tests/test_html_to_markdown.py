from slack_migrate.html_to_markdown import html_to_markdown


def test_headings_and_formatting():
    md = html_to_markdown("<h1>Title</h1><p>Hello <b>big</b> <i>world</i></p>")
    assert md == "# Title\n\nHello **big** _world_\n"


def test_link():
    assert "[Slack](https://slack.com)" in html_to_markdown(
        '<p><a href="https://slack.com">Slack</a></p>')


def test_lists_and_checklist():
    md = html_to_markdown(
        "<ul><li>a</li><li>b<ol><li>c</li></ol></li></ul>"
        '<p><input type="checkbox" checked> done</p>')
    assert "- a" in md and "- b" in md
    assert "  1. c" in md
    assert "[x]" in md
