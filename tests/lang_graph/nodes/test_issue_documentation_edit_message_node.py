import pytest
from langchain_core.messages import AIMessage, HumanMessage

from prometheus.lang_graph.nodes.issue_documentation_edit_message_node import (
    IssueDocumentationEditMessageNode,
)
from prometheus.lang_graph.subgraphs.issue_documentation_state import IssueDocumentationState
from prometheus.models.context import Context


@pytest.fixture
def basic_state():
    return IssueDocumentationState(
        issue_title="Update API documentation",
        issue_body="The API documentation needs to be updated",
        issue_comments=[],
        max_refined_query_loop=3,
        documentation_query="Find API docs",
        documentation_context=[
            Context(
                relative_path="/docs/api.md",
                content="# API Documentation\n\nAPI Documentation content",
            )
        ],
        issue_documentation_analyzer_messages=[
            AIMessage(content="Plan:\n1. Update README.md\n2. Add new examples\n3. Fix typos")
        ],
        edit_messages=[],
        edit_patch="",
        issue_response="",
    )


def test_init_issue_documentation_edit_message_node():
    """Test IssueDocumentationEditMessageNode initialization."""
    node = IssueDocumentationEditMessageNode()
    assert node is not None


def test_call_method_creates_message(basic_state):
    """Test that the node creates a human message."""
    node = IssueDocumentationEditMessageNode()
    result = node(basic_state)

    assert "edit_messages" in result
    assert len(result["edit_messages"]) == 1
    assert isinstance(result["edit_messages"][0], HumanMessage)


def test_message_contains_plan(basic_state):
    """Test that the message contains the documentation plan."""
    node = IssueDocumentationEditMessageNode()
    result = node(basic_state)

    message_content = result["edit_messages"][0].content
    assert "Plan:" in message_content or "Update README.md" in message_content


def test_message_contains_context(basic_state):
    """Test that the message includes documentation context."""
    node = IssueDocumentationEditMessageNode()
    result = node(basic_state)

    message_content = result["edit_messages"][0].content
    # Should include context
    assert "context" in message_content.lower() or "API Documentation" in message_content


def test_message_includes_edit_instructions(basic_state):
    """Test that the message includes editing instructions."""
    node = IssueDocumentationEditMessageNode()
    result = node(basic_state)

    message_content = result["edit_messages"][0].content
    # Should include instructions for implementing changes
    assert any(
        keyword in message_content.lower() for keyword in ["implement", "edit", "changes", "file"]
    )


def test_call_with_empty_context():
    """Test the node with empty documentation context."""
    state = IssueDocumentationState(
        issue_title="Create docs",
        issue_body="Create new documentation",
        issue_comments=[],
        max_refined_query_loop=3,
        documentation_query="",
        documentation_context=[],
        issue_documentation_analyzer_messages=[AIMessage(content="Create new documentation files")],
        edit_messages=[],
        edit_patch="",
        issue_response="",
    )

    node = IssueDocumentationEditMessageNode()
    result = node(state)

    assert "edit_messages" in result
    assert len(result["edit_messages"]) == 1


def test_extracts_last_analyzer_message(basic_state):
    """Test that the node extracts the last message from analyzer history."""
    # Add multiple messages to analyzer history
    basic_state["issue_documentation_analyzer_messages"] = [
        AIMessage(content="First message"),
        AIMessage(content="Second message"),
        AIMessage(content="Final plan: Update docs"),
    ]

    node = IssueDocumentationEditMessageNode()
    result = node(basic_state)

    message_content = result["edit_messages"][0].content
    # Should contain the final plan
    assert "Final plan" in message_content
