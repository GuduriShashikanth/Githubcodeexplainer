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

DEFAULT_MODEL       = "llama-3.3-70b-versatile"
DEFAULT_TEMPERATURE = 0.15   # low = focused, deterministic code explanations
DEFAULT_MAX_TOKENS  = 2048

SYSTEM_PROMPT = """You are an expert software engineer analyzing a real GitHub repository.
Your job is to give accurate, grounded explanations based ONLY on the code context provided.

STRICT RULES:
1. ONLY reference code, files, functions, and classes that appear in the provided context.
2. NEVER invent, guess, or hallucinate code that is not shown to you.
3. When referencing code, always cite the source file path (e.g. "in `src/utils/auth.py`").
4. If the context is insufficient to fully answer, say exactly what is missing and what additional files or context would help.
5. Clearly distinguish between what is directly shown in the code vs. what you are inferring from patterns.
6. For casual messages (greetings, thanks, acknowledgements), respond with a brief, friendly reply — do NOT generate code explanations for non-code messages.

RESPONSE FORMAT:
- Start with a brief summary (1-2 sentences) of the answer.
- Use bullet points and numbered lists for multi-step flows or multiple concepts.
- Format code references with inline backticks (`function_name`) and code blocks for snippets.
- Keep explanations concise but thorough — favor clarity over brevity.
- When explaining control flow, trace through the code step by step.

Think carefully about the code before answering. Trace imports, function calls, and data flow to give precise answers."""


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
        # Count chunks for specificity
        chunk_count = context.count("# File:")
        chunk_label = f"{chunk_count} code chunk(s)" if chunk_count else "code"
        return (
            f"## Retrieved Context\n"
            f"The following {chunk_label} were retrieved from the repository "
            f"as most relevant to the question:\n\n"
            f"{context}\n\n"
            f"## Question\n{question}\n\n"
            f"Answer based ONLY on the code above. "
            f"Cite file paths when referencing specific code. "
            f"If the context doesn't fully answer the question, state what's missing."
        )
    return (
        f"## Question\n{question}\n\n"
        "No code context was retrieved from the repository for this question. "
        "If this is a general programming question, answer it. "
        "Otherwise, suggest the user rephrase their question to match the codebase content."
    )
