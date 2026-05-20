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
        # Strip internal metadata before sending to Replicate
        api_inputs = {k: v for k, v in inputs.items() if not k.startswith("_")}
        start = time.time()
        try:
            url = await replicate_client.run_model(model_slug, api_inputs)
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


async def run_shared_generation(
    gen_ids: list[int],
    model_slug: str,
    inputs: dict,
    semaphore: asyncio.Semaphore,
) -> None:
    """Run one API call and copy the result to all gen_ids.

    Used for aspect_ratio sweeps where the image is generated once
    and displayed at different CSS aspect ratios.
    """
    async with semaphore:
        for gid in gen_ids:
            await asyncio.to_thread(
                storage.update_generation_status, gid, "running"
            )
        api_inputs = {k: v for k, v in inputs.items() if not k.startswith("_")}
        start = time.time()
        try:
            url = await replicate_client.run_model(model_slug, api_inputs)
            generation_ms = int((time.time() - start) * 1000)
            for gid in gen_ids:
                await asyncio.to_thread(
                    storage.update_generation_status,
                    gid, "complete",
                    output_url=url,
                    generation_ms=generation_ms,
                )
        except Exception as e:
            generation_ms = int((time.time() - start) * 1000)
            for gid in gen_ids:
                await asyncio.to_thread(
                    storage.update_generation_status,
                    gid, "failed",
                    error=str(e),
                    generation_ms=generation_ms,
                )
