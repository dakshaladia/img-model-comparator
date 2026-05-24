/**
 * Sweep toggle logic + cost preview + UI helpers.
 * - toggleSweep(name): activate/deactivate sweep mode (up to 2 axes)
 * - updateCostPreview(): recalculate estimated cost
 * - renderSweepPills(input): live pill preview for comma-separated values
 */

function toggleSweep(inputName) {
    var wrapper = document.querySelector('[data-input-name="' + inputName + '"]');
    if (!wrapper) return;

    var isActive = wrapper.hasAttribute("data-sweep-active");

    if (isActive) {
        deactivateSweep(wrapper, inputName);
        renumberSweepOrders();
    } else {
        var activeCount = document.querySelectorAll("[data-sweep-active]").length;
        if (activeCount >= 2) {
            // Deactivate the first-activated (order=1) sweep to make room
            var first = document.querySelector('[data-sweep-order="1"]');
            if (first) {
                deactivateSweep(first, first.getAttribute("data-input-name"));
                renumberSweepOrders();
            }
        }
        activateSweep(wrapper, inputName);
        // Assign order: next available
        var newOrder = document.querySelectorAll("[data-sweep-active]").length;
        wrapper.setAttribute("data-sweep-order", newOrder);
    }
    updateAxisLabels();
    updateModelCompareState();
    updateCostPreview();
}

function activateSweep(wrapper, inputName) {
    wrapper.setAttribute("data-sweep-active", "");

    // Seg toggle styling
    var fixedBtn = wrapper.querySelector('[data-seg-fixed="' + inputName + '"]');
    var sweepBtn = wrapper.querySelector('[data-sweep-btn="' + inputName + '"]');
    if (fixedBtn) fixedBtn.classList.remove("is-on");
    if (sweepBtn) {
        sweepBtn.classList.add("is-on", "is-accent");
    }

    // Hide fixed, show sweep
    var fixed = wrapper.querySelector(".input-fixed");
    var sweep = wrapper.querySelector(".input-sweep");
    if (fixed) {
        fixed.classList.add("hidden");
        fixed.querySelectorAll("[name]").forEach(function (el) {
            el.setAttribute("data-name-backup", el.getAttribute("name"));
            el.removeAttribute("name");
        });
    }
    if (sweep) {
        sweep.classList.remove("hidden");
        sweep.querySelectorAll("[data-sweep-name]").forEach(function (el) {
            el.setAttribute("name", el.getAttribute("data-sweep-name"));
        });
    }

    // Prompt sweep: copy base prompt text into editable textarea
    if (inputName === "prompt") {
        var baseDisplay = wrapper.querySelector(".prompt-base-display");
        var textarea = fixed ? fixed.querySelector("textarea") : null;
        if (baseDisplay && textarea) {
            baseDisplay.value = textarea.value || "";
        }
    }
}

