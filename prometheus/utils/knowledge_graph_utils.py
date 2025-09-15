from typing import Any, List, Mapping, Optional, Sequence

from prometheus.models.context import Context

EMPTY_DATA_MESSAGE = "Your query returned empty result, please try a different query!"


def format_knowledge_graph_data(data: Sequence[Mapping[str, Any]]) -> str:
    """Format a Neo4j result into a string.

    Args:
      data: The result from a Neo4j query.

    Returns:
      A string representation of the result.
    """
    if not data:
        return EMPTY_DATA_MESSAGE

    output = ""
    for index, row_result in enumerate(data):
        output += f"Result {index + 1}:\n"
        for key in sorted(row_result.keys()):
            output += f"{key}: {str(row_result[key])}\n"
        output += "\n\n"
    return output.strip()


def knowledge_graph_data_for_context_generator(
    data: Optional[Sequence[Mapping[str, Any]]],
) -> List[Context]:
    if data is None:
        return []

    result = []

    for search_result in data:
        search_result_keys = search_result.keys()
        # Skip if the result has no keys or only contains the "FileNode" key
        if len(search_result_keys) == 1:
            continue

        content = (
            search_result.get("ASTNode", {}).get("text")
            or search_result.get("TextNode", {}).get("text")
            or search_result.get("preview", {}).get("text")
            or search_result.get("SelectedLines", {}).get("text")
        )

        # Skip empty content
        if not content or not content.strip():
            continue

        content = content.strip()

        context = Context(
            relative_path=search_result["FileNode"]["relative_path"],
            content=content,
            start_line_number=(
                search_result.get("ASTNode", {}).get("start_line")
                or search_result.get("SelectedLines", {}).get("start_line")
                or search_result.get("preview", {}).get("start_line")
                or search_result.get("TextNode", {}).get("start_line")
            ),
            end_line_number=search_result.get("ASTNode", {}).get("end_line")
            or search_result.get("SelectedLines", {}).get("end_line")
            or search_result.get("preview", {}).get("end_line")
            or search_result.get("TextNode", {}).get("end_line"),
        )
        result.append(context)

    # Deduplicate contexts
    return deduplicate_contexts(result)


def deduplicate_contexts(contexts: List[Context]) -> List[Context]:
    """
    Remove duplicate contexts

    Deduplication rules:
    1. Completely identical contexts (same file, content, line numbers)
    2. Content containment relationship: if one context's content is completely contained
       in another, keep the more complete one
    """
    if not contexts:
        return []

    # Use index tracking to avoid modifying list during iteration
    to_keep = []

    for i, context in enumerate(contexts):
        should_keep = True

        for j, other_context in enumerate(contexts):
            if i == j:  # Skip self
                continue

            # Only compare within the same file
            if context.relative_path != other_context.relative_path:
                continue

            # Check if duplicate or contained
            relationship = _analyze_context_relationship(context, other_context)

            if relationship == "duplicate":
                # If duplicate, keep the one with smaller index (appears first)
                if i > j:
                    should_keep = False
                    break
            elif relationship == "contained":
                # Current context is contained by another context, don't keep it
                should_keep = False
                break
            elif relationship == "contains":
                # Current context contains another context, continue checking
                continue

        if should_keep:
            to_keep.append(context)

    return to_keep


def _analyze_context_relationship(context1: Context, context2: Context) -> str:
    """
     analyze the relationship between two contexts.

    returns:
    - "duplicate": Same content and line numbers
    - "contained": context1 is contained in context2
    - "contains": context1 contains context2
    - "separate": No containment relationship
    """
    # Check if content is completely identical
    if context1.content == context2.content:
        return "duplicate"

    # Check content containment relationship
    if context1.content in context2.content:
        return "contained"
    elif context2.content in context1.content:
        return "contains"

    # If no line number information available, can only judge based on content
    if (
        context1.start_line_number is None
        or context1.end_line_number is None
        or context2.start_line_number is None
        or context2.end_line_number is None
    ):
        return "separate"

    # Check for complete containment based on line numbers
    if (
        context1.start_line_number <= context2.start_line_number
        and context1.end_line_number >= context2.end_line_number
    ):
        return "contains"
    elif (
        context2.start_line_number <= context1.start_line_number
        and context2.end_line_number >= context1.end_line_number
    ):
        return "contained"

    # For all other cases (including partial overlaps), return separate
    return "separate"
