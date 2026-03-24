# cv-agent/backend/agents/llm_client.py

"""
Shared Anthropic LLM client untuk semua agents di CV Agent system.

Menyediakan:
- `llm` — singleton Anthropic client, diinisialisasi sekali saat import
- `call_llm()` — helper async function untuk semua LLM calls

Semua agents mengimport dari module ini — tidak ada yang membuat
client instance sendiri. Ini memastikan:
1. API key hanya dibaca sekali dari config
2. Connection pooling yang efisien
3. Mudah mock saat testing
"""

import logging

import anthropic

from config import get_settings

logger = logging.getLogger("agents.llm_client")

# ── Singleton Anthropic Client ────────────────────────────────────────────────
# Dibuat sekali saat module di-import, dipakai oleh semua agents
# API key dibaca dari config yang membaca dari .env
settings = get_settings()
llm = anthropic.Anthropic(api_key=settings.anthropic_api_key)


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1000,
) -> str:
    """
    Helper function untuk semua LLM calls di CV Agent.

    Memanggil Anthropic Claude API dengan system prompt dan user prompt,
    dan mengembalikan text content dari response.

    Exception handling TIDAK dilakukan di sini — setiap caller node
    sudah dibungkus dengan @with_retry decorator yang menangani
    retry logic dan logging untuk semua Anthropic API exceptions.

    Args:
        system_prompt: instruksi untuk model (role, format output, constraints)
        user_prompt: input data yang akan diproses model
        max_tokens: maksimal token dalam response (default 1000)

    Returns:
        String text content dari response model

    Raises:
        anthropic.APIError: kalau API call gagal — dibiarkan propagate
                           ke @with_retry decorator di caller
    """
    logger.debug(
        f"[call_llm] calling model={settings.llm_model}, "
        f"max_tokens={max_tokens}, "
        f"system_prompt_len={len(system_prompt)}, "
        f"user_prompt_len={len(user_prompt)}"
    )

    # Anthropic Python SDK — synchronous call
    # Di Phase 6 kita pakai sync client karena Anthropic SDK
    # belum stabil untuk full async di semua environments
    # Kalau perlu async, bisa wrap dengan asyncio.to_thread()
    response = llm.messages.create(
        model=settings.llm_model,          # dari config — tidak hardcode
        max_tokens=max_tokens,
        system=system_prompt,               # instruksi dan constraints untuk model
        messages=[
            {
                "role": "user",
                "content": user_prompt,     # data yang diproses
            }
        ],
    )

    # Ekstrak text dari content block pertama
    # response.content adalah list — ambil index 0
    # .text adalah text content dari TextBlock
    text_content = response.content[0].text

    logger.debug(
        f"[call_llm] response received, "
        f"output_tokens={response.usage.output_tokens}"
    )

    return text_content