function deactivateSweep(wrapper, inputName) {
    wrapper.removeAttribute("data-sweep-active");
    wrapper.removeAttribute("data-sweep-order");

    // Seg toggle styling
    var fixedBtn = wrapper.querySelector('[data-seg-fixed="' + inputName + '"]');
    var sweepBtn = wrapper.querySelector('[data-sweep-btn="' + inputName + '"]');
    if (fixedBtn) fixedBtn.classList.add("is-on");
    if (sweepBtn) {
        sweepBtn.classList.remove("is-on", "is-accent");
        sweepBtn.textContent = "Sweep";
    }

    // Show fixed, hide sweep
    var fixed = wrapper.querySelector(".input-fixed");
    var sweep = wrapper.querySelector(".input-sweep");
    if (fixed) {
        fixed.classList.remove("hidden");
        fixed.querySelectorAll("[data-name-backup]").forEach(function (el) {
            el.setAttribute("name", el.getAttribute("data-name-backup"));
            el.removeAttribute("data-name-backup");
        });
    }
    if (sweep) {
        sweep.classList.add("hidden");
        sweep.querySelectorAll("[data-sweep-name]").forEach(function (el) {
            el.removeAttribute("name");
        });
        sweep.querySelectorAll("input[type=checkbox]").forEach(function (el) {
            el.checked = false;
        });
        sweep.querySelectorAll("input[type=text]").forEach(function (el) {
            el.value = "";
        });
        sweep.querySelectorAll(".chip.is-on").forEach(function (el) {
            el.classList.remove("is-on");
        });
        sweep.querySelectorAll(".sweep-pills").forEach(function (el) {
            el.innerHTML = "";
        });
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

function renumberSweepOrders() {
    var actives = document.querySelectorAll("[data-sweep-active]");
    // Sort by current order to preserve relative ordering
    var sorted = Array.from(actives).sort(function (a, b) {
        return (parseInt(a.getAttribute("data-sweep-order")) || 99) -
               (parseInt(b.getAttribute("data-sweep-order")) || 99);
    });
    sorted.forEach(function (el, i) {
        el.setAttribute("data-sweep-order", i + 1);
    });
}

function updateAxisLabels() {
    // Show Col/Row labels on sweep buttons when 2 axes are active
    var actives = document.querySelectorAll("[data-sweep-active]");
    actives.forEach(function (wrapper) {
        var name = wrapper.getAttribute("data-input-name");
        var btn = wrapper.querySelector('[data-sweep-btn="' + name + '"]');
        var order = wrapper.getAttribute("data-sweep-order");
        if (btn) {
            if (actives.length === 2) {
                btn.textContent = order === "1" ? "Col" : "Row";
            } else {
                btn.textContent = "Sweep";
            }
        }
    });
}


// ── Branch from cell ─────────────────────────────────────────────────

function branchFromCell(genId) {
    fetch("/cell/" + genId + "/inputs")
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var inputs = data.inputs || {};
            var modelSlug = data.model_slug || "";

            // Deactivate all sweeps
            document.querySelectorAll("[data-sweep-active]").forEach(function (wrapper) {
                var name = wrapper.getAttribute("data-input-name");
                deactivateSweep(wrapper, name);
            });

            // Clear model comparison chips
            var primary = document.getElementById("model-select");
            if (primary) {
                document.querySelectorAll("[data-model-chip]").forEach(function (chip) {
                    chip.classList.remove("is-on");
                });
            }

            // Switch model if needed, then fill values
            if (modelSlug && primary && primary.value !== modelSlug) {
                primary.value = modelSlug;
                // Trigger HTMX to reload the form for the new model
                htmx.trigger(primary, "change");
                // Wait for the form to settle before filling values
                var handler = function(e) {
                    if (e.detail.target && e.detail.target.id === "form-target") {
                        document.removeEventListener("htmx:afterSettle", handler);
                        fillFormValues(inputs);
                    }
                };
                document.addEventListener("htmx:afterSettle", handler);
            } else {
                fillFormValues(inputs);
            }
        });
}

function fillFormValues(inputs) {
    var form = document.getElementById("sweep-form");
    if (!form) return;

    for (var key in inputs) {
        var field = form.querySelector('[name="input__' + key + '"]');
        if (!field) continue;

        var val = inputs[key];
        field.value = val;

        // Update range slider chip if present
        if (field.type === "range") {
            var chip = field.parentElement.querySelector(".num-chip");
            if (chip) chip.textContent = val;
        }
    }

    // Scroll to form
    form.scrollIntoView({ behavior: "smooth", block: "start" });

    // Brief highlight
    form.style.outline = "2px solid var(--accent)";
    form.style.outlineOffset = "4px";
    form.style.borderRadius = "4px";
    setTimeout(function() {
        form.style.outline = "";
        form.style.outlineOffset = "";
    }, 1200);

    updateCostPreview();
    syncModelChips();
}


// ── Cross-model comparison ───────────────────────────────────────────

function toggleModelCompare(slug) {
    var chip = document.querySelector('[data-model-chip="' + slug + '"]');
    if (!chip) return;

    // Don't toggle the primary model — it's always on
    var primary = document.getElementById("model-select");
    if (primary && primary.value === slug) return;

    chip.classList.toggle("is-on");
    syncCompareInputs();
    updateCostPreview();
}

