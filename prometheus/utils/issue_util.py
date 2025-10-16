from typing import Mapping, Sequence


def format_issue_comments(issue_comments: Sequence[Mapping[str, str]]):
    """Formats a sequence of issue comments into a readable string.

    Combines multiple issue comments with their associated usernames into a
    formatted string suitable for inclusion in the response context.

    Args:
      issue_comments: Sequence of mappings containing 'username' and 'comment'
        keys for each issue comment.

    Returns:
      Formatted string containing all comments with usernames, separated by newlines.
    """
    formatted_issue_comments = []
    for issue_comment in issue_comments:
        formatted_issue_comments.append(f"{issue_comment['username']}: {issue_comment['comment']}")
    return "\n\n".join(formatted_issue_comments)


def format_issue_info(
    issue_title: str, issue_body: str, issue_comments: Sequence[Mapping[str, str]]
) -> str:
    return f"""\
Issue title:
{issue_title}

Issue description:
{issue_body}

Issue comments:
{format_issue_comments(issue_comments)}"""


def format_test_commands(test_commands: Sequence[str]) -> str:
    test_commands_with_prefix = [f"$ {test_command}" for test_command in test_commands]
    return "\n".join(test_commands_with_prefix)
