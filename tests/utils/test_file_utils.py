import pytest

from prometheus.exceptions.file_operation_exception import FileOperationException
from prometheus.utils.file_utils import (
    read_file_with_line_numbers,
)
from tests.test_utils.test_project_paths import TEST_PROJECT_PATH


def test_read_file_with_line_numbers():
    """Test reading specific line ranges from a file."""
    # Test reading specific lines
    result = read_file_with_line_numbers("foo/test.md", TEST_PROJECT_PATH, 1, 15)
    expected = """1. # A
2.
3. Text under header A.
4.
5. ## B
6.
7. Text under header B.
8.
9. ## C
10.
11. Text under header C.
12.
13. ### D
14.
15. Text under header D."""
    assert result == expected

    # Test invalid range should raise exception
    with pytest.raises(FileOperationException) as exc_info:
        read_file_with_line_numbers("foo/test.md", TEST_PROJECT_PATH, 4, 2)

    assert str(exc_info.value) == "The end line number must be greater than the start line number."