function syncModelChips() {
    // Called when dropdown changes: mark primary as always-on, sync state
    var primary = document.getElementById("model-select");
    if (!primary) return;
    var primarySlug = primary.value;

    document.querySelectorAll("[data-model-chip]").forEach(function (chip) {
        var slug = chip.getAttribute("data-model-chip");
        if (slug === primarySlug) {
            chip.classList.add("is-on");
        }
        // Don't auto-deselect others — user may have toggled them
    });
    syncCompareInputs();
    updateModelCompareState();
}

function syncCompareInputs() {
    // Populate hidden inputs for comparison models (excluding primary)
    var container = document.getElementById("compare-models-inputs");
    if (!container) return;
    var primary = document.getElementById("model-select");
    var primarySlug = primary ? primary.value : "";

    container.innerHTML = "";
    document.querySelectorAll("[data-model-chip].is-on").forEach(function (chip) {
        var slug = chip.getAttribute("data-model-chip");
        if (slug !== primarySlug) {
            var input = document.createElement("input");
            input.type = "hidden";
            input.name = "compare_model";
            input.value = slug;
            container.appendChild(input);
        }
    });
}

function getSelectedModelCount() {
    return document.querySelectorAll("[data-model-chip].is-on").length;
}

function updateModelCompareState() {
    // Disable comparison chips when 2 parameter sweeps are active
    var paramSweepCount = document.querySelectorAll("[data-sweep-active]").length;
    var note = document.getElementById("model-compare-note");
    var chips = document.querySelectorAll("[data-model-chip]");
    var primary = document.getElementById("model-select");
    var primarySlug = primary ? primary.value : "";

    if (paramSweepCount >= 2) {
        // Disable all non-primary chips, deselect them
        chips.forEach(function (chip) {
            var slug = chip.getAttribute("data-model-chip");
            if (slug !== primarySlug) {
                chip.classList.remove("is-on");
                chip.style.opacity = "0.4";
                chip.style.pointerEvents = "none";
            }
        });
        if (note) note.classList.remove("hidden");
        syncCompareInputs();
    } else {
        chips.forEach(function (chip) {
            chip.style.opacity = "";
            chip.style.pointerEvents = "";
        });
        if (note) note.classList.add("hidden");
    }
}

// Sync chips when dropdown changes
document.addEventListener("change", function(e) {
    if (e.target.id === "model-select") syncModelChips();
});
// Sync after form loads via HTMX
document.addEventListener("htmx:afterSettle", function(e) {
    if (e.detail.target && e.detail.target.id === "form-target") {
        syncModelChips();
    }
});


// ── Reset form ──────────────────────────────────────────────────────

function resetForm() {
    document.querySelectorAll("[data-sweep-active]").forEach(function (wrapper) {
        var name = wrapper.getAttribute("data-input-name");
        deactivateSweep(wrapper, name);
    });
    // Clear model comparison
    var primary = document.getElementById("model-select");
    var primarySlug = primary ? primary.value : "";
    document.querySelectorAll("[data-model-chip]").forEach(function (chip) {
        var slug = chip.getAttribute("data-model-chip");
        if (slug === primarySlug) {
            chip.classList.add("is-on");
        } else {
            chip.classList.remove("is-on");
        }
    });
    syncCompareInputs();
    var form = document.getElementById("sweep-form");
    if (form) form.reset();
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
    container.innerHTML = "";
    vals.forEach(function(v) {
        var pill = document.createElement("span");
        pill.className = "sweep-pill";
        pill.textContent = v;
        container.appendChild(pill);
    });

    updateCostPreview();
}


// ── Cost preview ────────────────────────────────────────────────────

