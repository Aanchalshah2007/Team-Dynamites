"""Thin shared LLM wrapper used by sql_rag_chain.py and orchestrator.py.

Not called out as its own file in architecture/architechture.md, but both
consumers need the same "call the LLM, get text back" primitive, so it's
factored out here rather than duplicated. Swap the implementation if the
project's LLM_API_KEY targets a different provider.
"""

import anthropic

import config

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.LLM_API_KEY)
    return _client


def complete(system: str, user: str, max_tokens: int = 1024) -> str:
    """Single-turn completion: system instructions + one user message -> text."""
    response = _get_client().messages.create(
        model=config.LLM_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in response.content if block.type == "text")
