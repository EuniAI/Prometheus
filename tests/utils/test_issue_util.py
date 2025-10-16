from prometheus.utils.issue_util import (
    format_issue_comments,
    format_issue_info,
    format_test_commands,
)


def test_format_issue_comments():
    comments = [
        {"username": "alice", "comment": "This looks good!"},
        {"username": "bob", "comment": "Can we add tests?"},
    ]

    result = format_issue_comments(comments)
    expected = "alice: This looks good!\n\nbob: Can we add tests?"

    assert result == expected


def test_format_issue_info():
    title = "Bug in login flow"
    body = "Users can't login on mobile devices"
    comments = [
        {"username": "alice", "comment": "I can reproduce this"},
        {"username": "bob", "comment": "Working on a fix"},
    ]

    result = format_issue_info(title, body, comments)
    expected = """\
Issue title:
Bug in login flow

Issue description:
Users can't login on mobile devices

Issue comments:
alice: I can reproduce this

bob: Working on a fix"""

    assert result == expected


def test_format_test_commands():
    commands = ["pytest test_login.py", "pytest test_auth.py -v"]

    result = format_test_commands(commands)
    expected = "$ pytest test_login.py\n$ pytest test_auth.py -v"

    assert result == expected
