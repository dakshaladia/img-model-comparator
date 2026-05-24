import asyncio
import json
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates

from config import MAX_CONCURRENCY, MAX_SWEEP_SIZE, SUPPORTED_MODELS
from services import replicate_client, schema, storage, sweep_engine

router = APIRouter()
templates = Jinja2Templates(directory="templates")

_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)


def _cast_value(value: str, input_type: str):
    """Cast a form string to the appropriate Python type."""
    if input_type == "integer":
        try:
            return int(value)
        except (ValueError, TypeError):
            return value
    if input_type == "number":
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
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


async def _filter_inputs_for_model(model_slug: str, inputs: dict) -> dict:
    """Return only the inputs that this model's schema defines."""
    cached = await asyncio.to_thread(storage.get_cached_schema, model_slug)
    if not cached:
        raw = await replicate_client.fetch_schema(model_slug)
        await asyncio.to_thread(storage.cache_schema, model_slug, json.dumps(raw))
        cached = json.dumps(raw)
    raw_schema = json.loads(cached)
    valid_names = set(
        raw_schema.get("components", {}).get("schemas", {})
        .get("Input", {}).get("properties", {}).keys()
    )
    return {k: v for k, v in inputs.items() if k in valid_names}


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

    # Validate: prompt must be present (fixed or swept)
    has_prompt = "prompt" in fixed_inputs or any(a["input_name"] == "prompt" for a in sweep_axes)
    if not has_prompt:
        return templates.TemplateResponse(request, "partials/grid.html", {
            "generations": [],
            "grid_cols": "grid-cols-1",
            "truncated": False,
            "two_axis": False,
            "error": "Prompt is required. Enter a prompt or expand prompt variations before running.",
        })

    # Extract num_outputs as a multiplier
    num_outputs = int(fixed_inputs.pop("num_outputs", 1) or 1)
    fixed_inputs.pop("max_images", None)
    if num_outputs < 1:
        num_outputs = 1

    # Collect cross-model comparison models
    compare_models = form.getlist("compare_model")
    all_models = [slug] + [m for m in compare_models if m != slug]
    is_cross_model = len(all_models) > 1

    # Cross-model + 2 param axes = not supported
    if is_cross_model and len(sweep_axes) >= 2:
        return templates.TemplateResponse(request, "partials/grid.html", {
            "generations": [],
            "grid_cols": "grid-cols-1",
            "truncated": False,
            "two_axis": False,
            "error": "Cross-model comparison supports at most one parameter sweep. Disable one parameter sweep to compare across models.",
        })

    # ── Cross-model sweep ────────────────────────────────────────────
    if is_cross_model:
        model_labels = [SUPPORTED_MODELS.get(m, m) for m in all_models]

        if len(sweep_axes) == 1:
            # Models × parameter values = table
            axis = sweep_axes[0]
            total = len(all_models) * len(axis["values"]) * num_outputs
            truncated = total > MAX_SWEEP_SIZE
            if truncated:
                max_cells = MAX_SWEEP_SIZE // num_outputs
                if max_cells < 1:
                    max_cells = 1
                    num_outputs = MAX_SWEEP_SIZE
                while len(all_models) * len(axis["values"]) > max_cells:
                    if len(axis["values"]) > 1:
                        axis["values"] = axis["values"][:-1]
                        axis["labels"] = axis["labels"][:-1]
                    elif len(all_models) > 1:
                        all_models = all_models[:-1]
                        model_labels = model_labels[:-1]
                    else:
                        break

            axis_config = {"axis": axis, "models": all_models}
            sweep_run_id = await asyncio.to_thread(
                storage.create_sweep_run, slug, fixed_inputs, axis_config
            )

            generations = []
            gen_grid = []
            pos = 0
            for model_slug, model_label in zip(all_models, model_labels):
                filtered = await _filter_inputs_for_model(model_slug, fixed_inputs)
                row = []
                for val, label in zip(axis["values"], axis["labels"]):
                    gen_inputs = {**filtered, axis["input_name"]: val, "_model_slug": model_slug}
                    compound_label = f"{model_label}, {label}"
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
                            sweep_engine.run_one_generation(gen_id, model_slug, gen_inputs, _semaphore)
                        )
                        pos += 1
                gen_grid.append(row)

            return templates.TemplateResponse(request, "partials/grid.html", {
                "generations": generations,
                "grid_cols": "",
                "truncated": truncated,
                "two_axis": True,
                "gen_grid": gen_grid,
                "col_headers": axis["labels"],
                "row_headers": model_labels,
                "col_axis_name": axis["input_name"],
                "row_axis_name": "model",
            })

        else:
            # Models only, no param sweep — flat grid
            total = len(all_models) * num_outputs
            truncated = total > MAX_SWEEP_SIZE
            if truncated:
                max_models = MAX_SWEEP_SIZE // num_outputs
                if max_models < 1:
                    max_models = 1
                    num_outputs = MAX_SWEEP_SIZE
                all_models = all_models[:max_models]
                model_labels = model_labels[:max_models]

            axis_config = {"models": all_models}
            sweep_run_id = await asyncio.to_thread(
                storage.create_sweep_run, slug, fixed_inputs, axis_config
            )

            generations = []
            pos = 0
            for model_slug, model_label in zip(all_models, model_labels):
                filtered = await _filter_inputs_for_model(model_slug, fixed_inputs)
                filtered_with_model = {**filtered, "_model_slug": model_slug}
                for rep in range(num_outputs):
                    rep_label = f"{model_label} #{rep + 1}" if num_outputs > 1 else model_label
                    gen_id = await asyncio.to_thread(
                        storage.create_generation, sweep_run_id, filtered_with_model, pos, rep_label
                    )
                    gen = await asyncio.to_thread(storage.get_generation, gen_id)
                    generations.append(gen)
                    asyncio.create_task(
                        sweep_engine.run_one_generation(gen_id, model_slug, filtered, _semaphore)
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
        is_aspect_sweep = axis["input_name"] == "aspect_ratio"
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
        all_gen_ids = []
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
                all_gen_ids.append(gen_id)
                if not is_aspect_sweep:
                    # Normal sweep: one API call per cell
                    asyncio.create_task(
                        sweep_engine.run_one_generation(gen_id, slug, gen_inputs, _semaphore)
                    )
                pos += 1

        if is_aspect_sweep:
            # Aspect ratio sweep: one API call, share result across all cells
            asyncio.create_task(
                sweep_engine.run_shared_generation(all_gen_ids, slug, fixed_inputs, _semaphore)
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


@router.get("/cell/{gen_id}/inputs")
async def get_cell_inputs(gen_id: int):
    """Return the inputs and model slug for a generation (used by Branch)."""
    gen = await asyncio.to_thread(storage.get_generation, gen_id)
    if not gen:
        return {"inputs": {}, "model_slug": ""}
    inputs = {}
    try:
        inputs = json.loads(gen.get("inputs", "{}"))
    except (json.JSONDecodeError, TypeError):
        pass
    # _model_slug is injected per-cell for cross-model sweeps; fall back to sweep_run
    model_slug = inputs.pop("_model_slug", None)
    if not model_slug:
        sweep_run = await asyncio.to_thread(storage.get_sweep_run, gen["sweep_run_id"])
        model_slug = sweep_run["model_slug"] if sweep_run else ""
    return {"inputs": inputs, "model_slug": model_slug}
