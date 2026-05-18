"""Thin async wrappers around the Replicate SDK.

Pure transport — no caching, no parsing, no orchestration.
"""

from __future__ import annotations

import replicate


async def fetch_schema(slug: str) -> dict:
    """Fetch the raw OpenAPI schema dict for a Replicate model."""
    model = await replicate.models.async_get(slug)
    return model.latest_version.openapi_schema


async def run_model(slug: str, inputs: dict) -> str:
    """Run a model and return the first output image URL."""
    output = await replicate.async_run(slug, input=inputs)
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        return str(output[0])
    # FileOutput or other object — convert to string (gives the URL)
    return str(output)
