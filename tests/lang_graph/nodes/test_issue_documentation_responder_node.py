import pytest
from langchain_core.messages import AIMessage

from prometheus.lang_graph.nodes.issue_documentation_responder_node import (
    IssueDocumentationResponderNode,
)
from prometheus.lang_graph.subgraphs.issue_documentation_state import IssueDocumentationState
from tests.test_utils.util import FakeListChatWithToolsModel


@pytest.fixture
def fake_llm():
    return FakeListChatWithToolsModel(
        responses=[
            "The documentation has been successfully updated. "
            "I've added new API endpoint documentation and included examples as requested."
        ]
    )


@pytest.fixture
def basic_state():
    return IssueDocumentationState(
        issue_title="Update API documentation",
        issue_body="The API documentation needs to be updated with the new endpoints",
        issue_comments=[
            {"username": "user1", "comment": "Please include examples"},
        ],
        max_refined_query_loop=3,
        documentation_query="Find API documentation",
        documentation_context=[],
        issue_documentation_analyzer_messages=[
            AIMessage(content="Plan: Update README.md with new API endpoints and add examples")
        ],
        edit_messages=[],
        edit_patch="diff --git a/README.md b/README.md\n+New API documentation",
        issue_response="",
    )


def test_init_issue_documentation_responder_node(fake_llm):
    """Test IssueDocumentationResponderNode initialization."""
    node = IssueDocumentationResponderNode(fake_llm)

    assert node.model is not None


def test_call_method_basic(fake_llm, basic_state):
    """Test basic call functionality."""
    node = IssueDocumentationResponderNode(fake_llm)
    result = node(basic_state)

    assert "issue_response" in result
    assert "successfully updated" in result["issue_response"]
    assert len(result["issue_response"]) > 0


def test_call_method_with_patch(fake_llm, basic_state):
    """Test response generation with patch."""
    node = IssueDocumentationResponderNode(fake_llm)
    result = node(basic_state)

    assert "issue_response" in result
    assert isinstance(result["issue_response"], str)


def test_call_method_without_patch(fake_llm):
    """Test response generation without patch."""
    state = IssueDocumentationState(
        issue_title="Update docs",
        issue_body="Please update the documentation",
        issue_comments=[],
        max_refined_query_loop=3,
        documentation_query="",
        documentation_context=[],
        issue_documentation_analyzer_messages=[AIMessage(content="Documentation plan created")],
        edit_messages=[],
        edit_patch="",
        issue_response="",
    )

    node = IssueDocumentationResponderNode(fake_llm)
    result = node(state)

    assert "issue_response" in result
    assert len(result["issue_response"]) > 0


def test_response_includes_issue_details(fake_llm, basic_state):
    """Test that the generated response is relevant to the issue."""
    node = IssueDocumentationResponderNode(fake_llm)
    result = node(basic_state)

    assert "issue_response" in result
    # The response should be a string with meaningful content
    assert len(result["issue_response"]) > 10
