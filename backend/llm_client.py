"""Thin shared LLM wrapper used by sql_rag_chain.py and orchestrator.py.

Not called out as its own file in architecture/architechture.md, but both
consumers need the same "call the LLM, get text back" primitive, so it's
factored out here rather than duplicated.

Talks to Groq's OpenAI-compatible chat completions API (config.LLM_API_KEY
is a Groq key) over plain HTTP via `requests`, rather than pulling in a
provider SDK for a single call shape.
"""

import requests

import config


def complete(system: str, user: str, max_tokens: int = 1024) -> str:
    """Single-turn completion: system instructions + one user message -> text."""
    response = requests.post(
        f"{config.LLM_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {config.LLM_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.LLM_MODEL,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
