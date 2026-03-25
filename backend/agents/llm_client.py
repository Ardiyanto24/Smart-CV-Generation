# cv-agent/backend/agents/llm_client.py

"""
Shared Anthropic LLM client untuk semua agents di CV Agent system.

Menggunakan Google Cloud Vertex AI sebagai provider.
Autentikasi via Application Default Credentials (ADC).
"""

import functools
import logging

from anthropic import AnthropicVertex
from config import get_settings

logger = logging.getLogger("agents.llm_client")

GCP_PROJECT_ID = "project-6f8e6637-365a-44b6-b0a"
GCP_REGION = "us-east5"


@functools.lru_cache
def _get_client() -> AnthropicVertex:
    return AnthropicVertex(
        project_id=GCP_PROJECT_ID,
        region=GCP_REGION,
    )


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1000,
) -> str:
    settings = get_settings()
    client = _get_client()

    logger.debug(
        f"[call_llm] calling model={settings.llm_model}, "
        f"max_tokens={max_tokens}, "
        f"system_prompt_len={len(system_prompt)}, "
        f"user_prompt_len={len(user_prompt)}"
    )

    response = client.messages.create(
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