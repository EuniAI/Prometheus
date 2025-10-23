from pathlib import Path
from unittest.mock import MagicMock, create_autospec, mock_open, patch

import pytest
from tree_sitter._binding import Tree

from prometheus.parser.file_types import FileType
from prometheus.parser.tree_sitter_parser import (
    FILE_TYPE_TO_LANG,
    FileNotSupportedError,
    parse,
    supports_file,
)


# Test fixtures
@pytest.fixture
def mock_python_file():
    return Path("test.py")


@pytest.fixture
def mock_unsupported_file():
    return Path("test.unsupported")


@pytest.fixture
def mock_tree():
    tree = create_autospec(Tree, instance=True)
    return tree


# Test supports_file function
def test_supports_file_with_supported_type(mock_python_file):
    with patch("prometheus.parser.file_types.FileType.from_path") as mock_from_path:
        mock_from_path.return_value = FileType.PYTHON
        assert supports_file(mock_python_file) is True
        mock_from_path.assert_called_once_with(mock_python_file)


def test_supports_file_with_unsupported_type(mock_unsupported_file):
    with patch("prometheus.parser.file_types.FileType.from_path") as mock_from_path:
        mock_from_path.return_value = None
        assert supports_file(mock_unsupported_file) is False
        mock_from_path.assert_called_once_with(mock_unsupported_file)


def test_parse_python_file_successfully(mock_python_file, mock_tree):
    mock_content = b'print("hello")'
    m = mock_open(read_data=mock_content)

    with (
        patch("prometheus.parser.file_types.FileType.from_path") as mock_from_path,
        patch("prometheus.parser.tree_sitter_parser.get_parser") as mock_get_parser,
        patch.object(Path, "open", m),
    ):
        # Setup mocks
        mock_from_path.return_value = FileType.PYTHON
        mock_parser = mock_get_parser.return_value
        mock_parser.parse.return_value = mock_tree

        # Test parse function
        result = parse(mock_python_file)

        # Verify results and interactions
        assert result == mock_tree
        mock_from_path.assert_called_once_with(mock_python_file)
        mock_get_parser.assert_called_once_with("python")
        mock_parser.parse.assert_called_once_with(mock_content)


def test_parse_unsupported_file_raises_error(mock_unsupported_file):
    with pytest.raises(FileNotSupportedError):
        parse(mock_unsupported_file)


def test_parse_all_supported_languages():
    """Test that we can get parsers for all supported languages."""
    with patch("tree_sitter_language_pack.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_get_parser.return_value = mock_parser

        for lang in FILE_TYPE_TO_LANG.values():
            mock_get_parser(lang)
            mock_get_parser.assert_called_with(lang)
            mock_get_parser.reset_mock()
