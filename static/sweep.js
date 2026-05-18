/**
 * Sweep toggle logic + cost preview + UI helpers.
 * - toggleSweep(name): activate/deactivate sweep mode for one input
 * - One-axis constraint: only one input can be in sweep mode at a time
 * - updateCostPreview(): recalculate estimated cost from model + sweep count
 * - renderSweepPills(input): live pill preview for comma-separated values
 */

function toggleSweep(inputName) {
    const wrapper = document.querySelector(`[data-input-name="${inputName}"]`);
    if (!wrapper) return;

    const isActive = wrapper.hasAttribute("data-sweep-active");

    if (isActive) {
        deactivateSweep(wrapper, inputName);
    } else {
        // Enforce one-axis: deactivate any other active sweep first
        document.querySelectorAll("[data-sweep-active]").forEach(function (other) {
            const otherName = other.getAttribute("data-input-name");
            deactivateSweep(other, otherName);
        });
        activateSweep(wrapper, inputName);
    }
}

function activateSweep(wrapper, inputName) {
    wrapper.setAttribute("data-sweep-active", "");

    // Seg toggle styling
    var fixedBtn = wrapper.querySelector(`[data-seg-fixed="${inputName}"]`);
    var sweepBtn = wrapper.querySelector(`[data-sweep-btn="${inputName}"]`);
    if (fixedBtn) fixedBtn.classList.remove("is-on");
    if (sweepBtn) {
        sweepBtn.classList.add("is-on", "is-accent");
    }

    // Hide fixed, show sweep
    const fixed = wrapper.querySelector(".input-fixed");
    const sweep = wrapper.querySelector(".input-sweep");
    if (fixed) {
        fixed.classList.add("hidden");
        // Remove name attrs so fixed fields aren't submitted
        fixed.querySelectorAll("[name]").forEach(function (el) {
            el.setAttribute("data-name-backup", el.getAttribute("name"));
            el.removeAttribute("name");
        });
    }
    if (sweep) {
        sweep.classList.remove("hidden");
        // Activate sweep field names (data-sweep-name -> name)
        sweep.querySelectorAll("[data-sweep-name]").forEach(function (el) {
            el.setAttribute("name", el.getAttribute("data-sweep-name"));
        });
    }

    // Prompt sweep: copy base prompt text into display span
    if (inputName === "prompt") {
        var baseDisplay = wrapper.querySelector(".prompt-base-display");
        var textarea = fixed ? fixed.querySelector("textarea") : null;
        if (baseDisplay && textarea) {
            baseDisplay.textContent = textarea.value || "(empty)";
        }
    }
}

function deactivateSweep(wrapper, inputName) {
    wrapper.removeAttribute("data-sweep-active");

    // Seg toggle styling
    var fixedBtn = wrapper.querySelector(`[data-seg-fixed="${inputName}"]`);
    var sweepBtn = wrapper.querySelector(`[data-sweep-btn="${inputName}"]`);
    if (fixedBtn) fixedBtn.classList.add("is-on");
    if (sweepBtn) {
        sweepBtn.classList.remove("is-on", "is-accent");
    }

    // Show fixed, hide sweep
    const fixed = wrapper.querySelector(".input-fixed");
    const sweep = wrapper.querySelector(".input-sweep");
    if (fixed) {
        fixed.classList.remove("hidden");
        // Restore name attrs
        fixed.querySelectorAll("[data-name-backup]").forEach(function (el) {
            el.setAttribute("name", el.getAttribute("data-name-backup"));
            el.removeAttribute("data-name-backup");
        });
    }
    if (sweep) {
        sweep.classList.add("hidden");
        // Deactivate sweep field names (remove name, keep data-sweep-name)
        sweep.querySelectorAll("[data-sweep-name]").forEach(function (el) {
            el.removeAttribute("name");
        });
        // Clear sweep inputs
        sweep.querySelectorAll("input[type=checkbox]").forEach(function (el) {
            el.checked = false;
        });
        sweep.querySelectorAll("input[type=text]").forEach(function (el) {
            el.value = "";
        });
        // Clear chip states
        sweep.querySelectorAll(".chip.is-on").forEach(function (el) {
            el.classList.remove("is-on");
        });
        // Clear sweep pills
        sweep.querySelectorAll(".sweep-pills").forEach(function (el) {
            el.innerHTML = "";
        });
        // Clear prompt variations and restore hint
        var variations = sweep.querySelector(".prompt-variations");
        if (variations) {
            variations.innerHTML = "";
        }
        var hint = sweep.querySelector(".prompt-expand-hint");
        if (hint) {
            hint.style.display = "";
        }
    }
    updateCostPreview();
}


