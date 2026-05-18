/**
 * Sweep toggle logic.
 * - toggleSweep(name): activate/deactivate sweep mode for one input
 * - One-axis constraint: only one input can be in sweep mode at a time
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

    // Toggle button styling
    const btn = wrapper.querySelector(`[data-sweep-btn="${inputName}"]`);
    if (btn) {
        btn.classList.add("border-blue-500", "text-blue-400", "bg-blue-500/10");
        btn.classList.remove("border-gray-600", "text-gray-400");
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
    }
}

function deactivateSweep(wrapper, inputName) {
    wrapper.removeAttribute("data-sweep-active");

    // Toggle button styling
    const btn = wrapper.querySelector(`[data-sweep-btn="${inputName}"]`);
    if (btn) {
        btn.classList.remove("border-blue-500", "text-blue-400", "bg-blue-500/10");
        btn.classList.add("border-gray-600", "text-gray-400");
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
        // Clear sweep inputs
        sweep.querySelectorAll("input[type=checkbox]").forEach(function (el) {
            el.checked = false;
        });
        sweep.querySelectorAll("input[type=text]").forEach(function (el) {
            el.value = "";
        });
    }
}
