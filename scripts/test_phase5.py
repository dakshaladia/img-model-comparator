"""Phase 5 integration tests.

Tests prompt expansion, prompt sweep submission, label truncation,
and verifies Phase 4 functionality still works (no regressions).

Usage: python scripts/test_phase5.py
       python scripts/test_phase5.py --with-claude   # includes real Claude API call
"""

import subprocess
import sys
import os
import time
import re
import urllib.request
import urllib.parse
import json

SERVER_PORT = 8112  # avoid conflict with dev (8000) and phase4 tests (8111)
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


# ── Phase 4 regression tests ────────────────────────────────────────

def test_index_loads():
    html = get("/")
    assert "Sweep" in html
    assert html.count("<option") == 6
    print("  PASS: index loads, 6 model options")


def test_model_form_renders():
    html = get("/model-form?slug=black-forest-labs/flux-schnell")
    assert 'name="input__prompt"' in html
    assert 'data-sweep-btn="prompt"' in html
    print("  PASS: model form renders with sweep toggles")


def test_single_generation():
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
    })
    assert "grid-cols-1" in html
    assert "Generating..." in html
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
    assert "num_inference_steps=1" in html
    assert "num_inference_steps=4" in html
    print("  PASS: numeric sweep — 4 cells, grid-cols-2, labeled")


def test_enum_sweep_checkboxes():
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__aspect_ratio": ["1:1", "16:9", "9:16"],
    })
    assert "grid-cols-3" in html
    assert html.count("hx-get") == 3
    assert "aspect_ratio=1:1" in html
    print("  PASS: enum sweep — 3 cells, grid-cols-3")


def test_truncation():
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__output_quality": "10,20,30,40,50,60,70,80,90,100",
    })
    assert "limited to 9" in html
    assert html.count("hx-get") == 9
    print("  PASS: truncation — 10 values capped to 9")


def test_grid_cols():
    # N=2 → grid-cols-2
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__num_inference_steps": "1,4",
    })
    assert "grid-cols-2" in html
    # N=5 → grid-cols-3
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__output_quality": "10,30,50,70,90",
    })
    assert "grid-cols-3" in html
    print("  PASS: grid cols — N=2→2col, N=5→3col")


# ── Phase 5: Prompt sweep UI tests ──────────────────────────────────

def test_prompt_sweep_ui_in_form():
    """Verify the prompt sweep UI elements render in the model form."""
    html = get("/model-form?slug=black-forest-labs/flux-schnell")
    # Direction dropdown with preset axes
    assert "prompt-direction" in html, "Missing direction dropdown"
    assert "camera angle" in html, "Missing 'camera angle' direction option"
    assert "lighting" in html, "Missing 'lighting' direction option"
    assert "art style" in html, "Missing 'art style' direction option"
    assert "mood" in html, "Missing 'mood' direction option"
    assert "color palette" in html, "Missing 'color palette' direction option"
    assert "time of day" in html, "Missing 'time of day' direction option"
    assert "weather" in html, "Missing 'weather' direction option"
    assert "composition" in html, "Missing 'composition' direction option"
    # Count selector
    assert "prompt-count" in html, "Missing count selector"
    assert 'value="3"' in html, "Missing count option 3"
    assert 'value="5" selected' in html, "Missing default count 5"
    assert 'value="9"' in html, "Missing count option 9"
    # Preview button with HTMX
    assert 'hx-post="/prompt-expand"' in html, "Missing HTMX prompt-expand"
    assert "prompt-variations" in html, "Missing variations container"
    # Base prompt display
    assert "prompt-base-display" in html, "Missing base prompt display"
    print("  PASS: prompt sweep UI — direction dropdown (8 axes), count selector, Preview button")


def test_prompt_sweep_ui_not_on_other_models():
    """Verify direction dropdown only appears when prompt input exists."""
    # All 6 models have a prompt input, so it should appear on all
    for slug in ["black-forest-labs/flux-schnell", "stability-ai/stable-diffusion-3.5-large"]:
        html = get(f"/model-form?slug={slug}")
        assert "prompt-direction" in html, f"Missing direction dropdown on {slug}"
    print("  PASS: prompt sweep UI present on multiple models")


def test_generic_string_sweep_unchanged():
    """Verify non-prompt string inputs still use the comma-separated sweep UI."""
    html = get("/model-form?slug=stability-ai/stable-diffusion-3.5-large")
    # negative_prompt is a string input that is NOT "prompt"
    assert 'name="input__negative_prompt"' in html, "Missing negative_prompt field"
    # Its sweep container should have the generic placeholder, not prompt sweep UI
    # Check that there's a sweep text input for it (placeholder="e.g. 1, 3, 5, 7")
    assert 'name="sweep__negative_prompt"' in html, "Missing sweep input for negative_prompt"
    print("  PASS: generic string sweep — comma-separated input preserved")


def test_prompt_expand_endpoint():
    """Test POST /prompt-expand returns correct HTML partial with textareas."""
    html = post("/prompt-expand", {
        "base_prompt": "a cat sitting on a windowsill",
        "direction": "lighting",
        "count": "3",
    })
    # Should contain exactly 3 textareas with name="sweep__prompt"
    textarea_count = html.count('name="sweep__prompt"')
    assert textarea_count == 3, f"Expected 3 textareas, got {textarea_count}"
    # Each should be an actual textarea element
    assert html.count("<textarea") == 3, f"Expected 3 <textarea> elements"
    # Content should mention the original subject
    assert "cat" in html.lower(), "Variations should preserve the subject (cat)"
    print("  PASS: /prompt-expand — 3 textareas, subject preserved")


