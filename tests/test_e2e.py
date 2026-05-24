"""End-to-end tests via FastAPI TestClient. No external API calls."""

from services import storage


# ── Index page ───────────────────────────────────────────────────────

def test_index_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "Sweep" in html
    assert "Parameter sweep" in html
    assert html.count("<option") == 6
    assert "Flux Schnell" in html
    assert 'value="black-forest-labs/flux-schnell"' in html
    assert "Run a sweep to see results" in html
    assert "SWEEP_COSTS" in html


# ── Model form ───────────────────────────────────────────────────────

def test_model_form(client):
    resp = client.get("/model-form?slug=black-forest-labs/flux-schnell")
    assert resp.status_code == 200
    html = resp.text
    assert 'name="input__prompt"' in html
    assert 'name="input__seed"' in html
    assert 'name="input__aspect_ratio"' in html
    assert 'data-sweep-btn="prompt"' in html
    assert 'hx-post="/sweep"' in html
    assert "cost-preview" in html


def test_model_form_sweep_toggle_not_on_image(client):
    resp = client.get("/model-form?slug=black-forest-labs/flux-schnell")
    html = resp.text
    assert 'data-sweep-btn="image"' not in html


def test_model_form_has_prompt_sweep_ui(client):
    resp = client.get("/model-form?slug=black-forest-labs/flux-schnell")
    html = resp.text
    assert "prompt-direction" in html
    assert "prompt-count" in html
    assert "camera angle" in html
    assert 'hx-post="/prompt-expand"' in html


# ── POST /sweep — single generation ─────────────────────────────────

def test_sweep_single_gen(client):
    resp = client.post("/sweep", data={
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "a test image",
    })
    assert resp.status_code == 200
    html = resp.text
    assert "grid-cols-1" in html
    assert html.count("hx-get") == 1
    assert "Generating" in html


# ── POST /sweep — numeric sweep ─────────────────────────────────────

def test_sweep_numeric(client):
    resp = client.post("/sweep", data={
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__num_outputs": "1,2,3,4",
    })
    assert resp.status_code == 200
    html = resp.text
    assert "grid-cols-2" in html
    assert html.count("hx-get") == 4
    assert "num_outputs=1" in html
    assert "num_outputs=4" in html


def test_sweep_numeric_3_values(client):
    resp = client.post("/sweep", data={
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__cfg": "1,5,10",
    })
    html = resp.text
    assert "grid-cols-3" in html
    assert html.count("hx-get") == 3


# ── POST /sweep — enum sweep ────────────────────────────────────────

