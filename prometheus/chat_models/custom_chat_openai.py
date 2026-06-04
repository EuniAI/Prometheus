import json
import logging
import re
import threading
from typing import Any, ClassVar, Optional

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_openai import ChatOpenAI


class StructuredOutputError(ValueError):
    """Raised when the model fails to produce a structured (tool-call) output.

    In function-calling mode langchain returns ``None`` when the model replies with
    plain text instead of invoking the output tool. Surfacing that as an explicit
    error (instead of letting callers crash on ``None.<attr>``) lets ``with_retry``
    give the model another chance and yields a readable failure if it never complies.
    """


class CustomChatOpenAI(ChatOpenAI):
    # Number of times to re-invoke the model when it fails to emit a tool call.
    STRUCTURED_OUTPUT_RETRIES: ClassVar[int] = 3

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def bind_tools(self, tools, tool_choice=None, **kwargs):
        kwargs["parallel_tool_calls"] = False
        return super().bind_tools(tools, tool_choice=tool_choice, **kwargs)

    def with_structured_output(self, schema, *, method="function_calling", **kwargs):
        # langchain-openai defaults to method="json_schema" (strict response_format),
        # which is unreliable for OpenAI-compatible providers such as OpenRouter-hosted
        # models (e.g. kimi-k2) and silently yields empty/partial fields. Tool/function
        # calling is honored consistently, so default to it here.
        structured = super().with_structured_output(schema, method=method, **kwargs)

        # include_raw=True changes the output to a dict; leave those callers untouched.
        if kwargs.get("include_raw"):
            return structured

        # Some OpenAI-compatible providers do not honor forced tool_choice and reply
        # with plain text, in which case the runnable above resolves to None. Convert
        # that into a retryable error so the model gets another chance, and fail loudly
        # (instead of returning None and crashing downstream) if it never complies.
        def _require_tool_call(parsed: Any) -> Any:
            if parsed is None:
                raise StructuredOutputError(
                    f"Model did not emit a tool call for {getattr(schema, '__name__', schema)}"
                )
            return parsed

        return (structured | RunnableLambda(_require_tool_call)).with_retry(
            retry_if_exception_type=(StructuredOutputError,),
            stop_after_attempt=self.STRUCTURED_OUTPUT_RETRIES,
        )

    # JSON only allows these characters to follow a backslash in a string. Anything
    # else (e.g. the "\;" some models emit for shell -exec) is an invalid escape.
    _VALID_JSON_ESCAPES: ClassVar[frozenset] = frozenset('"\\/bfnrtu')

    @classmethod
    def _repair_json_escapes(cls, text: str) -> str:
        """Double any backslash that does not start a valid JSON escape sequence.

        Turns malformed fragments like ``\\;`` (common in shell ``-exec ... {} \\;``)
        into the JSON-legal ``\\\\;`` so the string can be parsed. Only used as a
        fallback on text that already failed to parse, so well-formed JSON is untouched.
        """
        return re.sub(
            r"\\(.)",
            lambda m: m.group(0) if m.group(1) in cls._VALID_JSON_ESCAPES else "\\\\" + m.group(1),
            text,
        )

    @classmethod
    def _coerce_to_json_object(cls, value: Any) -> Optional[dict]:
        """Best-effort recovery of a dict from a possibly-malformed arguments value.

        Handles the quirks some OpenAI-compatible providers (e.g. OpenRouter-hosted
        kimi-k2) emit for tool-call ``function.arguments``: a plain object string, a
        double- (or multiply-) encoded JSON string, and object strings containing
        invalid escape sequences. Returns the parsed dict, or ``None`` if unrecoverable.
        """
        if isinstance(value, dict):
            return value
        if not isinstance(value, str):
            return None
        for candidate in (value, cls._repair_json_escapes(value)):
            try:
                parsed = json.loads(candidate)
            except (TypeError, ValueError):
                continue
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, str):
                # One encoding layer peeled off; recurse on the inner payload.
                inner = cls._coerce_to_json_object(parsed)
                if inner is not None:
                    return inner
        return None

    @classmethod
    def _normalize_tool_call_arguments(cls, arguments: str) -> str:
        """Return a valid JSON object string for malformed tool-call arguments.

        Tool-call ``function.arguments`` must decode to a JSON object. When a provider
        double-encodes it or leaves invalid escapes, langchain parses ``args`` to a
        ``str`` and ``AIMessage`` validation crashes. We recover the intended object
        when possible; otherwise we leave well-formed input untouched and neutralize
        only the case that would otherwise crash (decodes to a non-object)."""
        recovered = cls._coerce_to_json_object(arguments)
        if recovered is not None:
            return json.dumps(recovered)
        try:
            decoded = json.loads(arguments)
        except (TypeError, ValueError):
            # Unparseable: leave as-is so langchain records an invalid tool call.
            return arguments
        # Parseable but not an object (e.g. a bare string): replace with an empty
        # object so AIMessage validation does not crash; the tool will then fail
        # gracefully and the agent can retry rather than aborting the whole run.
        return arguments if isinstance(decoded, dict) else "{}"

    def _create_chat_result(self, response, generation_info=None):
        # Normalize malformed tool-call arguments before langchain builds the
        # AIMessage, so a provider double-encoding the arguments string does not crash
        # parsing (see _normalize_tool_call_arguments).
        response_dict = response if isinstance(response, dict) else response.model_dump()
        for choice in response_dict.get("choices") or []:
            message = choice.get("message") or {}
            for tool_call in message.get("tool_calls") or []:
                function = tool_call.get("function") or {}
                arguments = function.get("arguments")
                if isinstance(arguments, str):
                    function["arguments"] = self._normalize_tool_call_arguments(arguments)
        return super()._create_chat_result(response_dict, generation_info)

    def invoke(
        self,
        input: LanguageModelInput,
        config: Optional[RunnableConfig] = None,
        *,
        stop: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> BaseMessage:
        return super().invoke(
            input=input,
            config=config,
            stop=stop,
            **kwargs,
        )
