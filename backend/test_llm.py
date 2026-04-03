import asyncio
from agents.llm_client import call_llm


async def test():
    result = await call_llm(
        system_prompt="You are a helpful assistant.",
        user_prompt="Reply with exactly: ANTHROPIC_OK",
        max_tokens=20,
    )
    print("Response:", result)

asyncio.run(test())