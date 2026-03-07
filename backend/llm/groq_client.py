"""
backend/llm/groq_client.py
---------------------------
Wrapper around the Groq Python SDK.

Groq provides free, ultra-fast LLM inference.
Get a free API key at: https://console.groq.com

Default model : llama3-8b-8192
Override via  : GROQ_MODEL env var
"""

import os
import logging
from groq import Groq, APIError, RateLimitError, AuthenticationError

logger = logging.getLogger(__name__)

DEFAULT_MODEL       = "llama-3.1-8b-instant"
DEFAULT_TEMPERATURE = 0.2    # low = focused, deterministic code explanations
DEFAULT_MAX_TOKENS  = 1024

SYSTEM_PROMPT = """You are an expert software engineer and code reviewer.
Your task is to clearly explain code from a GitHub repository to a developer.

Guidelines:
- Be precise and technically accurate
- Reference specific file names and function names when visible in the context
- Use bullet points and numbered lists for multi-step flows
- Format code snippets with markdown code blocks
- Keep answers concise but complete
- If the context is insufficient, say so clearly and explain what additional information would help

You are explaining real code from the repository — do not invent or assume code that isn't shown."""


class GroqLLMClient:
    """Chat-completion client for the Groq API."""

    def __init__(
        self,
        model: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY is not set.\n"
                "1. Get a free key at https://console.groq.com\n"
                "2. Add it to backend/.env:  GROQ_API_KEY=gsk_..."
            )
        self.client      = Groq(api_key=api_key)
        self.model       = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)
        self.temperature = temperature
        self.max_tokens  = max_tokens
        logger.info("GroqLLMClient ready — model: %s", self.model)

    def ask(self, question: str, context: str = "") -> str:
        """
        Send question + code context to Groq and return the answer string.

        Args:
            question: User's natural-language question.
            context:  Concatenated relevant code chunks from FAISS retrieval.

        Raises:
            RuntimeError: Wraps Groq SDK errors with user-friendly messages.
        """
        user_msg = _build_user_message(question, context)
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return resp.choices[0].message.content
        except AuthenticationError:
            raise RuntimeError(
                "Invalid GROQ_API_KEY. Verify at https://console.groq.com"
            )
        except RateLimitError:
            raise RuntimeError(
                "Groq rate limit reached. Please wait a moment and try again."
            )
        except APIError as exc:
            raise RuntimeError(f"Groq API error: {exc}") from exc

    def stream_tokens(self, question: str, context: str = ""):
        """
        Stream the LLM response token-by-token using Groq's streaming API.

        Yields:
            str: Individual text chunks as they arrive from the model.

        Raises:
            RuntimeError: Wraps Groq SDK errors with user-friendly messages.
        """
        user_msg = _build_user_message(question, context)
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except AuthenticationError:
            raise RuntimeError("Invalid GROQ_API_KEY. Verify at https://console.groq.com")
        except RateLimitError:
            raise RuntimeError("Groq rate limit reached. Please wait and try again.")
        except APIError as exc:
            raise RuntimeError(f"Groq API error: {exc}") from exc


def _build_user_message(question: str, context: str) -> str:
    """Assemble the RAG user prompt: code context first, then the question."""
    if context.strip():
        return (
            "Here is relevant code retrieved from the GitHub repository:\n\n"
            f"```\n{context}\n```\n\n"
            f"**Question:** {question}\n\n"
            "Please explain this clearly and thoroughly."
        )
    return (
        f"**Question about a GitHub repository:** {question}\n\n"
        "No specific code context was retrieved. "
        "Please answer based on general software engineering knowledge."
    )
