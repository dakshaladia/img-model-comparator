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
