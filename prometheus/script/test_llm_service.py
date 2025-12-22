from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from prometheus.app.services.llm_service import LLMService
from prometheus.configuration.config import settings


class TestStructuredOutput(BaseModel):
    """Test schema for structured output"""

    reasoning: str = Field(description="Your reasoning about the answer")
    answer: str = Field(description="A short fun fact about space")
    confidence: str = Field(description="High, Medium, or Low confidence in this fact")


def test_model_response():
    llm_service = LLMService(
        settings.ADVANCED_MODEL,
        settings.BASE_MODEL,
        settings.ADVANCED_MODEL_TEMPERATURE,
        settings.BASE_MODEL_TEMPERATURE,
        settings.OPENAI_FORMAT_API_KEY,
        settings.OPENAI_FORMAT_BASE_URL,
        settings.ANTHROPIC_API_KEY,
        settings.GEMINI_API_KEY,
    )

    # Test base model
    chat_model = llm_service.base_model
    print(f"\nTesting Base Model: {settings.BASE_MODEL}")
    response = chat_model.invoke([HumanMessage(content="Hello! Tell me a fun fact about space.")])
    print("Response:", response.content)

    # Test advanced model
    chat_model = llm_service.advanced_model
    print(f"\nTesting Advanced Model: {settings.ADVANCED_MODEL}")
    response = chat_model.invoke([HumanMessage(content="Hello! Tell me a fun fact about space.")])
    print("Response:", response.content)
    print("Basic test completed successfully!")


def test_structured_output():
    """Test if models support LangChain's with_structured_output"""
    llm_service = LLMService(
        settings.ADVANCED_MODEL,
        settings.BASE_MODEL,
        settings.ADVANCED_MODEL_TEMPERATURE,
        settings.BASE_MODEL_TEMPERATURE,
        settings.OPENAI_FORMAT_API_KEY,
        settings.OPENAI_FORMAT_BASE_URL,
        settings.ANTHROPIC_API_KEY,
        settings.GEMINI_API_KEY,
    )

    # Test base model
    print(f"\n{'=' * 60}")
    print(f"Testing Structured Output - Base Model: {settings.BASE_MODEL}")
    print(f"{'=' * 60}")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful assistant."),
            ("human", "{question}"),
        ]
    )

    structured_llm = llm_service.base_model.with_structured_output(TestStructuredOutput)
    chain = prompt | structured_llm
    response = chain.invoke({"question": "Tell me a fun fact about space."})

    print(f"Response type: {type(response)}")
    print(f"Response: {response}")
    if response:
        print(f"Reasoning: {response.reasoning}")
        print(f"Answer: {response.answer}")
        print(f"Confidence: {response.confidence}")

    # Test advanced model
    print(f"\n{'=' * 60}")
    print(f"Testing Structured Output - Advanced Model: {settings.ADVANCED_MODEL}")
    print(f"{'=' * 60}")

    structured_llm = llm_service.advanced_model.with_structured_output(TestStructuredOutput)
    chain = prompt | structured_llm
    response = chain.invoke({"question": "Tell me a fun fact about space."})

    print(f"Response type: {type(response)}")
    print(f"Response: {response}")
    if response:
        print(f"Reasoning: {response.reasoning}")
        print(f"Answer: {response.answer}")
        print(f"Confidence: {response.confidence}")

    print("\nStructured output test completed!")


if __name__ == "__main__":
    test_model_response()
    print("\n" + "=" * 60)
    print("Starting Structured Output Tests...")
    print("=" * 60)
    test_structured_output()
