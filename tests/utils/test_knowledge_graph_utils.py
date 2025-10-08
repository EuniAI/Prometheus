from prometheus.models.context import Context
from prometheus.utils.knowledge_graph_utils import (
    knowledge_graph_data_for_context_generator,
    sort_contexts,
)


def test_empty_data():
    """Test with None or empty data"""
    assert knowledge_graph_data_for_context_generator(None) == []
    assert knowledge_graph_data_for_context_generator([]) == []


def test_skip_empty_content():
    """Test that empty or whitespace-only content is skipped"""
    data = [
        {
            "FileNode": {"relative_path": "test.py"},
            "ASTNode": {"text": "", "start_line": 1, "end_line": 1},
        },
        {
            "FileNode": {"relative_path": "test.py"},
            "TextNode": {"text": "   \n\t  ", "start_line": 2, "end_line": 2},
        },
        {
            "FileNode": {"relative_path": "test.py"},
            "ASTNode": {"text": "valid content", "start_line": 3, "end_line": 3},
        },
    ]
    result = knowledge_graph_data_for_context_generator(data)
    assert len(result) == 1
    assert result[0].content == "valid content"


def test_deduplication_identical_content():
    """Test deduplication of identical content"""
    data = [
        {
            "FileNode": {"relative_path": "test.py"},
            "ASTNode": {"text": "def hello():", "start_line": 1, "end_line": 1},
        },
        {
            "FileNode": {"relative_path": "test.py"},
            "TextNode": {"text": "def hello():", "start_line": 1, "end_line": 1},
        },
    ]
    result = knowledge_graph_data_for_context_generator(data)
    assert len(result) == 1
    assert result[0].content == "def hello():"


def test_deduplication_content_containment():
    """Test deduplication when one content contains another"""
    data = [
        {
            "FileNode": {"relative_path": "test.py"},
            "ASTNode": {"text": "def hello():\n    print('world')", "start_line": 1, "end_line": 2},
        },
        {
            "FileNode": {"relative_path": "test.py"},
            "TextNode": {"text": "print('world')", "start_line": 2, "end_line": 2},
        },
    ]
    result = knowledge_graph_data_for_context_generator(data)
    assert len(result) == 1
    assert result[0].content == "def hello():\n    print('world')"


def test_deduplication_line_containment():
    """Test deduplication based on line number containment"""
    data = [
        {
            "FileNode": {"relative_path": "test.py"},
            "ASTNode": {"text": "function body", "start_line": 1, "end_line": 5},
        },
        {
            "FileNode": {"relative_path": "test.py"},
            "TextNode": {"text": "inner content", "start_line": 2, "end_line": 3},
        },
    ]
    result = knowledge_graph_data_for_context_generator(data)
    assert len(result) == 1
    assert result[0].content == "function body"
    assert result[0].start_line_number == 1
    assert result[0].end_line_number == 5


def test_different_files_no_deduplication():
    """Test that identical content in different files is not deduplicated"""
    data = [
        {
            "FileNode": {"relative_path": "file1.py"},
            "ASTNode": {"text": "def hello():", "start_line": 1, "end_line": 1},
        },
        {
            "FileNode": {"relative_path": "file2.py"},
            "ASTNode": {"text": "def hello():", "start_line": 1, "end_line": 1},
        },
    ]
    result = knowledge_graph_data_for_context_generator(data)
    assert len(result) == 2
    assert result[0].relative_path == "file1.py"
    assert result[1].relative_path == "file2.py"


def test_content_stripping():
    """Test that content is properly stripped of whitespace"""
    data = [
        {
            "FileNode": {"relative_path": "test.py"},
            "ASTNode": {"text": "  \n  def hello():  \n  ", "start_line": 1, "end_line": 1},
        }
    ]
    result = knowledge_graph_data_for_context_generator(data)
    assert len(result) == 1
    assert result[0].content == "def hello():"