// ── Reset form ──────────────────────────────────────────────────────

function resetForm() {
    // Deactivate all sweeps
    document.querySelectorAll("[data-sweep-active]").forEach(function (wrapper) {
        var name = wrapper.getAttribute("data-input-name");
        deactivateSweep(wrapper, name);
    });
    // Reset native form fields to defaults
    var form = document.getElementById("sweep-form");
    if (form) form.reset();
    // Update range slider chips to match reset values
    form.querySelectorAll("input[type=range]").forEach(function (el) {
        var chip = el.parentElement.querySelector(".num-chip");
        if (chip) chip.textContent = el.value;
    });
    updateCostPreview();
}


// ── Sweep value pills (live preview) ────────────────────────────────

function renderSweepPills(input) {
    var wrapper = input.closest("[data-input-name]");
    if (!wrapper) return;
    var name = wrapper.getAttribute("data-input-name");
    var container = wrapper.querySelector("[data-pills-for='" + name + "']");
    if (!container) return;

    var vals = input.value.split(",").map(function(v) { return v.trim(); }).filter(Boolean);
    container.innerHTML = vals.map(function(v) {
        return '<span class="sweep-pill">' + v + '</span>';
    }).join("");

    updateCostPreview();
}


// ── Cost preview ────────────────────────────────────────────────────

function updateCostPreview() {
    var el = document.getElementById("cost-preview");
    if (!el) return;

    var costs = window.SWEEP_COSTS || {};
    var modelSelect = document.getElementById("model-select");
    if (!modelSelect) return;

    var slug = modelSelect.value;
    var costPerImage = costs[slug];
    if (costPerImage === undefined) { el.textContent = ""; return; }

    // Count how many images will be generated
    var count = 1;
    var activeWrapper = document.querySelector("[data-sweep-active]");
    if (activeWrapper) {
        var sweep = activeWrapper.querySelector(".input-sweep");
        if (sweep) {
            // Checkboxes (enum/boolean sweep)
            var checked = sweep.querySelectorAll("input[type=checkbox]:checked");
            if (checked.length > 0) {
                count = checked.length;
            } else {
                // Comma-separated text input
                var textInput = sweep.querySelector("input[type=text]");
                if (textInput && textInput.value.trim()) {
                    count = textInput.value.split(",").filter(function(v) { return v.trim(); }).length;
                }
                // Prompt variations (textareas from Claude)
                var promptTextareas = sweep.querySelectorAll("textarea[name='sweep__prompt']");
                if (promptTextareas.length > 0) {
                    count = promptTextareas.length;
                }
            }
        }
    }

    var total = (costPerImage * count).toFixed(3);
    var modelName = modelSelect.options[modelSelect.selectedIndex].text;
    el.textContent = count + (count === 1 ? " cell" : " cells") + " \u00b7 est $" + total + " \u00b7 " + modelName;
}

// Attach cost preview updates via event delegation
document.addEventListener("change", function(e) {
    if (e.target.id === "model-select" || e.target.closest("#sweep-form")) {
        updateCostPreview();
    }
});
document.addEventListener("input", function(e) {
    if (e.target.closest("#sweep-form")) {
        updateCostPreview();
    }
});
// Update after HTMX swaps (e.g. prompt variations loaded)
document.addEventListener("htmx:afterSwap", function() {
    updateCostPreview();
    // Hide the expand hint once variations are loaded
    var hint = document.querySelector(".prompt-expand-hint");
    var variations = document.getElementById("prompt-variations");
    if (hint && variations && variations.children.length > 0) {
        hint.style.display = "none";
    }
});
