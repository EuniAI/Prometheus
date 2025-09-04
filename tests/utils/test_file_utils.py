import pytest

from prometheus.exceptions.file_operation_exception import FileOperationException
from prometheus.utils.file_utils import (
    read_file_with_line_numbers,
)
from tests.test_utils.fixtures import temp_test_dir  # noqa: F401


def test_read_file_with_line_numbers(temp_test_dir):  # noqa: F811
    """Test reading specific line ranges from a file."""
    # Test reading specific lines
    result = read_file_with_line_numbers("foo/test.md", str(temp_test_dir), 1, 15)
    expected = "2. line 2\n3. line 3\n4. line 4"
    assert result == expected

    # Test invalid range should raise exception
    with pytest.raises(FileOperationException) as exc_info:
        read_file_with_line_numbers("test_lines.txt", str(temp_test_dir), 4, 2)

    assert str(exc_info.value) == "The end line number must be greater than the start line number."
