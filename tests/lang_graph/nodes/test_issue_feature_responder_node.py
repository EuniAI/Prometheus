import pytest

from prometheus.lang_graph.nodes.issue_feature_responder_node import IssueFeatureResponderNode
from prometheus.lang_graph.subgraphs.issue_feature_state import IssueFeatureState
from tests.test_utils.util import FakeListChatWithToolsModel


@pytest.fixture
def fake_llm():
    return FakeListChatWithToolsModel(
        responses=[
            "Thank you for requesting this feature. The implementation has been completed and is ready for review."
        ]
    )


@pytest.fixture
def basic_state():
    return IssueFeatureState(
        issue_title="Add dark mode support",
        issue_body="Please add dark mode to the application",
        issue_comments=[
            {"username": "user1", "comment": "This would be great!"},
            {"username": "user2", "comment": "I need this feature"},
        ],
        final_patch="Added dark mode theme switching functionality",
        run_regression_test=True,
        number_of_candidate_patch=3,
        selected_regression_tests=["tests:tests"],
        issue_response="Mock Response",
    )


def test_format_human_message_basic(fake_llm, basic_state):
    """Test basic human message formatting."""
    node = IssueFeatureResponderNode(fake_llm)
    message = node.format_human_message(basic_state)

    assert "Add dark mode support" in message.content
    assert "Please add dark mode to the application" in message.content
    assert "user1" in message.content
    assert "user2" in message.content
    assert "Added dark mode theme switching functionality" in message.content


def test_format_human_message_with_regression_tests(fake_llm, basic_state):
    """Test message formatting with regression tests."""
    # Add tested_patch_result to simulate passed tests
    from prometheus.models.test_patch_result import TestedPatchResult

    basic_state["tested_patch_result"] = [
        TestedPatchResult(patch="test patch", passed=True, regression_test_failure_log="")
    ]

    node = IssueFeatureResponderNode(fake_llm)
    message = node.format_human_message(basic_state)

    assert "✓ All selected regression tests passed successfully" in message.content


def test_format_human_message_no_tests(fake_llm):
    """Test message formatting without tests."""
    state = IssueFeatureState(
        issue_title="Add feature",
        issue_body="Feature description",
        issue_comments=[],
        final_patch="Implementation patch",
        run_regression_test=False,
        number_of_candidate_patch=1,
        selected_regression_tests=[],
        issue_response="",
    )

    node = IssueFeatureResponderNode(fake_llm)
    message = node.format_human_message(state)

    assert "No automated tests were run for this feature implementation." in message.content


def test_call_method(fake_llm, basic_state):
    """Test the call method execution."""
    node = IssueFeatureResponderNode(fake_llm)
    result = node(basic_state)

    assert "issue_response" in result
    assert (
        result["issue_response"]
        == "Thank you for requesting this feature. The implementation has been completed and is ready for review."
    )
