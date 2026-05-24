from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from services import prompt_expander

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.post("/prompt-expand")
async def prompt_expand(request: Request):
    form = await request.form()
    base_prompt = form.get("base_prompt", "")
    direction = form.get("direction", "")
    try:
        count = int(form.get("count", 5))
    except (ValueError, TypeError):
        count = 5

    try:
        variations = await prompt_expander.expand_prompt(base_prompt, direction, count)
    except Exception:
        return templates.TemplateResponse(request, "partials/prompt_variations.html", {
            "variations": [base_prompt] * count,
        })

    return templates.TemplateResponse(request, "partials/prompt_variations.html", {
        "variations": variations,
    })
