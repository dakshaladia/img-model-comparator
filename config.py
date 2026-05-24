import os

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

DATABASE_PATH = "data/sweep.db"

SUPPORTED_MODEL_SLUGS = [
    "black-forest-labs/flux-schnell",
    "black-forest-labs/flux-1.1-pro",
    "bytedance/seedream-4",
    "google/imagen-4-fast",
    "recraft-ai/recraft-v3",
    "stability-ai/stable-diffusion-3.5-large",
]

SUPPORTED_MODELS = {
    "black-forest-labs/flux-schnell": "Flux Schnell",
    "black-forest-labs/flux-1.1-pro": "Flux 1.1 Pro",
    "bytedance/seedream-4": "Seedream 4",
    "google/imagen-4-fast": "Imagen 4 Fast",
    "recraft-ai/recraft-v3": "Recraft v3",
    "stability-ai/stable-diffusion-3.5-large": "SD 3.5 Large",
}

MODEL_DESCRIPTIONS = {
    "black-forest-labs/flux-schnell": "Fast photorealistic generation, great for rapid iteration",
    "black-forest-labs/flux-1.1-pro": "High-quality photorealistic images with fine detail",
    "bytedance/seedream-4": "Strong prompt adherence with vibrant, stylized outputs",
    "google/imagen-4-fast": "Photorealistic with excellent text rendering",
    "recraft-ai/recraft-v3": "Illustration-focused — logos, icons, and vector-style art",
    "stability-ai/stable-diffusion-3.5-large": "Classic diffusion aesthetic, versatile and community-proven",
}

COST_PER_IMAGE_USD = {
    "black-forest-labs/flux-schnell": 0.003,
    "black-forest-labs/flux-1.1-pro": 0.04,
    "google/imagen-4-fast": 0.02,
    "bytedance/seedream-4": 0.025,
    "recraft-ai/recraft-v3": 0.04,
    "stability-ai/stable-diffusion-3.5-large": 0.065,
}

NEVER_SWEEP_INPUT_NAMES = {"image", "mask", "init_image", "control_image", "num_outputs", "max_images"}

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
