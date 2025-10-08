from prometheus.utils.str_util import (
    pre_append_line_numbers,
)


def test_single_line():
    text = "Hello world"
    result = pre_append_line_numbers(text, start_line=1)
    assert result == "1. Hello world"


def test_multiple_lines():
    text = "First line\nSecond line\nThird line"
    result = pre_append_line_numbers(text, start_line=1)
    assert result == "1. First line\n2. Second line\n3. Third line"


def test_empty_string():
    text = ""
    result = pre_append_line_numbers(text, start_line=1)
    assert result == ""
