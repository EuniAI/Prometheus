from unittest.mock import MagicMock

import pytest

from prometheus.utils.knowledge_graph_utils import (
    EMPTY_DATA_MESSAGE,
    format_knowledge_graph_data,
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
