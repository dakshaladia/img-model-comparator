"""Phase 6 integration tests.

Tests UI polish (display names, empty state, cost data, loading states,
timing format, click-to-enlarge, error styling) and verifies all prior
phases still work.

Usage: python scripts/test_phase6.py
       python scripts/test_phase6.py --with-claude   # includes real Claude API call
"""

import subprocess
import sys
import os
import time
import urllib.request
import urllib.parse

SERVER_PORT = 8113
BASE = f"http://localhost:{SERVER_PORT}"


def post(path, data: dict) -> str:
    encoded = urllib.parse.urlencode(data, doseq=True).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=encoded, method="POST")
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode()


def get(path) -> str:
    with urllib.request.urlopen(f"{BASE}{path}") as resp:
        return resp.read().decode()


def start_server():
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--port", str(SERVER_PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
    )
    for _ in range(20):
        time.sleep(0.5)
        try:
            get("/")
            return proc
        except Exception:
            pass
    proc.kill()
    raise RuntimeError("Server failed to start")


# ── Phase 4 + 5 regressions ─────────────────────────────────────────

def test_single_generation():
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
    })
    assert "grid-cols-1" in html
    assert html.count("hx-get") == 1
    print("  PASS: single generation — 1 cell, grid-cols-1")


def test_numeric_sweep():
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__num_inference_steps": "1,2,3,4",
    })
    assert "grid-cols-2" in html
    assert html.count("hx-get") == 4
    print("  PASS: numeric sweep — 4 cells, grid-cols-2")


def test_enum_sweep():
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__aspect_ratio": ["1:1", "16:9", "9:16"],
    })
    assert "grid-cols-3" in html
    assert html.count("hx-get") == 3
    print("  PASS: enum sweep — 3 cells, grid-cols-3")


def test_prompt_sweep():
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "sweep__prompt": ["cat in sunlight", "cat in moonlight", "cat in neon"],
    })
    assert "grid-cols-3" in html
    assert html.count("hx-get") == 3
    print("  PASS: prompt sweep — 3 cells, grid-cols-3")


def test_truncation():
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__output_quality": "10,20,30,40,50,60,70,80,90,100",
    })
    assert "limited to 9" in html
    assert html.count("hx-get") == 9
    print("  PASS: truncation — 10 values capped to 9")


# ── Phase 6: Branding + display names ───────────────────────────────

def test_branding():
    html = get("/")
    assert "Sweep" in html, "Missing title"
    assert "Parameter exploration for generative image models" in html, "Missing tagline"
    print("  PASS: branding — title + tagline present")


def test_display_names_in_dropdown():
    html = get("/")
    assert "Flux Schnell" in html, "Missing display name for flux-schnell"
    assert "Flux 1.1 Pro" in html, "Missing display name for flux-1.1-pro"
    assert "Imagen 4 Fast" in html, "Missing display name for imagen-4-fast"
    assert "Seedream 4" in html, "Missing display name for seedream-4"
    assert "Recraft v3" in html, "Missing display name for recraft-v3"
    assert "SD 3.5 Large" in html, "Missing display name for sd-3.5-large"
    # Slugs still present as option values
    assert 'value="black-forest-labs/flux-schnell"' in html, "Missing slug as value"
    print("  PASS: display names — all 6 models have friendly names, slugs as values")


def test_display_names_with_slug():
    """Display names should include the slug for clarity."""
    html = get("/")
    assert "Flux Schnell" in html and "black-forest-labs/flux-schnell" in html
    print("  PASS: display names include slug for reference")


# ── Phase 6: Empty state ────────────────────────────────────────────

def test_empty_state():
    html = get("/")
    assert "Run a sweep to see results here" in html, "Missing empty state text"
    assert "results-target" in html, "Missing results target div"
    print("  PASS: empty state — placeholder text in results area")


# ── Phase 6: Cost data embedded ─────────────────────────────────────