function countSweepValues(wrapper) {
    var sweep = wrapper.querySelector(".input-sweep");
    if (!sweep) return 0;
    var checked = sweep.querySelectorAll("input[type=checkbox]:checked");
    if (checked.length > 0) return checked.length;
    var textInput = sweep.querySelector("input[type=text]");
    if (textInput && textInput.value.trim()) {
        return textInput.value.split(",").filter(function(v) { return v.trim(); }).length;
    }
    var promptTextareas = sweep.querySelectorAll("textarea[name='sweep__prompt']");
    if (promptTextareas.length > 0) return promptTextareas.length;
    return 0;
}

function updateCostPreview() {
    var el = document.getElementById("cost-preview");
    if (!el) return;

    var costs = window.SWEEP_COSTS || {};
    var modelSelect = document.getElementById("model-select");
    if (!modelSelect) return;

    var slug = modelSelect.value;
    var costPerImage = costs[slug];
    if (costPerImage === undefined) { el.textContent = ""; return; }

    // Get num_outputs multiplier
    var numOutputsInput = document.querySelector("[name='input__num_outputs']") ||
                          document.querySelector("[name='input__max_images']");
    var numOutputs = numOutputsInput ? (parseInt(numOutputsInput.value) || 1) : 1;
    if (numOutputs < 1) numOutputs = 1;

    // Count sweep values across all active axes
    var actives = document.querySelectorAll("[data-sweep-active]");
    var sweepCount = 1;
    actives.forEach(function (wrapper) {
        var axisCount = countSweepValues(wrapper);
        if (axisCount > 0) sweepCount *= axisCount;
    });

    // Account for cross-model comparison
    var selectedModels = document.querySelectorAll("[data-model-chip].is-on");
    var modelCount = selectedModels.length || 1;
    var cellsPerModel = sweepCount * numOutputs;
    var count = cellsPerModel * modelCount;

    // Sum cost across selected models (each has different pricing)
    var totalCost = 0;
    if (selectedModels.length > 0) {
        selectedModels.forEach(function (chip) {
            var mSlug = chip.getAttribute("data-model-chip");
            totalCost += (costs[mSlug] || 0) * cellsPerModel;
        });
    } else {
        totalCost = costPerImage * count;
    }

    var modelLabel = modelCount > 1 ? (modelCount + " models") : modelSelect.options[modelSelect.selectedIndex].text;
    el.textContent = count + (count === 1 ? " cell" : " cells") + " \u00b7 est $" + totalCost.toFixed(3) + " \u00b7 " + modelLabel;
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
// Validate before HTMX requests
document.addEventListener("htmx:configRequest", function(e) {
    var errorHtml = '<div class="info-banner" style="border-color:var(--danger)">' +
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>' +
        '<span style="color:var(--ink-2)">MSG</span></div>';

    // Validate prompt-expand: base prompt must not be empty
    if (e.detail.path === "/prompt-expand") {
        var basePrompt = document.querySelector(".prompt-base-display");
        if (!basePrompt || !basePrompt.value.trim()) {
            e.preventDefault();
            var variations = document.getElementById("prompt-variations");
            if (variations) {
                variations.innerHTML = errorHtml.replace("MSG", "Enter a base prompt before expanding.");
            }
            return;
        }
    }

    // Validate sweep: prompt must be present
    if (e.detail.path === "/sweep") {
        var promptFixed = document.querySelector("[name='input__prompt']");
        var promptSweepActive = document.querySelector("[data-input-name='prompt'][data-sweep-active]");

        if (promptFixed && promptFixed.value.trim()) return;
        if (promptSweepActive) {
            var sweepVariations = document.querySelectorAll("textarea[name='sweep__prompt']");
            if (sweepVariations.length > 0) return;
        }

        e.preventDefault();
        var target = document.getElementById("results-target");
        if (target) {
            var msg = promptSweepActive
                ? "Enter a base prompt and click Expand before running."
                : "Prompt is required. Enter a prompt before running.";
            target.innerHTML = errorHtml.replace("MSG", msg);
        }
    }
});

document.addEventListener("htmx:afterSwap", function() {
    updateCostPreview();
    var hint = document.querySelector(".prompt-expand-hint");
    var variations = document.getElementById("prompt-variations");
    if (hint && variations && variations.children.length > 0) {
        hint.style.display = "none";
    }
});