def test_sweep_enum(client):
    resp = client.post("/sweep", content="slug=black-forest-labs/flux-schnell&input__prompt=test&sweep__aspect_ratio=1:1&sweep__aspect_ratio=16:9&sweep__aspect_ratio=9:16",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert resp.status_code == 200
    html = resp.text
    assert "grid-cols-3" in html
    assert html.count("hx-get") == 3
    assert "aspect_ratio=1:1" in html
    assert "aspect_ratio=16:9" in html


# ── POST /sweep — prompt sweep ───────────────────────────────────────

def test_sweep_prompt(client):
    resp = client.post("/sweep",
        content="slug=black-forest-labs/flux-schnell&sweep__prompt=a+cat+in+sunlight&sweep__prompt=a+cat+in+moonlight&sweep__prompt=a+cat+in+neon",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert resp.status_code == 200
    html = resp.text
    assert "grid-cols-3" in html
    assert html.count("hx-get") == 3
    assert "prompt=" in html


def test_sweep_prompt_labels_truncated(client):
    long = "a very detailed and elaborate scene " * 5
    body = "slug=black-forest-labs/flux-schnell&sweep__prompt=" + long.replace(" ", "+") + "&sweep__prompt=" + (long + " at night").replace(" ", "+")
    resp = client.post("/sweep", content=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    html = resp.text
    assert "..." in html


# ── POST /sweep — truncation ────────────────────────────────────────

def test_sweep_truncation(client):
    resp = client.post("/sweep", data={
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__seed": ",".join(str(i) for i in range(15)),
    })
    html = resp.text
    assert "truncated to 9" in html
    assert html.count("hx-get") == 9


# ── POST /sweep — cross-model sweep ──────────────────────────────────

def test_sweep_cross_model_flat(client):
    """Cross-model with no param sweep = flat grid, one cell per model."""
    resp = client.post("/sweep", content="slug=black-forest-labs/flux-schnell&input__prompt=test&compare_model=google/imagen-4-fast",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert resp.status_code == 200
    html = resp.text
    assert html.count("hx-get") == 2, "Should have 2 cells (2 models)"


def test_sweep_cross_model_with_param(client):
    """Cross-model + 1-axis param sweep = table."""
    resp = client.post("/sweep", content="slug=black-forest-labs/flux-schnell&input__prompt=test&compare_model=google/imagen-4-fast&sweep__seed=1,2",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert resp.status_code == 200
    html = resp.text
    assert "<table" in html, "Cross-model + param should render as table"
    assert html.count("hx-get") == 4, "2 models x 2 values = 4 cells"


def test_sweep_cross_model_blocks_two_axes(client):
    """Cross-model + 2 param sweeps = error."""
    resp = client.post("/sweep", content="slug=black-forest-labs/flux-schnell&input__prompt=test&compare_model=google/imagen-4-fast&sweep__seed=1,2&sweep__num_outputs=1,2",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert resp.status_code == 200
    html = resp.text
    assert "Disable one parameter sweep" in html


# ── POST /sweep — two-axis sweep ─────────────────────────────────────

def test_sweep_two_axis(client):
    resp = client.post("/sweep", content="slug=black-forest-labs/flux-schnell&input__prompt=test&sweep__num_outputs=1,2&sweep__aspect_ratio=1:1&sweep__aspect_ratio=16:9",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert resp.status_code == 200
    html = resp.text
    assert "<table" in html, "Two-axis should render as table"
    assert "<th" in html, "Should have header cells"
    assert html.count("hx-get") == 4, "2x2 = 4 cells"
    assert "&times;" in html, "Sheet header should show axis names with x"


def test_sweep_two_axis_labels(client):
    resp = client.post("/sweep", data={
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__num_outputs": "1,2",
        "sweep__seed": "42,99",
    })
    html = resp.text
    assert "num_outputs=1" in html
    assert "seed=42" in html


# ── GET /cell/{id} — polling states ─────────────────────────────────

def test_cell_pending(client):
    # Create a generation manually so we can poll it
    run_id = storage.create_sweep_run("test/model", {}, {})
    gen_id = storage.create_generation(run_id, {}, 0, "test")

    resp = client.get(f"/cell/{gen_id}")
    assert resp.status_code == 200
    html = resp.text
    assert "hx-get" in html
    assert "Generating" in html


def test_cell_complete(client):
    run_id = storage.create_sweep_run("test/model", {}, {})
    gen_id = storage.create_generation(run_id, {}, 0, "seed=42")
    storage.update_generation_status(
        gen_id, "complete",
        output_url="https://example.com/img.webp",
        generation_ms=1500,
    )

    resp = client.get(f"/cell/{gen_id}")
    assert resp.status_code == 200
    html = resp.text
    assert "hx-get" not in html
    assert "https://example.com/img.webp" in html
    assert 'target="_blank"' in html
    assert "1.5s" in html
    assert "seed=42" in html


def test_cell_failed(client):
    run_id = storage.create_sweep_run("test/model", {}, {})
    gen_id = storage.create_generation(run_id, {}, 0, "test")
    storage.update_generation_status(gen_id, "failed", error="Rate limited")

    resp = client.get(f"/cell/{gen_id}")
    assert resp.status_code == 200
    html = resp.text
    assert "hx-get" not in html
    assert "Rate limited" in html
    assert "frame--failed" in html


# ── GET /cell/{id}/inputs — branch feature ─────────────────────────

def test_cell_inputs_returns_inputs_and_slug(client):
    """Branch endpoint returns stored inputs and model slug."""
    run_id = storage.create_sweep_run("black-forest-labs/flux-schnell", {"prompt": "test"}, {})
    gen_id = storage.create_generation(run_id, {"prompt": "test", "seed": 42}, 0, "seed=42")

    resp = client.get(f"/cell/{gen_id}/inputs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["inputs"]["prompt"] == "test"
    assert data["inputs"]["seed"] == 42
    assert data["model_slug"] == "black-forest-labs/flux-schnell"


def test_cell_inputs_cross_model_uses_embedded_slug(client):
    """Cross-model generations embed _model_slug in inputs; branch returns it."""
    run_id = storage.create_sweep_run("black-forest-labs/flux-schnell", {}, {"models": ["a", "b"]})
    gen_id = storage.create_generation(
        run_id,
        {"prompt": "test", "_model_slug": "google/imagen-4-fast"},
        0, "Imagen"
    )

    resp = client.get(f"/cell/{gen_id}/inputs")
    data = resp.json()
    assert data["model_slug"] == "google/imagen-4-fast"
    assert "_model_slug" not in data["inputs"]


def test_cell_inputs_not_found(client):
    resp = client.get("/cell/99999/inputs")
    data = resp.json()
    assert data["inputs"] == {}
    assert data["model_slug"] == ""


# ── GET /download/{id} ─────────────────────────────────────────────

def test_download_not_found(client):
    resp = client.get("/download/99999")
    assert resp.status_code == 200
    assert resp.json()["error"] == "not found"


def test_download_incomplete_gen(client):
    """Download returns not-found for non-complete generations."""
    run_id = storage.create_sweep_run("test/model", {}, {})
    gen_id = storage.create_generation(run_id, {}, 0, "test")

    resp = client.get(f"/download/{gen_id}")
    assert resp.status_code == 200
    assert resp.json()["error"] == "not found"


def test_download_complete_gen(client):
    """Download proxies the image and sets Content-Disposition."""
    import httpx
    from unittest.mock import AsyncMock, patch, MagicMock

    run_id = storage.create_sweep_run("test/model", {}, {})
    gen_id = storage.create_generation(run_id, {}, 0, "test")
    storage.update_generation_status(
        gen_id, "complete",
        output_url="https://replicate.delivery/fake/output.webp",
        generation_ms=1000,
    )

    # Mock httpx streaming response
    mock_response = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    async def fake_aiter():
        yield b"fake-image-data"

    mock_response.aiter_bytes = fake_aiter

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.stream = MagicMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = client.get(f"/download/{gen_id}")
        assert resp.status_code == 200
        assert "attachment" in resp.headers.get("content-disposition", "")
        assert f"sweep_{gen_id}.webp" in resp.headers["content-disposition"]
