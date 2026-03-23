# cv-agent/backend/workflow/retry.py

"""
Retry decorator untuk LangGraph workflow nodes.

Menyediakan with_retry decorator yang membungkus async node functions
dengan exponential backoff retry logic menggunakan tenacity library.

Hanya diapply ke nodes yang akan memanggil LLM (Phase 6).
Nodes deterministik (select_best_version, render_document) tidak perlu ini.
"""

import functools
import logging
from typing import Callable

from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
)

from config import get_settings

logger = logging.getLogger("workflow.retry")


def with_retry(func: Callable) -> Callable:
    """
    Decorator yang membungkus async node function dengan retry logic.

    Retry behavior:
    - Maksimal LLM_MAX_RETRIES kali (dari settings)
    - Exponential backoff: mulai 2 detik, maksimal 10 detik
    - Log warning setiap retry attempt
    - Log critical error dan re-raise kalau semua retry habis

    Usage:
        @with_retry
        async def my_node(state: CVAgentState) -> dict:
            ...

    Args:
        func: async node function yang akan dibungkus

    Returns:
        Wrapped function dengan retry behavior
    """
    # functools.wraps memastikan metadata function asli (nama, docstring)
    # tetap ada di wrapped function — penting untuk LangGraph node registration
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        settings = get_settings()
        max_retries = settings.llm_max_retries
        node_name = func.__name__

        try:
            # AsyncRetrying adalah context manager untuk async retry
            # Setiap iterasi mencoba menjalankan function
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_retries),
                wait=wait_exponential(
                    multiplier=1,   # base multiplier
                    min=2,          # minimum wait 2 detik
                    max=10,         # maximum wait 10 detik
                ),
                # reraise=False agar kita bisa handle error sendiri di except block
                reraise=False,
            ):
                with attempt:
                    # Cek apakah ini bukan attempt pertama
                    # attempt.retry_state.attempt_number dimulai dari 1
                    attempt_number = attempt.retry_state.attempt_number
                    if attempt_number > 1:
                        logger.warning(
                            f"[{node_name}] retry attempt {attempt_number}/{max_retries} "
                            f"after previous failure"
                        )

                    # Jalankan function asli
                    return await func(*args, **kwargs)

        except RetryError as retry_error:
            # RetryError dilempar tenacity setelah semua attempt habis
            # Unwrap exception asli dari RetryError untuk log yang lebih informatif
            original_exception = retry_error.last_attempt.exception()

            logger.critical(
                f"[{node_name}] all {max_retries} retry attempts exhausted. "
                f"Last error: {type(original_exception).__name__}: {original_exception}. "
                f"LangGraph will pause workflow at this node."
            )

            # Re-raise exception asli (bukan RetryError) agar LangGraph
            # bisa menangani dengan benar dan pause workflow di node ini
            raise original_exception

    return wrapper