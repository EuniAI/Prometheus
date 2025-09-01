from typing import Any, Iterator, Mapping, Optional, Sequence

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
) -> Iterator[Context]:
    if data is None:
        return

    for search_result in data:
        search_result_keys = search_result.keys()
        # Skip if the result has no keys or only contains the "FileNode" key
        if len(search_result_keys) == 1:
            continue

        context = Context(
            relative_path=search_result["FileNode"]["relative_path"],
            content=(
                search_result.get("ASTNode", {}).get("text")
                or search_result.get("TextNode", {}).get("text")
                or search_result.get("preview", {}).get("text")
                or search_result.get("SelectedLines", {}).get("text")
            ),
            start_line_number=(
                search_result.get("ASTNode", {}).get("start_line")
                or search_result.get("SelectedLines", {}).get("start_line")
                or search_result.get("preview", {}).get("start_line")
            ),
            end_line_number=search_result.get("ASTNode", {}).get("end_line")
            or search_result.get("SelectedLines", {}).get("end_line")
            or search_result.get("preview", {}).get("end_line"),
        )

        yield context
