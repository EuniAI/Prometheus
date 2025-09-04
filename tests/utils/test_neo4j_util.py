from unittest.mock import MagicMock

import pytest

from prometheus.utils.knowledge_graph_utils import (
    EMPTY_DATA_MESSAGE,
    format_knowledge_graph_data,
    knowledge_graph_data_for_context_generator,
)


class MockResult:
    def __init__(self, data_list):
        self._data = data_list

    def data(self):
        return self._data


class MockSession:
    def __init__(self):
        self.execute_read = MagicMock()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class MockDriver:
    def __init__(self, session):
        self._session = session

    def session(self):
        return self._session


@pytest.fixture
def mock_neo4j_driver():
    session = MockSession()
    driver = MockDriver(session)
    return driver, session


def test_format_neo4j_data_single_row():
    data = [{"name": "John", "age": 30}]

    formatted = format_knowledge_graph_data(data)
    expected = "Result 1:\nage: 30\nname: John"

    assert formatted == expected


def test_format_neo4j_result_multiple_rows():
    data = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]

    formatted = format_knowledge_graph_data(data)
    expected = "Result 1:\nage: 30\nname: John\n\n\nResult 2:\nage: 25\nname: Jane"

    assert formatted == expected


def test_format_neo4j_result_empty():
    data = []
    formatted = format_knowledge_graph_data(data)
    assert formatted == EMPTY_DATA_MESSAGE


def test_format_neo4j_result_different_keys():
    data = [{"name": "John", "age": 30}, {"city": "New York", "country": "USA"}]

    formatted = format_knowledge_graph_data(data)
    expected = "Result 1:\nage: 30\nname: John\n\n\nResult 2:\ncity: New York\ncountry: USA"

    assert formatted == expected


def test_format_neo4j_result_complex_values():
    data = [
        {"numbers": [1, 2, 3], "metadata": {"type": "user", "active": True}, "date": "2024-01-01"}
    ]

    formatted = format_knowledge_graph_data(data)
    expected = "Result 1:\ndate: 2024-01-01\nmetadata: {'type': 'user', 'active': True}\nnumbers: [1, 2, 3]"

    assert formatted == expected


def mock_file_node_data():
    return [{"FileNode": {"basename": "test.py", "relative_path": "bar/test.py", "node_id": 37}}]


def mock_ast_node_data():
    return [
        {
            "FileNode": {"basename": "test.py", "relative_path": "bar/test.py", "node_id": 37},
            "ASTNode": {
                "start_line": 1,
                "text": "Hello world!",
                "type": "string_content",
                "end_line": 1,
                "node_id": 47,
            },
        },
        {
            "FileNode": {"basename": "test.py", "relative_path": "bar/test.py", "node_id": 37},
            "ASTNode": {
                "start_line": 1,
                "text": '"Hello world!"',
                "type": "string",
                "end_line": 1,
                "node_id": 44,
            },
        },
        {
            "FileNode": {"basename": "test.py", "relative_path": "bar/test.py", "node_id": 37},
            "ASTNode": {
                "start_line": 1,
                "text": '("Hello world!")',
                "type": "argument_list",
                "end_line": 1,
                "node_id": 42,
            },
        },
        {
            "FileNode": {"basename": "test.py", "relative_path": "bar/test.py", "node_id": 37},
            "ASTNode": {
                "start_line": 1,
                "text": 'print("Hello world!")',
                "type": "expression_statement",
                "end_line": 1,
                "node_id": 39,
            },
        },
        {
            "FileNode": {"basename": "test.py", "relative_path": "bar/test.py", "node_id": 37},
            "ASTNode": {
                "start_line": 1,
                "text": 'print("Hello world!")',
                "type": "call",
                "end_line": 1,
                "node_id": 40,
            },
        },
    ]


def mock_text_node_data():
    return [
        {
            "FileNode": {"basename": "test.md", "relative_path": "foo/test.md", "node_id": 33},
            "TextNode": {
                "metadata": "",
                "text": "# A\n\nText under header A.\n\n## B\n\nText under header B.\n\n## C\n\nText under header C.\n\n### D",
                "node_id": 34,
                "start_line": 1,
                "end_line": 15,
            },
        }
    ]


def mock_preview_file_data():
    return [
        {
            "FileNode": {"basename": "test.py", "relative_path": "bar/test.py", "node_id": 37},
            "preview": {"start_line": 1, "text": '1. print("Hello world!")', "end_line": 1},
        }
    ]


def mock_read_code_data():
    return [
        {
            "FileNode": {"basename": "test.java", "relative_path": "bar/test.java", "node_id": 36},
            "SelectedLines": {
                "start_line": 2,
                "text": "2.   public static void main(String[] args) {",
                "end_line": 3,
            },
        }
    ]


def test_neo4j_data_for_context_generator():
    # Get testing data
    data = [
        *mock_file_node_data(),
        *mock_ast_node_data(),
        *mock_text_node_data(),
        *mock_preview_file_data(),
        *mock_read_code_data(),
    ]

    # Call the target function
    result = list(knowledge_graph_data_for_context_generator(data))

    # Test the length of the result
    assert len(result) == 8

    # Check the contents of each Context object
    context_1 = result[0]
    assert context_1.relative_path == "bar/test.py"
    assert context_1.content == "Hello world!"
    assert context_1.start_line_number == 1
    assert context_1.end_line_number == 1

    context_2 = result[5]
    assert context_2.relative_path == "foo/test.md"
    assert (
        context_2.content
        == "# A\n\nText under header A.\n\n## B\n\nText under header B.\n\n## C\n\nText under header C.\n\n### D"
    )
    assert context_2.start_line_number == 1
    assert context_2.end_line_number == 15

    context_3 = result[6]
    assert context_3.relative_path == "bar/test.py"
    assert context_3.content == """1. print("Hello world!")"""
    assert context_3.start_line_number == 1
    assert context_3.end_line_number == 1

    context_4 = result[7]
    assert context_4.relative_path == "bar/test.java"
    assert context_4.content == "2.   public static void main(String[] args) {"
    assert context_4.start_line_number == 2
    assert context_4.end_line_number == 3
