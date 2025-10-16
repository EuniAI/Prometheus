from typing import Callable, Dict, List, Sequence

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.output_parsers import StrOutputParser

from prometheus.models.context import Context
from prometheus.utils.knowledge_graph_utils import knowledge_graph_data_for_context_generator


def check_remaining_steps(
    state: Dict,
    router: Callable[..., str],
    min_remaining_steps: int,
    remaining_steps_key: str = "remaining_steps",
) -> str:
    original_route = router(state)
    if state[remaining_steps_key] > min_remaining_steps:
        return original_route
    else:
        return "low_remaining_steps"


def extract_ai_responses(messages: Sequence[BaseMessage]) -> Sequence[str]:
    ai_responses = []
    output_parser = StrOutputParser()
    for index, message in enumerate(messages):
        if isinstance(message, AIMessage) and (
            index == len(messages) - 1 or isinstance(messages[index + 1], HumanMessage)
        ):
            ai_responses.append(output_parser.invoke(message))
    return ai_responses


def extract_human_queries(messages: Sequence[BaseMessage]) -> Sequence[str]:
    human_queries = []
    output_parser = StrOutputParser()
    for message in messages:
        if isinstance(message, HumanMessage):
            human_queries.append(output_parser.invoke(message))
    return human_queries


def extract_last_tool_messages(messages: Sequence[BaseMessage]) -> Sequence[ToolMessage]:
    """
    Extracts all tool messages that come after the last human message in the sequence.
    :param messages:
    :return: messages: A list of ToolMessage objects that come after the last HumanMessage.
    """
    tool_messages = []
    last_human_index = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_human_index = i
            break

    if last_human_index == -1:
        return []

    for message in messages[last_human_index + 1:]:
        if isinstance(message, ToolMessage):
            tool_messages.append(message)
    return tool_messages


def transform_tool_messages_to_context(messages: Sequence[ToolMessage]) -> List[Context]:
    """
    Transform tool messages to Context objects and return them in explored_context.

    Args:
        messages: Sequence of ToolMessage objects that may contain artifacts

    Returns:
        Dictionary with 'explored_context' key containing list of Context objects
    """
    # Aggregate all artifacts from the tool messages
    total_artifacts = []
    for message in messages:
        # only process messages that have artifacts
        if message.artifact:
            total_artifacts.extend(message.artifact)

    # Convert the aggregated artifacts to Context objects using the knowledge graph generator
    return list(knowledge_graph_data_for_context_generator(total_artifacts))


def get_last_message_content(messages: Sequence[BaseMessage]) -> str:
    output_parser = StrOutputParser()
    return output_parser.invoke(messages[-1])


def format_agent_tool_message_history(messages: Sequence[BaseMessage]) -> str:
    formatted_messages = []
    for message in messages:
        if isinstance(message, AIMessage):
            if message.content:
                formatted_messages.append(f"Assistant internal thought: {message.content}")
            if (
                message.additional_kwargs
                and "tool_calls" in message.additional_kwargs
                and message.additional_kwargs["tool_calls"]
            ):
                for tool_call in message.additional_kwargs["tool_calls"]:
                    formatted_messages.append(f"Assistant executed tool: {tool_call['function']}")
        elif isinstance(message, ToolMessage):
            formatted_messages.append(f"Tool output: {message.content}")
    return "\n\n".join(formatted_messages)
