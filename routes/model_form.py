import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from services import replicate_client, schema, storage

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/model-form")
async def model_form(request: Request, slug: str):
    cached = await asyncio.to_thread(storage.get_cached_schema, slug)

    if cached:
        raw = json.loads(cached)
    else:
        raw = await replicate_client.fetch_schema(slug)
        await asyncio.to_thread(storage.cache_schema, slug, json.dumps(raw))

    inputs = schema.parse_schema(raw)

    return templates.TemplateResponse(request, "partials/form.html", {
        "inputs": inputs,
        "slug": slug,
    })
