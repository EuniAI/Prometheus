import pytest

from prometheus.lang_graph.nodes.issue_documentation_context_message_node import (
    IssueDocumentationContextMessageNode,
)
from prometheus.lang_graph.subgraphs.issue_documentation_state import IssueDocumentationState


@pytest.fixture
def basic_state():
    return IssueDocumentationState(
        issue_title="Update API documentation",
        issue_body="The API documentation needs to be updated with new endpoints",
        issue_comments=[
            {"username": "user1", "comment": "Please include examples"},
        ],
        max_refined_query_loop=3,
        documentation_query="",
        documentation_context=[],
        issue_documentation_analyzer_messages=[],
        edit_messages=[],
        edit_patch="",
        issue_response="",
    )


def test_init_issue_documentation_context_message_node():
    """Test IssueDocumentationContextMessageNode initialization."""
    node = IssueDocumentationContextMessageNode()
    assert node is not None


def test_call_method_generates_query(basic_state):
    """Test that the node generates a documentation query."""
    node = IssueDocumentationContextMessageNode()
    result = node(basic_state)

    assert "documentation_query" in result
    assert len(result["documentation_query"]) > 0


def test_query_contains_issue_info(basic_state):
    """Test that the query contains issue information."""
    node = IssueDocumentationContextMessageNode()
    result = node(basic_state)

    query = result["documentation_query"]
    assert "Update API documentation" in query or "API documentation" in query


def test_query_includes_instructions(basic_state):
    """Test that the query includes documentation finding instructions."""
    node = IssueDocumentationContextMessageNode()
    result = node(basic_state)

    query = result["documentation_query"]
    # Should include instructions about finding documentation
    assert "documentation" in query.lower() or "find" in query.lower()


def test_call_with_empty_comments():
    """Test the node with empty comments."""
    state = IssueDocumentationState(
        issue_title="Test title",
        issue_body="Test body",
        issue_comments=[],
        max_refined_query_loop=3,
        documentation_query="",
        documentation_context=[],
        issue_documentation_analyzer_messages=[],
        edit_messages=[],
        edit_patch="",
        issue_response="",
    )

    node = IssueDocumentationContextMessageNode()
    result = node(state)

    assert "documentation_query" in result
    assert len(result["documentation_query"]) > 0
