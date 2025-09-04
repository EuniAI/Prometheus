import pytest

from prometheus.graph.knowledge_graph import KnowledgeGraph
from prometheus.tools import graph_traversal
from tests.test_utils import test_project_paths


@pytest.fixture(scope="function")
async def knowledge_graph_fixture():
    kg = KnowledgeGraph(1000, 100, 10, 0)
    await kg.build_graph(test_project_paths.TEST_PROJECT_PATH)
    return kg


@pytest.mark.slow
async def test_find_file_node_with_basename(knowledge_graph_fixture):
    result = graph_traversal.find_file_node_with_basename(
        test_project_paths.PYTHON_FILE.name, knowledge_graph_fixture
    )

    basename = test_project_paths.PYTHON_FILE.name
    relative_path = str(
        test_project_paths.PYTHON_FILE.relative_to(test_project_paths.TEST_PROJECT_PATH).as_posix()
    )

    result_data = result[1]
    assert len(result_data) == 1
    assert "FileNode" in result_data[0]
    assert result_data[0]["FileNode"].get("basename", "") == basename
    assert result_data[0]["FileNode"].get("relative_path", "") == relative_path


@pytest.mark.slow
async def test_find_file_node_with_relative_path(knowledge_graph_fixture):
    relative_path = str(
        test_project_paths.MD_FILE.relative_to(test_project_paths.TEST_PROJECT_PATH).as_posix()
    )
    result = graph_traversal.find_file_node_with_relative_path(
        relative_path, knowledge_graph_fixture
    )

    basename = test_project_paths.MD_FILE.name

    result_data = result[1]
    assert len(result_data) == 1
    assert "FileNode" in result_data[0]
    assert result_data[0]["FileNode"].get("basename", "") == basename
    assert result_data[0]["FileNode"].get("relative_path", "") == relative_path


@pytest.mark.slow
async def test_find_ast_node_with_text_in_file_with_basename(knowledge_graph_fixture):  # noqa: F811
    basename = test_project_paths.PYTHON_FILE.name
    result = graph_traversal.find_ast_node_with_text_in_file_with_basename(
        "Hello world!", basename, knowledge_graph_fixture
    )

    result_data = result[1]
    assert len(result_data) > 0
    for result_row in result_data:
        assert "ASTNode" in result_row
        assert "Hello world!" in result_row["ASTNode"].get("text", "")
        assert "FileNode" in result_row
        assert result_row["FileNode"].get("basename", "") == basename


@pytest.mark.slow
async def test_find_ast_node_with_text_in_file_with_relative_path(knowledge_graph_fixture):
    relative_path = str(
        test_project_paths.C_FILE.relative_to(test_project_paths.TEST_PROJECT_PATH).as_posix()
    )
    result = graph_traversal.find_ast_node_with_text_in_file_with_relative_path(
        "Hello world!", relative_path, knowledge_graph_fixture
    )

    result_data = result[1]
    assert len(result_data) > 0
    for result_row in result_data:
        assert "ASTNode" in result_row
        assert "Hello world!" in result_row["ASTNode"].get("text", "")
        assert "FileNode" in result_row
        assert result_row["FileNode"].get("relative_path", "") == relative_path


@pytest.mark.slow
async def test_find_ast_node_with_type_in_file_with_basename(knowledge_graph_fixture):
    basename = test_project_paths.C_FILE.name
    node_type = "function_definition"
    result = graph_traversal.find_ast_node_with_type_in_file_with_basename(
        node_type, basename, knowledge_graph_fixture
    )

    result_data = result[1]
    assert len(result_data) > 0
    for result_row in result_data:
        assert "ASTNode" in result_row
        assert result_row["ASTNode"].get("type", "") == node_type
        assert "FileNode" in result_row
        assert result_row["FileNode"].get("basename", "") == basename


@pytest.mark.slow
async def test_find_ast_node_with_type_in_file_with_relative_path(knowledge_graph_fixture):  # noqa: F811
    relative_path = str(
        test_project_paths.JAVA_FILE.relative_to(test_project_paths.TEST_PROJECT_PATH).as_posix()
    )
    node_type = "string_literal"
    result = graph_traversal.find_ast_node_with_type_in_file_with_relative_path(
        node_type, relative_path, knowledge_graph_fixture
    )

    result_data = result[1]
    assert len(result_data) > 0
    for result_row in result_data:
        assert "ASTNode" in result_row
        assert result_row["ASTNode"].get("type", "") == node_type
        assert "FileNode" in result_row
        assert result_row["FileNode"].get("relative_path", "") == relative_path


@pytest.mark.slow
async def test_find_text_node_with_text(knowledge_graph_fixture):
    text = "Text under header C"
    result = graph_traversal.find_text_node_with_text(text, knowledge_graph_fixture)

    result_data = result[1]
    assert len(result_data) > 0
    for result_row in result_data:
        assert "TextNode" in result_row
        assert text in result_row["TextNode"].get("text", "")
        assert "start_line" in result_row["TextNode"]
        assert result_row["TextNode"]["start_line"] == 1
        assert "end_line" in result_row["TextNode"]
        assert result_row["TextNode"]["end_line"] == 13
        assert "FileNode" in result_row
        assert result_row["FileNode"].get("relative_path", "") == "foo/test.md"


@pytest.mark.slow
async def test_find_text_node_with_text_in_file(knowledge_graph_fixture):
    basename = test_project_paths.MD_FILE.name
    text = "Text under header B"
    result = graph_traversal.find_text_node_with_text_in_file(
        text, basename, knowledge_graph_fixture
    )

    result_data = result[1]
    assert len(result_data) > 0
    for result_row in result_data:
        assert "TextNode" in result_row
        assert text in result_row["TextNode"].get("text", "")
        assert "start_line" in result_row["TextNode"]
        assert result_row["TextNode"]["start_line"] == 1
        assert "end_line" in result_row["TextNode"]
        assert result_row["TextNode"]["end_line"] == 13
        assert "FileNode" in result_row
        assert result_row["FileNode"].get("basename", "") == basename


@pytest.mark.slow
async def test_get_next_text_node_with_node_id(knowledge_graph_fixture):
    node_id = 34
    result = graph_traversal.get_next_text_node_with_node_id(node_id, knowledge_graph_fixture)

    result_data = result[1]
    assert len(result_data) > 0
    for result_row in result_data:
        assert "TextNode" in result_row
        assert "Text under header D" in result_row["TextNode"].get("text", "")
        assert "start_line" in result_row["TextNode"]
        assert result_row["TextNode"]["start_line"] == 13
        assert "end_line" in result_row["TextNode"]
        assert result_row["TextNode"]["end_line"] == 15
        assert "FileNode" in result_row
        assert result_row["FileNode"].get("relative_path", "") == "foo/test.md"


@pytest.mark.slow
async def test_read_code_with_relative_path(knowledge_graph_fixture):  # noqa: F811
    relative_path = str(
        test_project_paths.C_FILE.relative_to(test_project_paths.TEST_PROJECT_PATH).as_posix()
    )
    result = graph_traversal.read_code_with_relative_path(
        relative_path, 5, 6, knowledge_graph_fixture
    )

    result_data = result[1]
    assert len(result_data) > 0
    for result_row in result_data:
        assert "SelectedLines" in result_row
        assert "return 0;" in result_row["SelectedLines"].get("text", "")
        assert "FileNode" in result_row
        assert result_row["FileNode"].get("relative_path", "") == relative_path
