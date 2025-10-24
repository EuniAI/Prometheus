import pytest
from langchain_core.messages import HumanMessage

from prometheus.lang_graph.nodes.issue_documentation_analyzer_node import (
    IssueDocumentationAnalyzerNode,
)
from prometheus.lang_graph.subgraphs.issue_documentation_state import IssueDocumentationState
from tests.test_utils.util import FakeListChatWithToolsModel


@pytest.fixture
def fake_llm():
    return FakeListChatWithToolsModel(
        responses=[
            "Documentation Plan:\n1. Update README.md with new API documentation\n"
            "2. Add code examples\n3. Update table of contents"
        ]
    )


@pytest.fixture
def basic_state():
    return IssueDocumentationState(
        issue_title="Update API documentation",
        issue_body="The API documentation needs to be updated with the new endpoints",
        issue_comments=[
            {"username": "user1", "comment": "Please include examples"},
            {"username": "user2", "comment": "Add authentication details"},
        ],
        max_refined_query_loop=3,
        documentation_query="Find API documentation files",
        documentation_context=[],
        issue_documentation_analyzer_messages=[
            HumanMessage(content="Please analyze the documentation request and provide a plan")
        ],
        edit_messages=[],
        edit_patch="",
        issue_response="",
    )


def test_init_issue_documentation_analyzer_node(fake_llm):
    """Test IssueDocumentationAnalyzerNode initialization."""
    node = IssueDocumentationAnalyzerNode(fake_llm)

    assert node.system_prompt is not None
    assert node.web_search_tool is not None
    assert len(node.tools) == 1  # Should have web search tool
    assert node.model_with_tools is not None


def test_call_method_basic(fake_llm, basic_state):
    """Test basic call functionality."""
    node = IssueDocumentationAnalyzerNode(fake_llm)
    result = node(basic_state)

    assert "issue_documentation_analyzer_messages" in result
    assert len(result["issue_documentation_analyzer_messages"]) == 1
    assert "Documentation Plan" in result["issue_documentation_analyzer_messages"][0].content


def test_call_method_with_empty_messages(fake_llm):
    """Test call method with empty message history."""
    state = IssueDocumentationState(
        issue_title="Test",
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

    node = IssueDocumentationAnalyzerNode(fake_llm)
    result = node(state)

    assert "issue_documentation_analyzer_messages" in result
    assert len(result["issue_documentation_analyzer_messages"]) == 1
