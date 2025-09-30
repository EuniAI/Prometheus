import logging
import threading
from typing import Any, Optional

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic_core._pydantic_core import ValidationError

from prometheus.exceptions.llm_exception import LLMException


class CustomChatOpenAI(ChatOpenAI):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.max_retries = 3  # Set the maximum number of retries
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def bind_tools(self, tools, tool_choice=None, **kwargs):
        kwargs["parallel_tool_calls"] = False
        return super().bind_tools(tools, tool_choice=tool_choice, **kwargs)

    def invoke(
        self,
        input: LanguageModelInput,
        config: Optional[RunnableConfig] = None,
        *,
        stop: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> BaseMessage:
        for attempt in range(self.max_retries):
            try:
                return super().invoke(
                    input=input,
                    config=config,
                    stop=stop,
                    **kwargs,
                )
            except ValidationError:
                self._logger.warning(
                    f"ValidationError encountered. Retrying the model invocation... Attempt {attempt + 1}/{self.max_retries}"
                )
        raise LLMException(
            "Failed to invoke the model after multiple retries due to validation errors."
        )
