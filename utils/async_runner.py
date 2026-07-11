"""Helper to run async coroutines from sync Flask views."""

import asyncio
from typing import TypeVar, Coroutine

T = TypeVar("T")


def run_async(coro: Coroutine[None, None, T]) -> T:
    """Run an async coroutine in a sync context."""
    return asyncio.run(coro)
