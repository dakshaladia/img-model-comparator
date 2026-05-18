"""Phase 4 integration tests.

Starts the server, runs tests against it, then shuts it down.
Tests verify form parsing, grid rendering, polling, and sweep logic.
Does NOT call Replicate (only tests 1-6 check response shape;
test 7 fires a real generation and polls until complete).

Usage: python scripts/test_phase4.py
       python scripts/test_phase4.py --with-generation   # includes real Replicate call
"""

import subprocess
import sys
import os
import time
import urllib.request
import urllib.parse

SERVER_PORT = 8111  # avoid conflict with dev server on 8000
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
    # Wait for server to be ready
    for _ in range(20):
        time.sleep(0.5)
        try:
            get("/")
            return proc
        except Exception:
            pass
    proc.kill()
    raise RuntimeError("Server failed to start")

def test_index_loads():
    html = get("/")
    assert "Sweep" in html, "Missing title"
    assert "flux-schnell" in html, "Missing model slug"
    assert html.count("<option") == 6, f"Expected 6 options, got {html.count('<option')}"
    print("  PASS: index loads, 6 model options")

def test_model_form_renders():
    html = get("/model-form?slug=black-forest-labs/flux-schnell")
    assert 'name="input__prompt"' in html, "Missing prompt field"
    assert 'name="input__aspect_ratio"' in html, "Missing aspect_ratio field"
    assert 'data-sweep-btn="prompt"' in html, "Missing sweep toggle for prompt"
    assert 'data-sweep-btn="image"' not in html, "image should not be sweepable"
    print("  PASS: model form renders with correct fields and sweep toggles")

def test_single_generation():
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
    })
    assert "grid-cols-1" in html, f"Expected grid-cols-1, got: {html[:100]}"
    assert "hx-get" in html, "Missing polling hx-get"
    assert "Generating..." in html, "Missing generating text"
    # No label for single gen
    assert "font-medium text-gray-400" not in html, "Single gen should have no label"
    print("  PASS: single generation — 1 cell, grid-cols-1, no label")

def test_numeric_sweep():
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__num_inference_steps": "1,2,3,4",
    })
    assert "grid-cols-2" in html, "Expected grid-cols-2 for N=4"
    assert "num_inference_steps=1" in html, "Missing label for value 1"
    assert "num_inference_steps=4" in html, "Missing label for value 4"
    assert html.count("hx-get") == 4, f"Expected 4 polling cells"
    print("  PASS: numeric sweep — 4 cells, grid-cols-2, labeled")

def test_enum_sweep_checkboxes():
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__aspect_ratio": ["1:1", "16:9", "9:16"],
    })
    assert "grid-cols-3" in html, "Expected grid-cols-3 for N=3"
    assert "aspect_ratio=1:1" in html, "Missing label 1:1"
    assert "aspect_ratio=16:9" in html, "Missing label 16:9"
    assert "aspect_ratio=9:16" in html, "Missing label 9:16"
    print("  PASS: enum sweep (checkboxes) — 3 cells, grid-cols-3, labeled")

def test_truncation():
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__output_quality": "10,20,30,40,50,60,70,80,90,100",
    })
    assert "limited to 9" in html, "Missing truncation warning"
    assert "grid-cols-3" in html, "Expected grid-cols-3 for N=9"
    assert html.count("hx-get") == 9, f"Expected 9 cells, got {html.count('hx-get')}"
    print("  PASS: truncation — 10 values capped to 9, warning shown")

def test_grid_cols_n2():
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__num_inference_steps": "1,4",
    })
    assert "grid-cols-2" in html, "Expected grid-cols-2 for N=2"
    assert html.count("hx-get") == 2, "Expected 2 cells"
    print("  PASS: grid cols N=2 — grid-cols-2")

def test_grid_cols_n5():
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__output_quality": "10,30,50,70,90",
    })
    assert "grid-cols-3" in html, "Expected grid-cols-3 for N=5"
    assert html.count("hx-get") == 5, "Expected 5 cells"
    print("  PASS: grid cols N=5 — grid-cols-3")

def test_real_generation_and_poll():
    """Fires a real flux-schnell generation and polls until complete."""
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "a red cube on white background",
    })
    # Extract cell id from hx-get="/cell/N"
    import re
    match = re.search(r'hx-get="/cell/(\d+)"', html)
    assert match, "Could not find cell id in response"
    cell_id = match.group(1)

    # Poll until complete or timeout
    for _ in range(30):
        time.sleep(2)
        cell_html = get(f"/cell/{cell_id}")
        if "hx-get" not in cell_html:
            # Final state — polling stopped
            assert "replicate.delivery" in cell_html or "Generation failed" in cell_html
            if "replicate.delivery" in cell_html:
                assert "ms</p>" in cell_html, "Missing generation time"
                print(f"  PASS: real generation — image delivered, polling stopped")
            else:
                print(f"  PASS: real generation — completed (failed state but polling stopped)")
            return
    raise AssertionError("Generation did not complete within 60s")


if __name__ == "__main__":
    with_generation = "--with-generation" in sys.argv

    print("Starting server...")
    proc = start_server()

    try:
        print(f"\nRunning Phase 4 tests against port {SERVER_PORT}:\n")

        test_index_loads()
        test_model_form_renders()
        test_single_generation()
        test_numeric_sweep()
        test_enum_sweep_checkboxes()
        test_truncation()
        test_grid_cols_n2()
        test_grid_cols_n5()

        if with_generation:
            print("\n  Running real generation test (~$0.003)...")
            test_real_generation_and_poll()
        else:
            print("\n  Skipping real generation test (use --with-generation to include)")

        print("\nAll tests passed.")
    except Exception as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
    finally:
        proc.kill()
        proc.wait()
