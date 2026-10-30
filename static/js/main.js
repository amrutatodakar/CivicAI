/* CivicAI citizen-side interactions. Plain ES2017, no dependencies. */
(function () {
  "use strict";

  var SAVED_KEY = "civicai.savedReports.v1";

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  /* ---------- Mobile navigation ---------- */
  function initNav() {
    var toggle = document.querySelector(".nav-toggle");
    var nav = document.getElementById("primary-nav");
    if (!toggle || !nav) return;
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
    });
    nav.addEventListener("click", function (event) {
      if (event.target.closest("a") && nav.classList.contains("is-open")) {
        nav.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  /* ---------- Flash messages ---------- */
  function initFlash() {
    document.querySelectorAll(".flash-close").forEach(function (button) {
      button.addEventListener("click", function () {
        var flash = button.closest(".flash");
        if (flash) flash.remove();
      });
    });
  }

  /* ---------- Copy to clipboard ---------- */
  function copyText(value) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(value);
    }
    return new Promise(function (resolve, reject) {
      var area = document.createElement("textarea");
      area.value = value;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try {
        document.execCommand("copy") ? resolve() : reject(new Error("copy failed"));
      } catch (error) {
        reject(error);
      } finally {
        area.remove();
      }
    });
  }

  function initCopy() {
    document.querySelectorAll(".copy-btn").forEach(function (button) {
      button.addEventListener("click", function () {
        var value = button.getAttribute("data-copy") || "";
        if (!value) return;
        var original = button.textContent;
        copyText(value).then(
          function () {
            button.textContent = "Copied";
            window.setTimeout(function () {
              button.textContent = original;
            }, 1600);
          },
          function () {
            button.textContent = "Copy failed";
            window.setTimeout(function () {
              button.textContent = original;
            }, 1600);
          }
        );
      });
    });
  }

  /* ---------- Character counters ---------- */
  function initCounters() {
    document.querySelectorAll("[data-count-for]").forEach(function (counter) {
      var field = document.getElementById(counter.getAttribute("data-count-for"));
      if (!field) return;
      var max = counter.getAttribute("data-max") || field.maxLength || 0;
      function update() {
        counter.textContent = field.value.length + " / " + max;
      }
      field.addEventListener("input", update);
      update();
    });
  }

  /* ---------- Submit state for server-validated forms ---------- */
  function initSubmitState() {
    document.querySelectorAll("form[data-loading-form]").forEach(function (form) {
      form.addEventListener("submit", function () {
        if (typeof form.checkValidity === "function" && !form.checkValidity()) return;
        var button = form.querySelector('button[type="submit"]');
        if (!button || button.disabled) return;
        button.disabled = true;
        button.dataset.originalText = button.textContent;
        button.textContent = "Submitting…";
      });
    });
  }

  function readSaved() {
    try {
      var raw = window.localStorage.getItem(SAVED_KEY);
      var parsed = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(parsed)) return [];
      return parsed
        .filter(function (id) {
          return typeof id === "string" && /^CIV-\d{4,}$/i.test(id);
        })
        .map(function (id) {
          return id.toUpperCase();
        })
        .filter(function (id, index, list) {
          return list.indexOf(id) === index;
        });
    } catch (error) {
      return [];
    }
  }

  function writeSaved(ids) {
    try {
      window.localStorage.setItem(SAVED_KEY, JSON.stringify(ids));
    } catch (error) {
      /* Storage may be unavailable (private mode); the page still works. */
    }
  }

  function saveId(id) {
    var ids = readSaved();
    var normalised = id.trim().toUpperCase();
    if (!/^CIV-\d{4,}$/.test(normalised)) return { ok: false, reason: "Use the format CIV-0001." };
    if (ids.indexOf(normalised) !== -1) {
      return { ok: false, reason: "That complaint ID is already saved on this device." };
    }
    ids.unshift(normalised);
    writeSaved(ids.slice(0, 50));
    return { ok: true };
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function statusClass(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/\s+/g, "-");
  }

  function priorityClass(value) {
    return String(value || "low").toLowerCase();
  }

  function formatDate(value) {
    if (!value) return "";
    var date = new Date(value);
    if (isNaN(date.getTime())) return "";
    return date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
  }

  function buildSavedCard(data) {
    var card = el("article", "saved-report-card");
    var top = el("div", "saved-report-top");
    top.appendChild(el("span", "saved-report-id", data.public_id));
    var status = el("span", "badge status-" + statusClass(data.status), data.status);
    top.appendChild(status);
    if (data.priority_level) {
      top.appendChild(
        el("span", "badge priority-" + priorityClass(data.priority_level), data.priority_level)
      );
    }
    card.appendChild(top);

    var title = el("h3");
    var link = el("a", null, data.title || "(untitled complaint)");
    link.href = "/track/" + encodeURIComponent(data.public_id);
    title.appendChild(link);
    card.appendChild(title);

    var meta = el("div", "saved-report-meta");
    if (data.category) meta.appendChild(el("span", null, data.category));
    if (data.address) meta.appendChild(el("span", null, data.address));
    if (data.created_at) meta.appendChild(el("span", null, "Submitted " + formatDate(data.created_at)));
    card.appendChild(meta);

    if (data.summary) card.appendChild(el("p", "saved-report-summary", data.summary));

    var foot = el("div", "saved-report-foot");
    var department =
      data.assigned_department || data.recommended_department || "Awaiting assignment";
    foot.appendChild(el("span", "muted-small", department));
    var actions = el("div", "saved-report-actions");
    var open = el("a", "btn btn-outline btn-small", "Open tracking");
    open.href = "/track/" + encodeURIComponent(data.public_id);
    actions.appendChild(open);
    var remove = el("button", "btn btn-ghost btn-small", "Remove");
    remove.type = "button";
    remove.addEventListener("click", function () {
      writeSaved(
        readSaved().filter(function (id) {
          return id !== data.public_id;
        })
      );
      card.remove();
      updateSavedStatus();
    });
    actions.appendChild(remove);
    foot.appendChild(actions);
    card.appendChild(foot);
    return card;
  }

  function buildErrorCard(id, message) {
    var card = el("article", "saved-report-card saved-report-error");
    var top = el("div", "saved-report-top");
    top.appendChild(el("span", "saved-report-id", id));
    top.appendChild(el("span", "badge badge-neutral", "Not found"));
    card.appendChild(top);
    card.appendChild(el("p", null, message || "This complaint ID could not be loaded."));
    var actions = el("div", "saved-report-actions");
    var remove = el("button", "btn btn-ghost btn-small", "Remove from this device");
    remove.type = "button";
    remove.addEventListener("click", function () {
      writeSaved(
        readSaved().filter(function (savedId) {
          return savedId !== id;
        })
      );
      card.remove();
      updateSavedStatus();
    });
    actions.appendChild(remove);
    card.appendChild(actions);
    return card;
  }

  function updateSavedStatus(extra) {
    var status = document.getElementById("saved-reports-status");
    if (!status) return;
    var count = readSaved().length;
    var text = count
      ? count + (count === 1 ? " complaint ID saved on this device." : " complaint IDs saved on this device.")
      : "No complaint IDs saved on this device yet.";
    status.textContent = extra ? extra + " " + text : text;
  }

  function initSavedReports() {
    var container = document.getElementById("saved-reports");
    if (!container) return;
    var form = document.getElementById("saved-add-form");
    var input = document.getElementById("saved-complaint-id");
    updateSavedStatus();

    if (form && input) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        var result = saveId(input.value);
        if (!result.ok) {
          updateSavedStatus(result.reason);
          input.focus();
          return;
        }
        input.value = "";
        updateSavedStatus("Complaint ID added.");
        renderSavedReports();
      });
    }

    renderSavedReports();
  }

  function renderSavedReports() {
    var container = document.getElementById("saved-reports");
    if (!container) return;
    var ids = readSaved();
    container.textContent = "";
    updateSavedStatus();
    if (!ids.length) {
      var empty = el("div", "empty-state");
      empty.appendChild(el("h3", null, "No saved reports yet"));
      empty.appendChild(
        el(
          "p",
          null,
          "Submit a complaint, or add an existing ID above. Only this browser sees this list."
        )
      );
      var cta = el("a", "btn btn-primary btn-small", "Report an issue");
      cta.href = "/report";
      empty.appendChild(cta);
      container.appendChild(empty);
      return;
    }

    ids.forEach(function (id) {
      var card = el("article", "saved-report-card");
      card.appendChild(el("div", "skeleton-card"));
      container.appendChild(card);
      fetch("/api/complaints/" + encodeURIComponent(id), {
        headers: { Accept: "application/json" },
      })
        .then(function (response) {
          if (!response.ok) throw new Error(response.status === 404 ? "Complaint not found." : "Unable to load this complaint.");
          return response.json();
        })
        .then(function (data) {
          if (card.isConnected) card.replaceWith(buildSavedCard(data));
        })
        .catch(function (error) {
          if (card.isConnected) card.replaceWith(buildErrorCard(id, error.message));
        });
    });
  }

  ready(function () {
    initNav();
    initFlash();
    initCopy();
    initCounters();
    initSubmitState();
    initSavedReports();
    window.CivicAI = {
      copyText: copyText,
      saveId: saveId,
      readSaved: readSaved,
    };
  });
})();