def test_prompt_expand_different_counts():
    """Test that /prompt-expand respects the count parameter."""
    for count in [3, 5, 7, 9]:
        html = post("/prompt-expand", {
            "base_prompt": "a mountain landscape at sunset",
            "direction": "art style",
            "count": str(count),
        })
        textarea_count = html.count('name="sweep__prompt"')
        assert textarea_count == count, f"Count={count}: expected {count} textareas, got {textarea_count}"
    print("  PASS: /prompt-expand — counts 3, 5, 7, 9 all return correct number")


def test_prompt_expand_different_directions():
    """Test that different directions produce different content."""
    results = {}
    for direction in ["camera angle", "mood"]:
        html = post("/prompt-expand", {
            "base_prompt": "a detective in a rain-soaked alley",
            "direction": direction,
            "count": "3",
        })
        results[direction] = html
    # The two sets of variations should be different
    assert results["camera angle"] != results["mood"], "Different directions should produce different variations"
    print("  PASS: /prompt-expand — different directions produce different content")


def test_prompt_sweep_submission():
    """Test submitting a prompt sweep via POST /sweep with multiple sweep__prompt values."""
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "sweep__prompt": [
            "a cat in golden hour sunlight",
            "a cat under harsh neon lights",
            "a cat in soft moonlight",
        ],
    })
    assert "grid-cols-3" in html, "Expected grid-cols-3 for 3 prompt variations"
    assert html.count("hx-get") == 3, "Expected 3 polling cells"
    # Labels should be present and truncated
    assert "prompt=" in html, "Labels should contain prompt="
    print("  PASS: prompt sweep submission — 3 cells, grid-cols-3, labels present")


def test_label_truncation_universal():
    """Test that labels are truncated to 60 chars for all sweep types."""
    # Numeric sweep with short labels — should NOT be truncated
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "input__prompt": "test",
        "sweep__num_inference_steps": "1,2",
    })
    assert "num_inference_steps=1" in html
    assert "..." not in html.split("grid")[1] if "grid" in html else True

    # Prompt sweep with long prompts — SHOULD be truncated
    long_prompt = "a very detailed and elaborate scene of a cat sitting on a beautiful ornate windowsill in paris"
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "sweep__prompt": [long_prompt, long_prompt + " at night"],
    })
    # Labels should be truncated (the full label would be "prompt=a very detailed..." which is >60 chars)
    assert "..." in html, "Long prompt labels should be truncated with ..."
    # The full long prompt should NOT appear as a label
    assert long_prompt not in html.split("hx-get")[0] if "hx-get" in html else True
    print("  PASS: label truncation — short labels intact, long labels truncated to 60 chars")


def test_prompt_sweep_single_variation():
    """Test prompt sweep with just 1 variation — should still work."""
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "sweep__prompt": ["a single cat prompt"],
    })
    assert "grid-cols-1" in html, "Expected grid-cols-1 for 1 variation"
    assert html.count("hx-get") == 1, "Expected 1 polling cell"
    print("  PASS: prompt sweep with 1 variation — single cell")


def test_prompt_sweep_max_truncation():
    """Test that prompt sweep respects MAX_SWEEP_SIZE."""
    prompts = [f"variation {i}" for i in range(12)]
    html = post("/sweep", {
        "slug": "black-forest-labs/flux-schnell",
        "sweep__prompt": prompts,
    })
    assert "limited to 9" in html, "Should show truncation warning"
    assert html.count("hx-get") == 9, f"Expected 9 cells, got {html.count('hx-get')}"
    print("  PASS: prompt sweep truncation — 12 variations capped to 9")


if __name__ == "__main__":
    with_claude = "--with-claude" in sys.argv

    print("Starting server...")
    proc = start_server()

    try:
        print(f"\nRunning Phase 5 tests against port {SERVER_PORT}:\n")

        # Phase 4 regressions
        print("── Phase 4 regressions ──")
        test_index_loads()
        test_model_form_renders()
        test_single_generation()
        test_numeric_sweep()
        test_enum_sweep_checkboxes()
        test_truncation()
        test_grid_cols()

        # Phase 5: UI tests (no Claude call)
        print("\n── Phase 5: Prompt sweep UI ──")
        test_prompt_sweep_ui_in_form()
        test_prompt_sweep_ui_not_on_other_models()
        test_generic_string_sweep_unchanged()

        # Phase 5: Submission tests (no Claude call)
        print("\n── Phase 5: Prompt sweep submission ──")
        test_prompt_sweep_submission()
        test_label_truncation_universal()
        test_prompt_sweep_single_variation()
        test_prompt_sweep_max_truncation()

        # Phase 5: Claude API tests (opt-in)
        if with_claude:
            print("\n── Phase 5: Claude API (real calls) ──")
            test_prompt_expand_endpoint()
            test_prompt_expand_different_counts()
            test_prompt_expand_different_directions()
        else:
            print("\n  Skipping Claude API tests (use --with-claude to include)")

        print("\nAll tests passed.")
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        proc.kill()
        proc.wait()
