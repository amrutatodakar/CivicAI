/* CivicAI officer dashboard: charts, map, filters and hotspot interactions. */
(function () {
  "use strict";

  var PRIORITY_COLORS = {
    Critical: "#b3261e",
    High: "#b8561f",
    Medium: "#8f6508",
    Low: "#216e43",
  };
  var STATUS_COLORS = {
    Submitted: "#28639c",
    "Under Review": "#8f6508",
    Assigned: "#5a4b91",
    "In Progress": "#b8561f",
    Resolved: "#1e7244",
  };
  var RESOLVED_COLOR = "#9aa9b4";
  var DEFAULT_CENTER = [22.31, 73.18];

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function parseData() {
    var node = document.getElementById("dashboard-data");
    if (!node) return null;
    try {
      return JSON.parse(node.textContent);
    } catch (error) {
      return null;
    }
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function statusClass(value) {
    return String(value || "").toLowerCase().replace(/\s+/g, "-");
  }

  function priorityClass(value) {
    return String(value || "low").toLowerCase();
  }

  function escapeHtml(value) {
    return String(value === undefined || value === null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function timeAgo(value) {
    if (!value) return "—";
    var date = new Date(value);
    if (isNaN(date.getTime())) return "—";
    var seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
    if (seconds < 60) return "just now";
    if (seconds < 3600) return Math.floor(seconds / 60) + " min ago";
    if (seconds < 86400) return Math.floor(seconds / 3600) + " h ago";
    if (seconds < 604800) return Math.floor(seconds / 86400) + " d ago";
    return date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
  }

  function markerColor(point) {
    if (point.status === "Resolved") return RESOLVED_COLOR;
    return PRIORITY_COLORS[point.priority_level] || "#617586";
  }

  ready(function () {
    var data = parseData();
    if (!data) return;
    var mapContext = initMap(data);
    try {
      initCharts(data);
    } catch (error) {
      if (window.console) window.console.warn("Chart rendering failed.", error);
    }
    initRefresh();
    initFilters(data, mapContext);
  });

  /* ------------------------------------------------------------
     Charts
     ------------------------------------------------------------ */
  function initCharts(data) {
    if (typeof window.Chart === "undefined") {
      fallback("chart-trends", "fallback-trends", data.trends.map(function (row) {
        return row.label + ": " + row.count + " report(s)";
      }));
      fallback("chart-priority", "fallback-priority", data.priority_distribution.map(function (row) {
        return row.level + ": " + row.count;
      }));
      fallback("chart-categories", "fallback-categories", data.category_distribution.map(function (row) {
        return row.category + ": " + row.count;
      }));
      fallback("chart-status", "fallback-status", data.status_distribution.map(function (row) {
        return row.status + ": " + row.count;
      }));
      return;
    }

    Chart.defaults.font.family =
      '"Segoe UI Variable", "Segoe UI", -apple-system, BlinkMacSystemFont, Inter, Roboto, Helvetica, Arial, sans-serif';
    Chart.defaults.color = "#617586";
    Chart.defaults.font.size = 11;

    var grid = { color: "rgba(18,33,47,.07)", drawBorder: false };

    new Chart(document.getElementById("chart-trends"), {
      type: "line",
      data: {
        labels: data.trends.map(function (row) {
          return row.label;
        }),
        datasets: [
          {
            label: "Reports",
            data: data.trends.map(function (row) {
              return row.count;
            }),
            borderColor: "#0b6b70",
            backgroundColor: "rgba(11,107,112,.12)",
            fill: true,
            tension: 0.32,
            pointRadius: 3,
            pointHoverRadius: 5,
            pointBackgroundColor: "#0b6b70",
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" },
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkipPadding: 8 } },
          y: { beginAtZero: true, ticks: { precision: 0 }, grid: grid },
        },
      },
    });

    new Chart(document.getElementById("chart-priority"), {
      type: "doughnut",
      data: {
        labels: data.priority_distribution.map(function (row) {
          return row.level;
        }),
        datasets: [
          {
            data: data.priority_distribution.map(function (row) {
              return row.count;
            }),
            backgroundColor: data.priority_distribution.map(function (row) {
              return PRIORITY_COLORS[row.level] || "#617586";
            }),
            borderWidth: 2,
            borderColor: "#ffffff",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 9, boxHeight: 9, padding: 12, usePointStyle: true } },
          tooltip: {
            callbacks: {
              label: function (context) {
                var total = context.dataset.data.reduce(function (sum, value) {
                  return sum + value;
                }, 0);
                var value = context.parsed;
                var pct = total ? Math.round((value / total) * 100) : 0;
                return " " + context.label + ": " + value + " (" + pct + "%)";
              },
            },
          },
        },
      },
    });

    new Chart(document.getElementById("chart-categories"), {
      type: "bar",
      data: {
        labels: data.category_distribution.map(function (row) {
          return row.category;
        }),
        datasets: [
          {
            label: "Reports",
            data: data.category_distribution.map(function (row) {
              return row.count;
            }),
            backgroundColor: "rgba(11,107,112,.78)",
            hoverBackgroundColor: "#075357",
            borderRadius: 4,
            barThickness: 14,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0 }, grid: grid },
          y: { grid: { display: false } },
        },
      },
    });

    new Chart(document.getElementById("chart-status"), {
      type: "bar",
      data: {
        labels: data.status_distribution.map(function (row) {
          return row.status;
        }),
        datasets: [
          {
            label: "Reports",
            data: data.status_distribution.map(function (row) {
              return row.count;
            }),
            backgroundColor: data.status_distribution.map(function (row) {
              return STATUS_COLORS[row.status] || "#617586";
            }),
            borderRadius: 4,
            barThickness: 14,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0 }, grid: grid },
          y: { grid: { display: false } },
        },
      },
    });
  }

  function fallback(canvasId, fallbackId, rows) {
    var canvas = document.getElementById(canvasId);
    var box = document.getElementById(fallbackId);
    if (canvas && canvas.parentElement) canvas.parentElement.hidden = true;
    if (!box) return;
    box.hidden = false;
    box.textContent = "";
    var note = el("p", null, "Charts could not load (offline or CDN blocked). Data table:");
    box.appendChild(note);
    var list = el("ul");
    rows.forEach(function (text) {
      list.appendChild(el("li", null, text));
    });
    box.appendChild(list);
  }

  /* ------------------------------------------------------------
     Map
     ------------------------------------------------------------ */
  function initMap(data) {
    var mapEl = document.getElementById("civic-map");
    if (!mapEl) return { render: function () {}, focusHotspot: function () {} };

    if (!window.L) {
      var note = document.getElementById("map-fallback-note");
      if (note) {
        note.hidden = false;
        note.textContent =
          "The map library could not load. Complaint locations and hotspot summaries are still available below and in the table.";
      }
      return { render: function () {}, focusHotspot: function () {} };
    }

    var map = L.map(mapEl, { scrollWheelZoom: false, zoomControl: true }).setView(DEFAULT_CENTER, 12);
    var tiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    });
    tiles.addTo(map);

    var tileFailure = false;
    tiles.on("tileerror", function () {
      if (tileFailure) return;
      tileFailure = true;
      var box = document.getElementById("map-fallback-note");
      if (box) {
        box.hidden = false;
        box.textContent =
          "Map tiles could not be loaded (no internet access or the tile server is blocked). The complaint table and hotspot summaries remain fully usable.";
      }
    });

    var complaintLayer = L.layerGroup().addTo(map);
    var hotspotLayer = L.layerGroup().addTo(map);
    var complaintBounds = null;

    function renderPoints(points) {
      complaintLayer.clearLayers();
      complaintBounds = L.latLngBounds();
      points.forEach(function (point) {
        if (point.lat === null || point.lng === null) return;
        if (point.lat === undefined || point.lng === undefined) return;
        var marker = L.circleMarker([point.lat, point.lng], {
          radius: point.status === "Resolved" ? 5 : 7,
          color: "#ffffff",
          weight: 1.5,
          fillColor: markerColor(point),
          fillOpacity: point.status === "Resolved" ? 0.6 : 0.92,
        });
        var popup =
          '<div class="map-popup">' +
          '<span class="mono">' + escapeHtml(point.public_id) + "</span>" +
          "<strong>" + escapeHtml(point.title) + "</strong>" +
          escapeHtml(point.category) + " · " + escapeHtml(point.status) + " · " + escapeHtml(point.priority_level) + " (" + escapeHtml(point.priority_score) + "/100)<br>" +
          escapeHtml(point.address) + "<br>" +
          '<a href="/officer/complaints/' + encodeURIComponent(point.public_id) + '">Open complaint →</a>' +
          "</div>";
        marker.bindPopup(popup);
        marker.bindTooltip(point.public_id + " · " + point.priority_level, { direction: "top" });
        marker.addTo(complaintLayer);
        complaintBounds.extend([point.lat, point.lng]);
      });
      var count = document.querySelector(".map-count");
      if (count) count.textContent = points.length + " geolocated";
      if (points.length && complaintBounds.isValid() && !map._civicInitialFit) {
        map.fitBounds(complaintBounds, { padding: [30, 30], maxZoom: 14 });
        map._civicInitialFit = true;
      }
    }

    function renderHotspots(clusters) {
      hotspotLayer.clearLayers();
      clusters.forEach(function (spot) {
        if (!spot.centroid) return;
        var color =
          spot.concern === "Critical concern"
            ? "#b3261e"
            : spot.concern === "High concern"
              ? "#b8561f"
              : "#8f6508";
        var circle = L.circle([spot.centroid.lat, spot.centroid.lng], {
          radius: spot.radius_m || 500,
          color: color,
          weight: 1.5,
          dashArray: "5 5",
          fillColor: color,
          fillOpacity: 0.07,
        });
        circle.bindPopup(
          "<strong>" + escapeHtml(spot.name) + "</strong>" +
            escapeHtml(spot.concern) + " · " + escapeHtml(spot.total) + " reports<br>" +
            escapeHtml(spot.insight || "")
        );
        circle.addTo(hotspotLayer);
        circle._civicHotspotId = spot.id;
      });
    }

    function focusHotspot(id) {
      var spot = (data.hotspot_data.clusters || []).find(function (item) {
        return item.id === id;
      });
      if (!spot) return;
      map.setView([spot.centroid.lat, spot.centroid.lng], 16);
      hotspotLayer.eachLayer(function (layer) {
        if (layer._civicHotspotId === id) layer.openPopup();
      });
    }

    renderPoints(data.map_points || []);
    renderHotspots((data.hotspot_data && data.hotspot_data.clusters) || []);

    window.setTimeout(function () {
      map.invalidateSize();
    }, 300);

    return { render: renderPoints, focusHotspot: focusHotspot };
  }

  /* ------------------------------------------------------------
     Refresh / filters / table
     ------------------------------------------------------------ */
  function initRefresh() {
    var button = document.getElementById("refresh-dashboard");
    if (!button) return;
    button.addEventListener("click", function () {
      button.disabled = true;
      button.textContent = "Refreshing…";
      window.location.reload();
    });
  }

  function initFilters(data, mapContext) {
    var form = document.getElementById("complaint-filters");
    if (!form) return;
    var tbody = document.getElementById("complaints-tbody");
    var loading = document.getElementById("table-loading");
    var count = document.getElementById("table-count");
    var title = document.getElementById("table-title");
    var clear = document.getElementById("clear-filters");

    var initialRows = data.recent || [];

    function setLoading(isLoading) {
      if (loading) loading.hidden = !isLoading;
    }

    function renderRows(rows) {
      if (!tbody) return;
      tbody.textContent = "";
      if (!rows.length) {
        var row = el("tr");
        var cell = el("td");
        cell.colSpan = 7;
        var empty = el("div", "empty-state compact-empty");
        empty.appendChild(el("strong", null, "No complaints match these filters."));
        empty.appendChild(el("p", null, "Try clearing one or more filters."));
        cell.appendChild(empty);
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
      }

      rows.forEach(function (item) {
        var row = el("tr");

        var complaintCell = el("td");
        var idLink = el("a", "table-id", item.public_id);
        idLink.href = "/officer/complaints/" + encodeURIComponent(item.public_id);
        complaintCell.appendChild(idLink);
        var titleLink = el("a", "table-title-link", item.title);
        titleLink.href = idLink.href;
        complaintCell.appendChild(titleLink);
        if (item.summary) complaintCell.appendChild(el("span", "table-summary", item.summary));
        row.appendChild(complaintCell);

        row.appendChild(el("td", null, item.category || "—"));

        var priorityCell = el("td");
        priorityCell.appendChild(
          el("span", "badge priority-" + priorityClass(item.priority_level), item.priority_level)
        );
        priorityCell.appendChild(el("span", "table-score", item.priority_score + "/100"));
        row.appendChild(priorityCell);

        var statusCell = el("td");
        statusCell.appendChild(el("span", "badge status-" + statusClass(item.status), item.status));
        row.appendChild(statusCell);

        row.appendChild(el("td", null, item.address || "—"));
        row.appendChild(el("td", null, timeAgo(item.created_at)));

        var arrowCell = el("td");
        var arrow = el("a", "row-arrow", "→");
        arrow.href = idLink.href;
        arrow.setAttribute("aria-label", "Open " + item.public_id);
        arrowCell.appendChild(arrow);
        row.appendChild(arrowCell);

        tbody.appendChild(row);
      });
    }

    function applyResults(rows, isFiltered) {
      renderRows(rows);
      if (count) {
        count.textContent = rows.length
          ? "Showing " + rows.length + (isFiltered ? " matching" : " most recent") + " report(s)"
          : "No matching reports";
      }
      if (title) title.textContent = isFiltered ? "Filtered complaints" : "Recent complaints";
      if (mapContext && mapContext.render) mapContext.render(rows);
    }

    function runFilter() {
      var params = new URLSearchParams();
      new FormData(form).forEach(function (value, key) {
        var text = String(value).trim();
        if (text) params.set(key, text);
      });
      var isFiltered = Array.from(params.keys()).some(function (key) {
        return key !== "sort" || params.get(key) !== "newest";
      });

      setLoading(true);
      fetch("/api/officer/complaints?" + params.toString(), {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      })
        .then(function (response) {
          if (response.status === 401) {
            throw new Error("Your officer session expired. Sign in again to apply filters.");
          }
          if (!response.ok) throw new Error("The complaint list could not be loaded.");
          return response.json();
        })
        .then(function (payload) {
          applyResults(payload.complaints || [], isFiltered);
        })
        .catch(function (error) {
          if (tbody) {
            tbody.textContent = "";
            var row = el("tr");
            var cell = el("td");
            cell.colSpan = 7;
            var box = el("div", "empty-state compact-empty");
            box.appendChild(el("strong", null, "Could not load complaints."));
            var message = el("p", null, error.message || "Please try again.");
            box.appendChild(message);
            if (/session expired/i.test(error.message || "")) {
              var link = el("a", "btn btn-primary btn-small", "Sign in again");
              link.href = "/officer/login?next=" + encodeURIComponent(window.location.pathname);
              box.appendChild(link);
            } else {
              var retry = el("button", "btn btn-outline btn-small", "Retry");
              retry.type = "button";
              retry.addEventListener("click", runFilter);
              box.appendChild(retry);
            }
            cell.appendChild(box);
            row.appendChild(cell);
            tbody.appendChild(row);
          }
        })
        .finally(function () {
          setLoading(false);
        });
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      runFilter();
    });

    if (clear) {
      clear.addEventListener("click", function () {
        form.reset();
        applyResults(initialRows, false);
        if (mapContext && mapContext.render) mapContext.render(data.map_points || []);
      });
    }

    document.querySelectorAll("[data-hotspot-id]").forEach(function (link) {
      link.addEventListener("click", function () {
        var id = link.getAttribute("data-hotspot-id");
        var spot = (data.hotspot_data.clusters || []).find(function (item) {
          return item.id === id;
        });
        if (spot && mapContext && mapContext.focusHotspot) mapContext.focusHotspot(id);
        if (spot) {
          var search = document.getElementById("filter-q");
          if (search) search.value = spot.name;
          runFilter();
        }
      });
    });

    document.querySelectorAll(".hotspot-map-btn").forEach(function (button) {
      button.addEventListener("click", function () {
        var lat = Number(button.getAttribute("data-lat"));
        var lng = Number(button.getAttribute("data-lng"));
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
        var mapEl = document.getElementById("civic-map");
        if (mapEl) mapEl.scrollIntoView({ behavior: "smooth", block: "center" });
        var spotId = null;
        var card = button.closest(".hotspot-card");
        var manage = card ? card.querySelector("[data-hotspot-id]") : null;
        if (manage) spotId = manage.getAttribute("data-hotspot-id");
        if (spotId && mapContext && mapContext.focusHotspot) {
          mapContext.focusHotspot(spotId);
        }
      });
    });
  }
})();