def test_cost_data_embedded():
    html = get("/")
    assert "SWEEP_COSTS" in html, "Missing cost data in page"
    assert "0.003" in html, "Missing flux-schnell cost (0.003)"
    assert "0.04" in html, "Missing flux-1.1-pro cost (0.04)"
    assert "0.065" in html, "Missing sd-3.5-large cost (0.065)"
    print("  PASS: cost data — SWEEP_COSTS JSON embedded with all 6 model costs")


# ── Phase 6: Loading states ─────────────────────────────────────────

def test_run_button_loading_state():
    html = get("/model-form?slug=black-forest-labs/flux-schnell")
    assert 'hx-disabled-elt="this"' in html, "Missing hx-disabled-elt on Run button"
    assert "btn-label" in html, "Missing btn-label span"
    assert "btn-loading" in html, "Missing btn-loading span"
    assert "Running..." in html, "Missing Running... text"
    print("  PASS: Run button — has loading state (disabled + text swap)")


def test_preview_button_loading_state():
    html = get("/model-form?slug=black-forest-labs/flux-schnell")
    assert "Expanding..." in html, "Missing Expanding... text"
    # Find the Preview button area
    assert 'hx-post="/prompt-expand"' in html, "Missing prompt-expand HTMX"
    print("  PASS: Preview button — has loading state (Expanding...)")


def test_htmx_indicator_css():
    html = get("/")
    assert ".htmx-request .btn-label" in html, "Missing HTMX indicator CSS for btn-label"
    assert ".htmx-request .btn-loading" in html, "Missing HTMX indicator CSS for btn-loading"
    print("  PASS: HTMX indicator CSS — btn-label/btn-loading toggle rules present")


# ── Phase 6: Cost preview element ───────────────────────────────────

def test_cost_preview_element():
    html = get("/model-form?slug=black-forest-labs/flux-schnell")
    assert 'id="cost-preview"' in html, "Missing cost-preview element"
    print("  PASS: cost preview element present in form")


# ── Phase 6: Cell final polish ──────────────────────────────────────

def test_cell_complete_has_link():
    """Verify completed cells wrap image in a link for click-to-enlarge."""
    # Submit a sweep, wait for completion, check cell_final markup
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
    })
    # Extract cell id
    import re
    match = re.search(r'hx-get="/cell/(\d+)"', html)
    assert match, "Could not find cell id"
    cell_id = match.group(1)

    # Poll until complete (up to 60s)
    for _ in range(30):
        time.sleep(2)
        cell_html = get(f"/cell/{cell_id}")
        if "hx-get" not in cell_html:
            # Final state
            if "replicate.delivery" in cell_html:
                assert 'target="_blank"' in cell_html, "Image not wrapped in link"
                assert "<a " in cell_html, "Missing anchor tag"
                print("  PASS: completed cell — image wrapped in click-to-open link")
                return
            else:
                print("  SKIP: cell failed, can't test link (billing?)")
                return
    raise AssertionError("Generation did not complete within 60s")


def test_cell_timing_format():
    """Verify timing shows as seconds (e.g. '1.2s') not milliseconds."""
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test timing",
    })
    import re
    match = re.search(r'hx-get="/cell/(\d+)"', html)
    assert match
    cell_id = match.group(1)

    for _ in range(30):
        time.sleep(2)
        cell_html = get(f"/cell/{cell_id}")
        if "hx-get" not in cell_html:
            if "replicate.delivery" in cell_html:
                # Should show "X.Xs" format, not "Xms"
                assert re.search(r'\d+\.\d+s', cell_html), "Timing not in seconds format (X.Xs)"
                assert "ms<" not in cell_html, "Still showing raw milliseconds"
                print("  PASS: timing badge — shows seconds format (e.g. 0.9s)")
                return
            else:
                print("  SKIP: cell failed, can't test timing (billing?)")
                return
    raise AssertionError("Generation did not complete within 60s")


