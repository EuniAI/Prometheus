"""LLM utility functions for token counting using tiktoken.

This module provides functions for counting tokens in text and chat messages,
compatible with OpenAI models using the tiktoken library.
"""
from typing import Sequence

import tiktoken
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser


def str_token_counter(text: str) -> int:
    """Count the number of tokens in a text string using tiktoken.

    Uses the "o200k_base" encoding which is compatible with GPT-4o models.

    Args:
        text: The input text string to count tokens for.

    Returns:
        The number of tokens in the text.
    """
    enc = tiktoken.get_encoding("o200k_base")
    return len(enc.encode(text))


def tiktoken_counter(messages: Sequence[BaseMessage]) -> int:
    """Count tokens for a sequence of chat messages using OpenAI's methodology.

    Approximately reproduces the token counting logic from OpenAI's official
    implementation. For simplicity, only supports string Message.contents.

    Args:
        messages: A sequence of BaseMessage objects representing the chat messages.

    Returns:
        The total number of tokens including message formatting overhead.

    Raises:
        ValueError: If an unsupported message type is encountered.
    """
    output_parser = StrOutputParser()
    num_tokens = 3  # every reply is primed with <|start|>assistant<|message|>
    tokens_per_message = 3
    tokens_per_name = 1
    for msg in messages:
        if isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "assistant"
        elif isinstance(msg, ToolMessage):
            role = "tool"
        elif isinstance(msg, SystemMessage):
            role = "system"
        else:
            raise ValueError(f"Unsupported messages type {msg.__class__}")
        msg_content = output_parser.invoke(msg)
        num_tokens += tokens_per_message + str_token_counter(role) + str_token_counter(msg_content)
        if msg.name:
            num_tokens += tokens_per_name + str_token_counter(msg.name)
    return num_tokens
