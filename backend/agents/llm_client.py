# cv-agent/backend/agents/llm_client.py

"""
Shared Anthropic LLM client untuk semua agents di CV Agent system.

Menyediakan:
- `call_llm()` — helper async function untuk semua LLM calls

Semua agents mengimport dari module ini — tidak ada yang membuat
client instance sendiri.
"""

import logging

import anthropic

from config import get_settings

logger = logging.getLogger("agents.llm_client")

settings = get_settings()
llm = anthropic.Anthropic(api_key=settings.anthropic_api_key)


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1000,
) -> str:
    logger.debug(
        f"[call_llm] calling model={settings.llm_model}, "
        f"max_tokens={max_tokens}, "
        f"system_prompt_len={len(system_prompt)}, "
        f"user_prompt_len={len(user_prompt)}"
    )

    response = llm.messages.create(
        model=settings.llm_model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text_content = response.content[0].text

    logger.debug(
        f"[call_llm] response received, "
        f"output_tokens={response.usage.output_tokens}"
    )

    return text_content