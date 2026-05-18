"""Smoke test for services/replicate_client.py.

Fetches schemas for all 6 supported models, caches them,
then runs a single generation on flux-schnell (~$0.003).

Usage: python scripts/test_replicate.py
"""

import asyncio
import json
import sys
import os

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from config import SUPPORTED_MODEL_SLUGS
from services.replicate_client import fetch_schema, run_model
from services.storage import init_db, cache_schema, get_cached_schema


async def test_schemas():
    print("=" * 60)
    print("PART 1: Schema fetch for all 6 models")
    print("=" * 60)

    init_db()

    for slug in SUPPORTED_MODEL_SLUGS:
        schema = await fetch_schema(slug)
        input_schema = schema.get("components", {}).get("schemas", {}).get("Input", {})
        properties = input_schema.get("properties", {})
        input_names = list(properties.keys())

        print(f"\n{slug}: {len(input_names)} inputs")
        for name in input_names[:3]:
            prop = properties[name]
            prop_type = prop.get("type", prop.get("allOf", "unknown"))
            default = prop.get("default", "—")
            print(f"  {name} ({prop_type}) default={default}")

        # Cache the raw schema
        cache_schema(slug, json.dumps(schema))

    print("\n" + "-" * 60)
    print("Cached schemas in SQLite:")
    for slug in SUPPORTED_MODEL_SLUGS:
        cached = get_cached_schema(slug)
        if cached:
            print(f"  {slug}: {len(cached)} bytes")
        else:
            print(f"  {slug}: NOT CACHED")


async def test_generation():
    print("\n" + "=" * 60)
    print("PART 2: Single generation (flux-schnell, ~$0.003)")
    print("=" * 60)

    url = await run_model(
        "black-forest-labs/flux-schnell",
        {"prompt": "a red cube on a white background"},
    )
    print(f"\nOutput URL: {url}")


async def main():
    await test_schemas()
    await test_generation()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
