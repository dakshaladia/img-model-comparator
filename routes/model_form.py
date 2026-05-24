import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from config import PROMPT_SWEEP_DIRECTIONS
from services import replicate_client, schema, storage

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/model-form")
async def model_form(request: Request, slug: str):
    try:
        cached = await asyncio.to_thread(storage.get_cached_schema, slug)

        if cached:
            raw = json.loads(cached)
        else:
            raw = await replicate_client.fetch_schema(slug)
            await asyncio.to_thread(storage.cache_schema, slug, json.dumps(raw))

        inputs = schema.parse_schema(raw)
    except Exception:
        from fastapi.responses import HTMLResponse
        return HTMLResponse(
            '<p class="mono" style="font-size:12px;color:var(--danger)">'
            "Failed to load model schema. Check that the model slug is valid and Replicate is reachable.</p>"
        )

    return templates.TemplateResponse(request, "partials/form.html", {
        "inputs": inputs,
        "slug": slug,
        "directions": PROMPT_SWEEP_DIRECTIONS,
    })
