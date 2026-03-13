"""
Tests for LLM output sanitization — ensures XSS and injection vectors are stripped.
"""
from __future__ import annotations

import pytest

from ui.theme import sanitize_llm_output


class TestSanitizeLLMOutput:
    def test_plain_text_unchanged(self):
        text = "This is a normal response about Python programming."
        assert sanitize_llm_output(text) == text

    def test_markdown_preserved(self):
        text = "**Bold** and *italic* and `code` and [link](http://example.com)"
        assert sanitize_llm_output(text) == text

    def test_code_block_preserved(self):
        text = "```python\nprint('hello')\n```"
        assert sanitize_llm_output(text) == text

    def test_script_tag_removed(self):
        text = "Hello <script>alert('xss')</script> world"
        result = sanitize_llm_output(text)
        assert "<script" not in result.lower()
        assert "alert" not in result

    def test_script_tag_multiline(self):
        text = "Hello <script type='text/javascript'>\nalert('xss');\n</script> world"
        result = sanitize_llm_output(text)
        assert "<script" not in result.lower()

    def test_iframe_removed(self):
        text = "Check this: <iframe src='http://evil.com'></iframe>"
        result = sanitize_llm_output(text)
        assert "<iframe" not in result.lower()

    def test_self_closing_iframe(self):
        text = "Check this: <iframe src='http://evil.com'/>"
        result = sanitize_llm_output(text)
        assert "<iframe" not in result.lower()

    def test_object_tag_removed(self):
        text = "<object data='evil.swf'></object>"
        result = sanitize_llm_output(text)
        assert "<object" not in result.lower()

    def test_embed_tag_removed(self):
        text = "<embed src='evil.swf'>"
        result = sanitize_llm_output(text)
        assert "<embed" not in result.lower()

    def test_form_tag_removed(self):
        text = "<form action='http://evil.com'><input></form>"
        result = sanitize_llm_output(text)
        assert "<form" not in result.lower()

    def test_event_handler_onclick(self):
        text = '<div onclick="alert(1)">Click me</div>'
        result = sanitize_llm_output(text)
        assert "onclick" not in result.lower()

    def test_event_handler_onerror(self):
        text = '<img src=x onerror="alert(1)">'
        result = sanitize_llm_output(text)
        assert "onerror" not in result.lower()

    def test_event_handler_onload(self):
        text = '<body onload="alert(1)">'
        result = sanitize_llm_output(text)
        assert "onload" not in result.lower()

    def test_javascript_url(self):
        text = '<a href="javascript:alert(1)">click</a>'
        result = sanitize_llm_output(text)
        assert "javascript:" not in result.lower()

    def test_data_url_html(self):
        text = '<a href="data:text/html,<script>alert(1)</script>">click</a>'
        result = sanitize_llm_output(text)
        assert "data:text/html" not in result.lower()

    def test_non_string_input(self):
        assert sanitize_llm_output(42) == "42"
        assert sanitize_llm_output(None) == "None"

    def test_empty_string(self):
        assert sanitize_llm_output("") == ""

    def test_link_tag_removed(self):
        text = '<link rel="stylesheet" href="http://evil.com/evil.css">'
        result = sanitize_llm_output(text)
        assert "<link" not in result.lower()

    def test_meta_tag_removed(self):
        text = '<meta http-equiv="refresh" content="0;url=http://evil.com">'
        result = sanitize_llm_output(text)
        assert "<meta" not in result.lower()