def test_complex_deduplication_scenario():
    """Test complex scenario with multiple overlapping contexts"""
    data = [
        # Large context containing everything
        {
            "FileNode": {"relative_path": "test.py"},
            "ASTNode": {
                "text": "class MyClass:\n    def method1(self):\n        pass\n    def method2(self):\n        pass",
                "start_line": 1,
                "end_line": 5,
            },
        },
        # Smaller context contained within the large one
        {
            "FileNode": {"relative_path": "test.py"},
            "TextNode": {
                "text": "def method1(self):\n        pass",
                "start_line": 2,
                "end_line": 3,
            },
        },
        # Separate context in same file
        {
            "FileNode": {"relative_path": "test.py"},
            "SelectedLines": {"text": "# Comment at end", "start_line": 10, "end_line": 10},
        },
    ]
    result = knowledge_graph_data_for_context_generator(data)
    assert len(result) == 2  # Large context + separate comment
    assert "class MyClass:" in result[0].content
    assert result[1].content == "# Comment at end"


def test_sort_contexts_empty_list():
    """Test sorting an empty list"""
    result = sort_contexts([])
    assert result == []


def test_sort_contexts_by_relative_path():
    """Test sorting by relative path"""
    contexts = [
        Context(
            relative_path="src/z.py", content="content z", start_line_number=1, end_line_number=5
        ),
        Context(
            relative_path="src/a.py", content="content a", start_line_number=1, end_line_number=5
        ),
        Context(
            relative_path="src/m.py", content="content m", start_line_number=1, end_line_number=5
        ),
    ]
    result = sort_contexts(contexts)
    assert result[0].relative_path == "src/a.py"
    assert result[1].relative_path == "src/m.py"
    assert result[2].relative_path == "src/z.py"


def test_sort_contexts_by_line_numbers():
    """Test sorting by line numbers within same file"""
    contexts = [
        Context(
            relative_path="test.py", content="content 3", start_line_number=20, end_line_number=25
        ),
        Context(
            relative_path="test.py", content="content 1", start_line_number=1, end_line_number=5
        ),
        Context(
            relative_path="test.py", content="content 2", start_line_number=10, end_line_number=15
        ),
    ]
    result = sort_contexts(contexts)
    assert result[0].start_line_number == 1
    assert result[1].start_line_number == 10
    assert result[2].start_line_number == 20


def test_sort_contexts_none_line_numbers():
    """Test sorting when line numbers are None (should appear last)"""
    contexts = [
        Context(
            relative_path="test.py",
            content="content with lines",
            start_line_number=10,
            end_line_number=15,
        ),
        Context(
            relative_path="test.py",
            content="content no lines",
            start_line_number=None,
            end_line_number=None,
        ),
        Context(
            relative_path="test.py", content="content first", start_line_number=1, end_line_number=5
        ),
    ]
    result = sort_contexts(contexts)
    assert result[0].start_line_number == 1
    assert result[1].start_line_number == 10
    assert result[2].start_line_number is None


def test_sort_contexts_mixed_files_and_lines():
    """Test sorting with multiple files and different line numbers"""
    contexts = [
        Context(
            relative_path="b.py", content="b content 2", start_line_number=20, end_line_number=25
        ),
        Context(
            relative_path="a.py", content="a content 2", start_line_number=10, end_line_number=15
        ),
        Context(
            relative_path="b.py", content="b content 1", start_line_number=5, end_line_number=10
        ),
        Context(
            relative_path="a.py", content="a content 1", start_line_number=1, end_line_number=5
        ),
    ]
    result = sort_contexts(contexts)
    assert result[0].relative_path == "a.py" and result[0].start_line_number == 1
    assert result[1].relative_path == "a.py" and result[1].start_line_number == 10
    assert result[2].relative_path == "b.py" and result[2].start_line_number == 5
    assert result[3].relative_path == "b.py" and result[3].start_line_number == 20


def test_sort_contexts_end_line_number_tiebreaker():
    """Test sorting uses end_line_number as tiebreaker when start_line_number is same"""
    contexts = [
        Context(
            relative_path="test.py", content="content 3", start_line_number=10, end_line_number=30
        ),
        Context(
            relative_path="test.py", content="content 1", start_line_number=10, end_line_number=15
        ),
        Context(
            relative_path="test.py", content="content 2", start_line_number=10, end_line_number=20
        ),
    ]
    result = sort_contexts(contexts)
    assert result[0].end_line_number == 15
    assert result[1].end_line_number == 20
    assert result[2].end_line_number == 30
