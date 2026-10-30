/* CivicAI report page: map location picker and image preview. */
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function numberValue(input) {
    if (!input || input.value.trim() === "") return null;
    var value = Number(input.value);
    return Number.isFinite(value) ? value : null;
  }

  ready(function () {
    initMap();
    initImagePreview();
  });

  function initMap() {
    var mapEl = document.getElementById("location-map");
    if (!mapEl) return;

    var latInput = document.getElementById("latitude");
    var lngInput = document.getElementById("longitude");
    var statusEl = document.getElementById("map-status");
    var loadingEl = document.getElementById("map-loading");
    var locateBtn = document.getElementById("locate-me");
    var clearBtn = document.getElementById("clear-location");
    var defaultLat = Number(mapEl.getAttribute("data-lat")) || 22.31;
    var defaultLng = Number(mapEl.getAttribute("data-lng")) || 73.18;

    if (!window.L) {
      if (loadingEl) {
        loadingEl.textContent = "Map library could not load. Enter coordinates manually.";
        loadingEl.classList.remove("is-hidden");
      }
      return;
    }

    function setStatus(text, isSet) {
      if (!statusEl) return;
      statusEl.textContent = text;
      statusEl.classList.toggle("is-set", Boolean(isSet));
    }

    function round(value) {
      return Math.round(value * 100000) / 100000;
    }

    var hasInitial =
      latInput &&
      lngInput &&
      numberValue(latInput) !== null &&
      numberValue(lngInput) !== null;
    var initialLat = hasInitial ? numberValue(latInput) : defaultLat;
    var initialLng = hasInitial ? numberValue(lngInput) : defaultLng;

    var map = L.map(mapEl, {
      center: [initialLat, initialLng],
      zoom: hasInitial ? 16 : 14,
      scrollWheelZoom: false,
    });

    var tiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    });
    tiles.addTo(map);

    var tileFailureShown = false;
    tiles.on("tileerror", function () {
      if (tileFailureShown) return;
      tileFailureShown = true;
      var note = document.createElement("div");
      note.className = "map-fallback-note";
      note.textContent =
        "Map tiles could not be loaded (no internet access?). You can still type coordinates above.";
      note.style.margin = "8px";
      mapEl.appendChild(note);
    });

    var marker = null;

    function syncInputs(lat, lng) {
      if (latInput) latInput.value = round(lat);
      if (lngInput) lngInput.value = round(lng);
      setStatus(
        "Pin set at " + round(lat) + ", " + round(lng) + ". Drag the pin to adjust.",
        true
      );
    }

    function placeMarker(lat, lng, announce) {
      if (!marker) {
        marker = L.marker([lat, lng], { draggable: true }).addTo(map);
        marker.on("dragend", function () {
          var position = marker.getLatLng();
          syncInputs(position.lat, position.lng);
        });
      } else {
        marker.setLatLng([lat, lng]);
      }
      if (announce !== false) syncInputs(lat, lng);
    }

    function clearMarker() {
      if (marker) {
        map.removeLayer(marker);
        marker = null;
      }
      if (latInput) latInput.value = "";
      if (lngInput) lngInput.value = "";
      setStatus("No coordinates selected yet.", false);
    }

    map.on("click", function (event) {
      placeMarker(event.latlng.lat, event.latlng.lng);
    });

    function syncFromInputs() {
      var lat = numberValue(latInput);
      var lng = numberValue(lngInput);
      if (lat === null || lng === null) return;
      if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
        setStatus("Coordinates are outside the valid latitude/longitude range.", false);
        return;
      }
      placeMarker(lat, lng, false);
      map.setView([lat, lng], Math.max(map.getZoom(), 15));
      setStatus("Pin set at " + round(lat) + ", " + round(lng) + ".", true);
    }

    [latInput, lngInput].forEach(function (input) {
      if (!input) return;
      input.addEventListener("change", syncFromInputs);
      input.addEventListener("blur", syncFromInputs);
    });

    if (hasInitial) {
      placeMarker(initialLat, initialLng, false);
      setStatus("Pin set at " + round(initialLat) + ", " + round(initialLng) + ".", true);
    }

    if (locateBtn) {
      locateBtn.addEventListener("click", function () {
        if (!navigator.geolocation) {
          setStatus("This browser does not support geolocation. Type coordinates manually.", false);
          return;
        }
        locateBtn.disabled = true;
        setStatus("Requesting your location…", false);
        navigator.geolocation.getCurrentPosition(
          function (position) {
            locateBtn.disabled = false;
            var lat = position.coords.latitude;
            var lng = position.coords.longitude;
            map.setView([lat, lng], 16);
            placeMarker(lat, lng);
          },
          function (error) {
            locateBtn.disabled = false;
            var message =
              error && error.code === 1
                ? "Location permission was denied. Type coordinates or click the map instead."
                : "Your location could not be determined. Type coordinates or click the map instead.";
            setStatus(message, false);
          },
          { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
        );
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", clearMarker);
    }

    if (loadingEl) loadingEl.classList.add("is-hidden");

    // Leaflet needs a size recalculation if the container was initially hidden
    // or the viewport changed after load.
    window.setTimeout(function () {
      map.invalidateSize();
    }, 250);
  }

  function initImagePreview() {
    var input = document.getElementById("image");
    var wrapper = document.getElementById("image-preview");
    var image = document.getElementById("image-preview-img");
    var clear = document.getElementById("clear-image");
    if (!input || !wrapper || !image) return;

    var objectUrl = null;
    var allowed = ["image/png", "image/jpeg", "image/webp", "image/gif"];

    function revoke() {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
        objectUrl = null;
      }
    }

    input.addEventListener("change", function () {
      revoke();
      var file = input.files && input.files[0];
      if (!file) {
        wrapper.hidden = true;
        return;
      }
      if (allowed.indexOf(file.type) === -1) {
        wrapper.hidden = true;
        input.value = "";
        window.alert("Please choose a PNG, JPG, WEBP or GIF image.");
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        wrapper.hidden = true;
        input.value = "";
        window.alert("That image is larger than 5 MB. Please choose a smaller file.");
        return;
      }
      objectUrl = URL.createObjectURL(file);
      image.src = objectUrl;
      wrapper.hidden = false;
    });

    if (clear) {
      clear.addEventListener("click", function () {
        revoke();
        input.value = "";
        image.removeAttribute("src");
        wrapper.hidden = true;
      });
    }

    window.addEventListener("pagehide", revoke);
  }
})();
