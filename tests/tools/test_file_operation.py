import shutil

import pytest

from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.tools.file_operation import FileOperationTool
from tests.test_utils import test_project_paths
from tests.test_utils.fixtures import temp_test_dir  # noqa: F401


@pytest.fixture(scope="function")
async def knowledge_graph_fixture(temp_test_dir):  # noqa: F811
    if temp_test_dir.exists():
        shutil.rmtree(temp_test_dir)
    shutil.copytree(test_project_paths.TEST_PROJECT_PATH, temp_test_dir)
    kg = KnowledgeGraph(1, 1000, 100, 0)
    await kg.build_graph(temp_test_dir)
    return kg


@pytest.fixture(scope="function")
def file_operation_tool(temp_test_dir, knowledge_graph_fixture):  # noqa: F811
    file_operation = FileOperationTool(temp_test_dir, knowledge_graph_fixture)
    return file_operation


def test_read_file_with_knowledge_graph_data(file_operation_tool):
    relative_path = str(
        test_project_paths.PYTHON_FILE.relative_to(test_project_paths.TEST_PROJECT_PATH).as_posix()
    )
    result = file_operation_tool.read_file_with_knowledge_graph_data(relative_path)
    result_data = result[1]
    assert len(result_data) > 0
    for result_row in result_data:
        assert "preview" in result_row
        assert 'print("Hello world!")' in result_row["preview"].get("text", "")
        assert "FileNode" in result_row
        assert result_row["FileNode"].get("relative_path", "") == relative_path


def test_create_and_read_file(temp_test_dir, file_operation_tool):  # noqa: F811
    """Test creating a file and reading its contents."""
    test_file = temp_test_dir / "test.txt"
    content = "line 1\nline 2\nline 3"

    # Test create_file
    result = file_operation_tool.create_file("test.txt", content)
    assert test_file.exists()
    assert test_file.read_text() == content
    assert result == "The file test.txt has been created."

    # Test read_file
    result = file_operation_tool.read_file("test.txt")
    expected = "1. line 1\n2. line 2\n3. line 3"
    assert result == expected


def test_read_file_nonexistent(file_operation_tool):
    """Test reading a nonexistent file."""
    result = file_operation_tool.read_file("nonexistent_file.txt")
    assert result == "The file nonexistent_file.txt does not exist."


def test_read_file_with_line_numbers(file_operation_tool):
    """Test reading specific line ranges from a file."""
    content = "line 1\nline 2\nline 3\nline 4\nline 5"
    file_operation_tool.create_file("test_lines.txt", content)

    # Test reading specific lines
    result = file_operation_tool.read_file_with_line_numbers("test_lines.txt", 2, 4)
    expected = "2. line 2\n3. line 3"
    assert result == expected

    # Test invalid range
    result = file_operation_tool.read_file_with_line_numbers("test_lines.txt", 4, 2)
    assert result == "The end line number 2 must be greater than the start line number 4."


def test_delete(file_operation_tool, temp_test_dir):  # noqa: F811
    """Test file and directory deletion."""
    # Test file deletion
    test_file = temp_test_dir / "to_delete.txt"
    file_operation_tool.create_file("to_delete.txt", "content")
    assert test_file.exists()
    result = file_operation_tool.delete("to_delete.txt")
    assert result == "The file to_delete.txt has been deleted."
    assert not test_file.exists()

    # Test directory deletion
    test_subdir = temp_test_dir / "subdir"
    test_subdir.mkdir()
    file_operation_tool.create_file("subdir/file.txt", "content")
    result = file_operation_tool.delete("subdir")
    assert result == "The directory subdir has been deleted."
    assert not test_subdir.exists()


def test_delete_nonexistent(file_operation_tool):
    """Test deleting a nonexistent path."""
    result = file_operation_tool.delete("nonexistent_path")
    assert result == "The file nonexistent_path does not exist."


def test_edit_file(file_operation_tool):
    """Test editing specific lines in a file."""
    # Test case 1: Successfully edit a single occurrence
    initial_content = "line 1\nline 2\nline 3\nline 4\nline 5"
    file_operation_tool.create_file("edit_test.txt", initial_content)
    result = file_operation_tool.edit_file("edit_test.txt", "line 2", "new line 2")
    assert result == "Successfully edited edit_test.txt."

    # Test case 2: Absolute path error
    result = file_operation_tool.edit_file("/edit_test.txt", "line 2", "new line 2")
    assert result == "relative_path: /edit_test.txt is a absolute path, not relative path."

    # Test case 3: File doesn't exist
    result = file_operation_tool.edit_file("nonexistent.txt", "line 2", "new line 2")
    assert result == "The file nonexistent.txt does not exist."

    # Test case 4: No matches found
    result = file_operation_tool.edit_file("edit_test.txt", "nonexistent line", "new content")
    assert (
        result
        == "No match found for the specified content in edit_test.txt. Please verify the content to replace."
    )

    # Test case 5: Multiple occurrences
    duplicate_content = "line 1\nline 2\nline 2\nline 3"
    file_operation_tool.create_file("duplicate_test.txt", duplicate_content)
    result = file_operation_tool.edit_file("duplicate_test.txt", "line 2", "new line 2")
    assert (
        result
        == "Found 2 occurrences of the specified content in duplicate_test.txt. Please provide more context to ensure a unique match."
    )


def test_create_file_already_exists(file_operation_tool):
    """Test creating a file that already exists."""
    file_operation_tool.create_file("existing.txt", "content")
    result = file_operation_tool.create_file("existing.txt", "new content")
    assert result == "The file existing.txt already exists."
