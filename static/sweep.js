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


// ── Reset form ──────────────────────────────────────────────────────

function resetForm() {
    document.querySelectorAll("[data-sweep-active]").forEach(function (wrapper) {
        var name = wrapper.getAttribute("data-input-name");
        deactivateSweep(wrapper, name);
    });
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
    container.innerHTML = vals.map(function(v) {
        return '<span class="sweep-pill">' + v + '</span>';
    }).join("");

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

    var count = sweepCount * numOutputs;
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
document.addEventListener("htmx:afterSwap", function() {
    updateCostPreview();
    var hint = document.querySelector(".prompt-expand-hint");
    var variations = document.getElementById("prompt-variations");
    if (hint && variations && variations.children.length > 0) {
        hint.style.display = "none";
    }
});
