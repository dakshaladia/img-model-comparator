import asyncio
import json
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
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


def _collect_sweep_values(form, name: str) -> list[str]:
    """Collect sweep values for a given axis name from form data."""
    raw_list = form.getlist(f"sweep__{name}")
    values = []
    if len(raw_list) == 1:
        for v in raw_list[0].split(","):
            v = v.strip()
            if v:
                values.append(v)
    else:
        for v in raw_list:
            v = v.strip()
            if v:
                values.append(v)
    return values


@router.post("/sweep")
async def create_sweep(request: Request):
    form = await request.form()
    slug = form.get("slug", "")

    # Fetch schema for type info
    cached = await asyncio.to_thread(storage.get_cached_schema, slug)
    raw_schema = json.loads(cached) if cached else {}
    inputs_meta = schema.parse_schema(raw_schema) if raw_schema else []
    type_map = {inp.name: inp.type for inp in inputs_meta}

    # Separate fixed inputs from sweep axes (up to 2)
    fixed_inputs = {}
    sweep_axis_names = []

    for key, value in form.items():
        if key == "slug":
            continue
        if key.startswith("input__"):
            name = key[len("input__"):]
            if value == "":
                continue
            input_type = type_map.get(name, "string")
            cast = _cast_value(value, input_type)
            if input_type == "array" and cast == []:
                continue
            fixed_inputs[name] = cast
        elif key.startswith("sweep__") and value.strip():
            name = key[len("sweep__"):]
            if name not in sweep_axis_names and len(sweep_axis_names) < 2:
                sweep_axis_names.append(name)

    # Collect values for each axis
    sweep_axes = []
    for name in sweep_axis_names:
        values_raw = _collect_sweep_values(form, name)
        if values_raw:
            input_type = type_map.get(name, "string")
            cast_values = [_cast_value(v, input_type) for v in values_raw]
            labels = [_make_label(name, v) for v in cast_values]
            sweep_axes.append({
                "input_name": name,
                "values": cast_values,
                "labels": labels,
            })

    # Extract num_outputs as a multiplier
    num_outputs = int(fixed_inputs.pop("num_outputs", 1) or 1)
    fixed_inputs.pop("max_images", None)
    if num_outputs < 1:
        num_outputs = 1

    # ── Two-axis sweep ───────────────────────────────────────────────
    if len(sweep_axes) == 2:
        axis1, axis2 = sweep_axes[0], sweep_axes[1]
        total = len(axis1["values"]) * len(axis2["values"]) * num_outputs
        truncated = total > MAX_SWEEP_SIZE

        # Trim to fit cap
        if truncated:
            max_cells = MAX_SWEEP_SIZE // num_outputs
            if max_cells < 1:
                max_cells = 1
                num_outputs = MAX_SWEEP_SIZE
            # Reduce axis2 first, then axis1
            while len(axis1["values"]) * len(axis2["values"]) > max_cells:
                if len(axis2["values"]) > 1:
                    axis2["values"] = axis2["values"][:-1]
                    axis2["labels"] = axis2["labels"][:-1]
                elif len(axis1["values"]) > 1:
                    axis1["values"] = axis1["values"][:-1]
                    axis1["labels"] = axis1["labels"][:-1]
                else:
                    break

        axis_config = [axis1, axis2]

        sweep_run_id = await asyncio.to_thread(
            storage.create_sweep_run, slug, fixed_inputs, axis_config
        )

        # Cartesian product: rows (axis2) × cols (axis1)
        generations = []
        gen_grid = []  # 2D list: gen_grid[row][col] = gen dict
        pos = 0
        for row_idx, (v2, l2) in enumerate(zip(axis2["values"], axis2["labels"])):
            row = []
            for col_idx, (v1, l1) in enumerate(zip(axis1["values"], axis1["labels"])):
                gen_inputs = {**fixed_inputs, axis1["input_name"]: v1, axis2["input_name"]: v2}
                compound_label = f"{l1}, {l2}"
                if len(compound_label) > 60:
                    compound_label = compound_label[:57] + "..."
                for rep in range(num_outputs):
                    rep_label = f"{compound_label} #{rep + 1}" if num_outputs > 1 else compound_label
                    gen_id = await asyncio.to_thread(
                        storage.create_generation, sweep_run_id, gen_inputs, pos, rep_label
                    )
                    gen = await asyncio.to_thread(storage.get_generation, gen_id)
                    generations.append(gen)
                    row.append(gen)
                    asyncio.create_task(
                        sweep_engine.run_one_generation(gen_id, slug, gen_inputs, _semaphore)
                    )
                    pos += 1
            gen_grid.append(row)

        return templates.TemplateResponse(request, "partials/grid.html", {
            "generations": generations,
            "grid_cols": "",
            "truncated": truncated,
            "two_axis": True,
            "gen_grid": gen_grid,
            "col_headers": axis1["labels"],
            "row_headers": axis2["labels"],
            "col_axis_name": axis1["input_name"],
            "row_axis_name": axis2["input_name"],
        })

    # ── Single-axis sweep ────────────────────────────────────────────
    elif len(sweep_axes) == 1:
        axis = sweep_axes[0]
        total = len(axis["values"]) * num_outputs
        truncated = total > MAX_SWEEP_SIZE
        if truncated:
            max_values = MAX_SWEEP_SIZE // num_outputs
            if max_values < 1:
                max_values = 1
                num_outputs = MAX_SWEEP_SIZE
            axis["values"] = axis["values"][:max_values]
            axis["labels"] = axis["labels"][:max_values]

        axis_config = axis
        axis_config["num_outputs"] = num_outputs

        sweep_run_id = await asyncio.to_thread(
            storage.create_sweep_run, slug, fixed_inputs, axis_config
        )

        generations = []
        pos = 0
        for val, label in zip(axis["values"], axis["labels"]):
            gen_inputs = {**fixed_inputs, axis["input_name"]: val}
            for rep in range(num_outputs):
                rep_label = f"{label} #{rep + 1}" if num_outputs > 1 else label
                gen_id = await asyncio.to_thread(
                    storage.create_generation, sweep_run_id, gen_inputs, pos, rep_label
                )
                gen = await asyncio.to_thread(storage.get_generation, gen_id)
                generations.append(gen)
                asyncio.create_task(
                    sweep_engine.run_one_generation(gen_id, slug, gen_inputs, _semaphore)
                )
                pos += 1

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
            "two_axis": False,
        })

    # ── No sweep ─────────────────────────────────────────────────────
    else:
        truncated = False
        if num_outputs > MAX_SWEEP_SIZE:
            num_outputs = MAX_SWEEP_SIZE
            truncated = True

        sweep_run_id = await asyncio.to_thread(
            storage.create_sweep_run, slug, fixed_inputs, None
        )

        generations = []
        for i in range(num_outputs):
            label = f"#{i + 1}" if num_outputs > 1 else ""
            gen_id = await asyncio.to_thread(
                storage.create_generation, sweep_run_id, fixed_inputs, i, label
            )
            gen = await asyncio.to_thread(storage.get_generation, gen_id)
            generations.append(gen)
            asyncio.create_task(
                sweep_engine.run_one_generation(gen_id, slug, fixed_inputs, _semaphore)
            )

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
            "two_axis": False,
        })


