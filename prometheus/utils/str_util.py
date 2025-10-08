from functools import lru_cache

import tiktoken


@lru_cache(maxsize=1)
def get_tokenizer(encoding: str = "o200k_base") -> tiktoken.Encoding:
    return tiktoken.get_encoding(encoding)


def pre_append_line_numbers(text: str, start_line: int) -> str:
    return "\n".join([f"{start_line + i}. {line}" for i, line in enumerate(text.splitlines())])
