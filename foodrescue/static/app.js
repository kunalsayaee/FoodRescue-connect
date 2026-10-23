// "Use my location" buttons: fill hidden lat/lng inputs from the browser.
document.querySelectorAll("[data-geo]").forEach(function (btn) {
  btn.addEventListener("click", function () {
    var status = document.getElementById("geo-status");
    if (!navigator.geolocation) {
      status.textContent = "Your browser does not support location.";
      return;
    }
    status.textContent = "Finding your location...";
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        document.getElementById("lat").value = pos.coords.latitude.toFixed(6);
        document.getElementById("lng").value = pos.coords.longitude.toFixed(6);
        status.textContent = "Location saved for this form.";
      },
      function () {
        status.textContent = "Could not get your location. You can still continue without it.";
      }
    );
  });
});

// Browse page: draw listings on a Leaflet map (library is loaded only on that page).
(function () {
  var mapEl = document.getElementById("map");
  var dataEl = document.getElementById("markers-data");
  if (!mapEl || !dataEl) return;

  function draw() {
    var markers = JSON.parse(dataEl.textContent);
    var map = L.map(mapEl);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors"
    }).addTo(map);
    var points = markers.map(function (m) {
      var link = document.createElement("a");
      link.href = "/listings/" + m.id;
      link.textContent = m.title + " (" + m.servings + " servings)";
      L.marker([m.lat, m.lng]).addTo(map).bindPopup(link);
      return [m.lat, m.lng];
    });
    map.fitBounds(points, { padding: [30, 30], maxZoom: 15 });
  }

  var script = document.createElement("script");
  script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
  script.onload = draw;
  document.head.appendChild(script);
})();
