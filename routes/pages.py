from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from config import SUPPORTED_MODEL_SLUGS

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "model_slugs": SUPPORTED_MODEL_SLUGS,
    })