@router.get("/cell/{gen_id}")
async def poll_cell(request: Request, gen_id: int):
    gen = await asyncio.to_thread(storage.get_generation, gen_id)
    if gen and gen["status"] in ("complete", "failed"):
        # Parse inputs JSON for caption display
        gen_inputs = {}
        try:
            gen_inputs = json.loads(gen.get("inputs", "{}"))
        except (json.JSONDecodeError, TypeError):
            pass
        return templates.TemplateResponse(request, "partials/cell_final.html", {
            "gen": gen,
            "gen_inputs": gen_inputs,
        })
    return templates.TemplateResponse(request, "partials/cell_polling.html", {
        "gen": gen,
    })


@router.get("/download/{gen_id}")
async def download_image(gen_id: int):
    """Proxy download so the browser treats it as same-origin."""
    gen = await asyncio.to_thread(storage.get_generation, gen_id)
    if not gen or gen["status"] != "complete" or not gen["output_url"]:
        return {"error": "not found"}

    url = gen["output_url"]
    # Derive filename from URL path
    path = urlparse(url).path
    ext = path.rsplit(".", 1)[-1] if "." in path else "webp"
    filename = f"sweep_{gen_id}.{ext}"

    async def stream():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk

    return StreamingResponse(
        stream(),
        media_type=f"image/{ext}",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
