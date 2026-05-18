import os

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

DATABASE_PATH = "data/sweep.db"

SUPPORTED_MODEL_SLUGS = [
    "black-forest-labs/flux-schnell",
    "black-forest-labs/flux-1.1-pro",
    "google/imagen-4-fast",
    "bytedance/seedream-4",
    "recraft-ai/recraft-v3",
    "stability-ai/stable-diffusion-3.5-large",
]

NEVER_SWEEP_INPUT_NAMES = {"image", "mask", "init_image", "control_image"}

PROMPT_SWEEP_DIRECTIONS = [
    "camera angle",
    "lighting",
    "art style",
    "mood",
    "color palette",
    "time of day",
    "weather",
    "composition",
]

MAX_SWEEP_SIZE = 9
MAX_CONCURRENCY = 6
SCHEMA_CACHE_TTL_SECONDS = 86400  # 24 hours
