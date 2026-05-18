import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from config import MAX_CONCURRENCY, MAX_SWEEP_SIZE
from services import schema, storage, sweep_engine

router = APIRouter()
templates = Jinja2Templates(directory="templates")

_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)


def _cast_value(value: str, input_type: str):
    """Cast a form string to the appropriate Python type."""
    if input_type == "integer":
        return int(value)
    if input_type == "number":
        return float(value)
    if input_type == "boolean":
        return value.lower() == "true"
    if input_type == "array":
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return []
    return value


def _make_label(name: str, value) -> str:
    """Build a display label, truncated to 60 chars."""
    raw = f"{name}={value}"
    if len(raw) > 60:
        return raw[:57] + "..."
    return raw


@router.post("/sweep")
async def create_sweep(request: Request):
    form = await request.form()
    slug = form.get("slug", "")

    # Fetch schema for type info
    cached = await asyncio.to_thread(storage.get_cached_schema, slug)
    raw_schema = json.loads(cached) if cached else {}
    inputs_meta = schema.parse_schema(raw_schema) if raw_schema else []
    type_map = {inp.name: inp.type for inp in inputs_meta}

    # Separate fixed inputs from sweep axis
    fixed_inputs = {}
    sweep_name = None
    sweep_values_raw: list[str] = []

    for key, value in form.items():
        if key == "slug":
            continue
        if key.startswith("input__"):
            name = key[len("input__"):]
            if value == "":
                continue
            input_type = type_map.get(name, "string")
            cast = _cast_value(value, input_type)
            # Skip empty arrays — let Replicate use its default
            if input_type == "array" and cast == []:
                continue
            fixed_inputs[name] = cast
        elif key.startswith("sweep__") and not sweep_name:
            sweep_name = key[len("sweep__"):]

    # Collect sweep values: checkboxes submit multiple entries, text uses commas
    if sweep_name:
        raw_list = form.getlist(f"sweep__{sweep_name}")
        for raw in raw_list:
            for v in raw.split(","):
                v = v.strip()
                if v:
                    sweep_values_raw.append(v)

    # Build generations list
    if sweep_name and sweep_values_raw:
        input_type = type_map.get(sweep_name, "string")
        truncated = len(sweep_values_raw) > MAX_SWEEP_SIZE
        sweep_values_raw = sweep_values_raw[:MAX_SWEEP_SIZE]
        cast_values = [_cast_value(v, input_type) for v in sweep_values_raw]
        labels = [_make_label(sweep_name, v) for v in cast_values]

        axis_config = {
            "input_name": sweep_name,
            "values": cast_values,
            "labels": labels,
        }

        sweep_run_id = await asyncio.to_thread(
            storage.create_sweep_run, slug, fixed_inputs, axis_config
        )

        generations = []
        for i, (val, label) in enumerate(zip(cast_values, labels)):
            gen_inputs = {**fixed_inputs, sweep_name: val}
            gen_id = await asyncio.to_thread(
                storage.create_generation, sweep_run_id, gen_inputs, i, label
            )
            gen = await asyncio.to_thread(storage.get_generation, gen_id)
            generations.append(gen)
            asyncio.create_task(
                sweep_engine.run_one_generation(gen_id, slug, gen_inputs, _semaphore)
            )
    else:
        # Single generation, no sweep
        axis_config = None
        truncated = False

        sweep_run_id = await asyncio.to_thread(
            storage.create_sweep_run, slug, fixed_inputs, axis_config
        )

        gen_id = await asyncio.to_thread(
            storage.create_generation, sweep_run_id, fixed_inputs, 0, ""
        )
        gen = await asyncio.to_thread(storage.get_generation, gen_id)
        generations = [gen]
        asyncio.create_task(
            sweep_engine.run_one_generation(gen_id, slug, fixed_inputs, _semaphore)
        )

    # Determine grid columns
    n = len(generations)
    if n <= 1:
        grid_cols = "grid-cols-1"
    elif n in (2, 4):
        grid_cols = "grid-cols-2"
    else:
        grid_cols = "grid-cols-3"

    return templates.TemplateResponse(request, "partials/grid.html", {
        "generations": generations,
        "grid_cols": grid_cols,
        "truncated": truncated,
    })


@router.get("/cell/{gen_id}")
async def poll_cell(request: Request, gen_id: int):
    gen = await asyncio.to_thread(storage.get_generation, gen_id)
    if gen and gen["status"] in ("complete", "failed"):
        return templates.TemplateResponse(request, "partials/cell_final.html", {
            "gen": gen,
        })
    return templates.TemplateResponse(request, "partials/cell_polling.html", {
        "gen": gen,
    })