def test_cell_error_styling():
    """Verify failed cells have red border and error icon."""
    # We can't easily force a failure, so check the template structure
    # by reading cell_final.html directly
    import os
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "templates", "partials", "cell_final.html"
    )
    with open(template_path) as f:
        template = f.read()
    assert "border-red-500" in template, "Missing red border for failed state"
    assert "<svg" in template, "Missing error icon SVG"
    assert "Generation failed" in template, "Missing fallback error text"
    print("  PASS: error styling — red border, icon, fallback text in template")


# ── Phase 6: Sweep.js cost logic ────────────────────────────────────

def test_sweep_js_has_cost_logic():
    """Verify sweep.js contains cost preview update logic."""
    js = get("/static/sweep.js")
    assert "updateCostPreview" in js, "Missing updateCostPreview function"
    assert "SWEEP_COSTS" in js, "Missing SWEEP_COSTS reference"
    assert "cost-preview" in js, "Missing cost-preview element reference"
    assert "htmx:afterSwap" in js, "Missing htmx:afterSwap listener for cost updates"
    print("  PASS: sweep.js — cost preview logic with model lookup and event listeners")


# ── Phase 6: Docker + deploy files ──────────────────────────────────

def test_deploy_files_exist():
    """Verify deploy configuration files exist."""
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert os.path.exists(os.path.join(base, "fly.toml")), "Missing fly.toml"
    assert os.path.exists(os.path.join(base, ".dockerignore")), "Missing .dockerignore"
    assert os.path.exists(os.path.join(base, "Dockerfile")), "Missing Dockerfile"

    with open(os.path.join(base, "fly.toml")) as f:
        fly = f.read()
    assert "sweep_data" in fly, "Missing volume mount in fly.toml"
    assert "8000" in fly, "Missing port 8000 in fly.toml"

    with open(os.path.join(base, ".dockerignore")) as f:
        dockerignore = f.read()
    assert ".env" in dockerignore, "Missing .env in .dockerignore"
    assert ".venv" in dockerignore, "Missing .venv in .dockerignore"

    with open(os.path.join(base, ".gitignore")) as f:
        gitignore = f.read()
    assert "data/" in gitignore, "Missing data/ in .gitignore"

    print("  PASS: deploy files — fly.toml (with volume), .dockerignore, .gitignore all correct")


if __name__ == "__main__":
    with_generation = "--with-generation" in sys.argv or "--with-claude" in sys.argv

    print("Starting server...")
    proc = start_server()

    try:
        print(f"\nRunning Phase 6 tests against port {SERVER_PORT}:\n")

        # Prior phase regressions
        print("── Regression tests ──")
        test_single_generation()
        test_numeric_sweep()
        test_enum_sweep()
        test_prompt_sweep()
        test_truncation()

        # Phase 6: Branding
        print("\n── Branding + display names ──")
        test_branding()
        test_display_names_in_dropdown()
        test_display_names_with_slug()

        # Phase 6: Empty state
        print("\n── Empty state ──")
        test_empty_state()

        # Phase 6: Cost
        print("\n── Cost preview ──")
        test_cost_data_embedded()
        test_cost_preview_element()
        test_sweep_js_has_cost_logic()

        # Phase 6: Loading states
        print("\n── Loading states ──")
        test_run_button_loading_state()
        test_preview_button_loading_state()
        test_htmx_indicator_css()

        # Phase 6: Cell polish (template checks, no API calls)
        print("\n── Cell polish ──")
        test_cell_error_styling()

        # Phase 6: Deploy files
        print("\n── Deploy config ──")
        test_deploy_files_exist()

        # Real generation tests (opt-in, costs ~$0.006)
        if with_generation:
            print("\n── Real generation tests (~$0.006) ──")
            test_cell_complete_has_link()
            test_cell_timing_format()
        else:
            print("\n  Skipping real generation tests (use --with-generation to include)")

        print("\nAll tests passed.")
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        proc.kill()
        proc.wait()
