"""Fire-and-forget generation worker.

Each call runs one Replicate generation inside a shared semaphore,
updating SQLite status as it progresses.
"""

from __future__ import annotations

import asyncio
import time

from services import replicate_client, storage


async def run_one_generation(
    gen_id: int,
    model_slug: str,
    inputs: dict,
    semaphore: asyncio.Semaphore,
) -> None:
    async with semaphore:
        await asyncio.to_thread(
            storage.update_generation_status, gen_id, "running"
        )
        start = time.time()
        try:
            url = await replicate_client.run_model(model_slug, inputs)
            generation_ms = int((time.time() - start) * 1000)
            await asyncio.to_thread(
                storage.update_generation_status,
                gen_id, "complete",
                output_url=url,
                generation_ms=generation_ms,
            )
        except Exception as e:
            generation_ms = int((time.time() - start) * 1000)
            await asyncio.to_thread(
                storage.update_generation_status,
                gen_id, "failed",
                error=str(e),
                generation_ms=generation_ms,
            )
