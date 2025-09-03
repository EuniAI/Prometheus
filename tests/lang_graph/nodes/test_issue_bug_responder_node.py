import pytest

from prometheus.lang_graph.nodes.issue_bug_responder_node import IssueBugResponderNode
from prometheus.lang_graph.subgraphs.issue_bug_state import IssueBugState
from tests.test_utils.util import FakeListChatWithToolsModel


@pytest.fixture
def fake_llm():
    return FakeListChatWithToolsModel(
        responses=["Thank you for reporting this issue. The fix has been implemented and verified."]
    )


@pytest.fixture
def basic_state():
    return IssueBugState(
        issue_title="Test Bug",
        issue_body="Found a bug in the code",
        issue_comments=[
            {"username": "user1", "comment": "This affects my workflow"},
            {"username": "user2", "comment": "Same issue here"},
        ],
        edit_patch="Fixed array index calculation",
        passed_reproducing_test=True,
        passed_regression_test=True,
        passed_existing_test=True,
        run_build=True,
        run_existing_test=True,
        run_regression_test=True,
        run_reproduce_test=True,
        number_of_candidate_patch=6,
        reproduced_bug=True,
        reproduced_bug_file="mock.py",
        reproduced_bug_patch="mock patch to reproduce the bug",
        reproduced_bug_commands="pytest test_bug.py",
        selected_regression_tests=["tests:tests"],
        issue_response="Mock Response",
    )


def test_format_human_message_basic(fake_llm, basic_state):
    """Test basic human message formatting."""
    node = IssueBugResponderNode(fake_llm)
    message = node.format_human_message(basic_state)

    assert "Test Bug" in message.content
    assert "Found a bug in the code" in message.content
    assert "user1" in message.content
    assert "user2" in message.content
    assert "Fixed array index" in message.content


def test_format_human_message_verification(fake_llm, basic_state):
    """Test verification message formatting."""
    node = IssueBugResponderNode(fake_llm)
    message = node.format_human_message(basic_state)

    assert "✓ The bug reproducing test passed" in message.content
    assert "✓ All selected regression tests passes successfully" in message.content
    assert "✓ All existing tests pass successfully" in message.content


def test_format_human_message_no_verification(fake_llm):
    """Test message formatting without verifications."""
    state = IssueBugState(
        issue_title="Test Bug",
        issue_body="Bug description",
        issue_comments=[],
        edit_patch="Fixed array index calculation",
        passed_reproducing_test=False,
        passed_existing_test=False,
        passed_regression_test=False,
    )

    node = IssueBugResponderNode(fake_llm)
    message = node.format_human_message(state)

    assert "✓ The bug reproducing test passed" not in message.content
    assert "✓ All selected regression tests passes successfully" not in message.content
    assert "✓ All existing tests pass successfully" not in message.content


def test_format_human_message_partial_verification(fake_llm):
    """Test message formatting with partial verifications."""
    state = IssueBugState(
        issue_title="Test Bug",
        issue_body="Bug description",
        issue_comments=[],
        edit_patch="Fixed array index calculation",
        passed_reproducing_test=True,
        passed_existing_test=True,
        passed_regression_test=True,
    )

    node = IssueBugResponderNode(fake_llm)
    message = node.format_human_message(state)

    assert "✓ The bug reproducing test passed" in message.content
    assert "✓ Build passes successfully" not in message.content
    assert "✓ All existing tests pass successfully" in message.content


def test_call_method(fake_llm, basic_state):
    """Test the call method execution."""
    node = IssueBugResponderNode(fake_llm)
    result = node(basic_state)

    assert "issue_response" in result
    assert (
        result["issue_response"]
        == "Thank you for reporting this issue. The fix has been implemented and verified."
    )
