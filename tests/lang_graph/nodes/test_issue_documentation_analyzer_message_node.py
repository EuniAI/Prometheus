import pytest
from langchain_core.messages import HumanMessage

from prometheus.lang_graph.nodes.issue_documentation_analyzer_message_node import (
    IssueDocumentationAnalyzerMessageNode,
)
from prometheus.lang_graph.subgraphs.issue_documentation_state import IssueDocumentationState
from prometheus.models.context import Context


@pytest.fixture
def basic_state():
    return IssueDocumentationState(
        issue_title="Update API documentation",
        issue_body="The API documentation needs to be updated",
        issue_comments=[
            {"username": "user1", "comment": "Please add examples"},
        ],
        max_refined_query_loop=3,
        documentation_query="Find API docs",
        documentation_context=[
            Context(
                relative_path="/docs/api.md",
                content="# API Documentation\n\nAPI Documentation content",
            )
        ],
        issue_documentation_analyzer_messages=[],
        edit_messages=[],
        edit_patch="",
        issue_response="",
    )


def test_init_issue_documentation_analyzer_message_node():
    """Test IssueDocumentationAnalyzerMessageNode initialization."""
    node = IssueDocumentationAnalyzerMessageNode()
    assert node is not None


def test_call_method_creates_message(basic_state):
    """Test that the node creates a human message."""
    node = IssueDocumentationAnalyzerMessageNode()
    result = node(basic_state)

    assert "issue_documentation_analyzer_messages" in result
    assert len(result["issue_documentation_analyzer_messages"]) == 1
    assert isinstance(result["issue_documentation_analyzer_messages"][0], HumanMessage)


def test_message_contains_issue_info(basic_state):
    """Test that the message contains issue information."""
    node = IssueDocumentationAnalyzerMessageNode()
    result = node(basic_state)

    message_content = result["issue_documentation_analyzer_messages"][0].content
    assert "Update API documentation" in message_content


def test_message_contains_context(basic_state):
    """Test that the message includes documentation context."""
    node = IssueDocumentationAnalyzerMessageNode()
    result = node(basic_state)

    message_content = result["issue_documentation_analyzer_messages"][0].content
    # Should include context or reference to it
    assert "context" in message_content.lower() or "API Documentation" in message_content


def test_message_includes_analysis_instructions(basic_state):
    """Test that the message includes analysis instructions."""
    node = IssueDocumentationAnalyzerMessageNode()
    result = node(basic_state)

    message_content = result["issue_documentation_analyzer_messages"][0].content
    # Should include instructions for analysis
    assert "plan" in message_content.lower() or "analyze" in message_content.lower()


def test_call_with_empty_context():
    """Test the node with empty documentation context."""
    state = IssueDocumentationState(
        issue_title="Create new docs",
        issue_body="Create documentation for new feature",
        issue_comments=[],
        max_refined_query_loop=3,
        documentation_query="",
        documentation_context=[],
        issue_documentation_analyzer_messages=[],
        edit_messages=[],
        edit_patch="",
        issue_response="",
    )

    node = IssueDocumentationAnalyzerMessageNode()
    result = node(state)

    assert "issue_documentation_analyzer_messages" in result
    assert len(result["issue_documentation_analyzer_messages"]) == 1
