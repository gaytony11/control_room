// ================== opensky.js ==================
// OpenSky Network - Live Flight Tracking

const OPENSKY = {
  timer: null,
  lastFetch: 0,
  flightCount: 0,
  active: false,        // tracks whether the layer is enabled
  useCorsProxy: false,  // toggled on after first CORS failure
  retryAfter: 0         // rate-limit backoff timestamp
};

// State vector field indices
const SV = {
  ICAO24: 0,
  CALLSIGN: 1,
  ORIGIN: 2,
  LON: 5,
  LAT: 6,
  BARO_ALT: 7,
  ON_GROUND: 8,
  VELOCITY: 9,
  TRACK: 10,
  VERT_RATE: 11,
  GEO_ALT: 13,
  SQUAWK: 14
};

// Plane SVG (simple silhouette pointing north, rotated via CSS transform)
const PLANE_SVG = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
  <path d="M12 2 L14.5 9 L22 10 L15 14 L16.5 22 L12 18 L7.5 22 L9 14 L2 10 L9.5 9 Z" fill="currentColor"/>
</svg>`;

// ══════════════════════════════════════════════════════
// ALTITUDE -> COLOUR
// ══════════════════════════════════════════════════════

function altitudeColour(altMetres) {
  if (altMetres == null || altMetres <= 0) return "#94a3b8";     // ground/unknown: grey
  if (altMetres < 1000) return "#38bdf8";   // low: light blue
  if (altMetres < 3000) return "#22c55e";   // mid: green
  if (altMetres < 8000) return "#f59e0b";   // high: amber
  return "#ef4444";                          // very high: red
}

// ══════════════════════════════════════════════════════
// API FETCH
// ══════════════════════════════════════════════════════

function buildOpenSkyUrl() {
  const cfg = CONTROL_ROOM_CONFIG.opensky;
  const bb = cfg.bbox;
  const url = `${cfg.baseUrl}/states/all?lamin=${bb.lamin}&lamax=${bb.lamax}&lomin=${bb.lomin}&lomax=${bb.lomax}`;
  return url;
}

async function fetchFlights() {
  // Check rate-limit backoff
  if (OPENSKY.retryAfter > Date.now()) {
    const secs = Math.ceil((OPENSKY.retryAfter - Date.now()) / 1000);
    updateFlightInfo(`Rate limited, retry in ${secs}s`, 0);
    return null;
  }

  const url = buildOpenSkyUrl();

  try {
    let response;

    if (OPENSKY.useCorsProxy) {
      // Use CORS proxy
      const proxyUrl = CONTROL_ROOM_CONFIG.opensky.corsProxy + encodeURIComponent(url);
      response = await fetch(proxyUrl);
    } else {
      // Try direct first
      try {
        response = await fetch(url);
      } catch (directErr) {
        // CORS or network failure -> try proxy
        console.log("OpenSky direct fetch failed, trying CORS proxy...", directErr.message);
        OPENSKY.useCorsProxy = true;
        const proxyUrl = CONTROL_ROOM_CONFIG.opensky.corsProxy + encodeURIComponent(url);
        response = await fetch(proxyUrl);
      }
    }

    if (response.status === 429) {
      // Rate limited
      const retryHeader = response.headers.get("X-Rate-Limit-Retry-After-Seconds");
      const retrySecs = parseInt(retryHeader || "300", 10);
      OPENSKY.retryAfter = Date.now() + retrySecs * 1000;
      console.warn(`OpenSky rate limited. Retry in ${retrySecs}s`);
      updateFlightInfo(`Rate limited (${Math.ceil(retrySecs / 60)} min)`, OPENSKY.flightCount);
      return null;
    }

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    OPENSKY.lastFetch = Date.now();
    return data;
  } catch (e) {
    console.warn("OpenSky fetch failed:", e);
    updateFlightInfo("Connection failed", OPENSKY.flightCount);
    return null;
  }
}

// ══════════════════════════════════════════════════════
// RENDER FLIGHTS ON MAP
// ══════════════════════════════════════════════════════

function renderFlights(data) {
  layers.flights.clearLayers();

  if (!data || !data.states || data.states.length === 0) {
    OPENSKY.flightCount = 0;
    updateFlightInfo("No aircraft detected", 0);
    return;
  }

  let count = 0;

  for (const sv of data.states) {
    const lat = sv[SV.LAT];
    const lon = sv[SV.LON];
    if (lat == null || lon == null) continue;

    const callsign = (sv[SV.CALLSIGN] || "").trim();
    const origin = sv[SV.ORIGIN] || "Unknown";
    const alt = sv[SV.BARO_ALT];
    const geoAlt = sv[SV.GEO_ALT];
    const onGround = sv[SV.ON_GROUND];
    const velocity = sv[SV.VELOCITY];
    const track = sv[SV.TRACK];
    const vertRate = sv[SV.VERT_RATE];
    const squawk = sv[SV.SQUAWK];

    // Skip aircraft on ground
    if (onGround) continue;

    const colour = altitudeColour(alt);
    const rotation = track != null ? track : 0;

    // Altitude in feet
    const altFt = alt != null ? Math.round(alt * 3.28084) : "N/A";
    // Speed in knots
    const speedKts = velocity != null ? Math.round(velocity * 1.94384) : "N/A";
    // Vertical rate in ft/min
    const vsStr = vertRate != null ? `${vertRate > 0 ? "+" : ""}${Math.round(vertRate * 196.85)} ft/min` : "";

    // Create rotated plane icon
    const icon = L.divIcon({
      className: "flight-marker",
      html: `<div class="flight-marker-icon" style="color:${colour};transform:rotate(${rotation}deg)">${PLANE_SVG}</div>`,
      iconSize: [22, 22],
      iconAnchor: [11, 11],
      popupAnchor: [0, -14]
    });

    const marker = L.marker([lat, lon], { icon });

    const popup =
      `<strong>${escapeHtml(callsign || "No Callsign")}</strong>` +
      `<span class="popup-label">Origin</span> ${escapeHtml(origin)}<br>` +
      `<span class="popup-label">Altitude</span> ${altFt} ft<br>` +
      `<span class="popup-label">Speed</span> ${speedKts} kts<br>` +
      (vsStr ? `<span class="popup-label">Vertical</span> ${vsStr}<br>` : "") +
      `<span class="popup-label">Heading</span> ${track != null ? Math.round(track) + "°" : "N/A"}<br>` +
      (squawk ? `<span class="popup-label">Squawk</span> ${escapeHtml(squawk)}<br>` : "") +
      `<span class="popup-tag" style="background:rgba(245,158,11,0.15);color:#f59e0b;border:1px solid rgba(245,158,11,0.3);">OpenSky Live</span>`;

    marker.bindPopup(popup);
    marker.addTo(layers.flights);
    count++;
  }

  OPENSKY.flightCount = count;
  updateFlightInfo(null, count);
  setStatus(`${count} aircraft tracked`);
}

// ══════════════════════════════════════════════════════
// UI
// ══════════════════════════════════════════════════════

function updateFlightInfo(errorMsg, count) {
  const panel = document.getElementById("flight-info");
  const timeEl = document.getElementById("flight-info-time");
  if (!panel) return;

  if (!OPENSKY.active) {
    panel.innerHTML = '<span class="flight-info-text">Enable layer to track aircraft</span>';
    if (timeEl) timeEl.textContent = "";
    return;
  }

  if (errorMsg) {
    panel.innerHTML =
      `<div class="flight-info-stats">` +
      `<span class="flight-info-text">${escapeHtml(errorMsg)}</span>` +
      `<button class="flight-refresh-btn" onclick="manualFlightRefresh()">Retry</button>` +
      `</div>`;
  } else {
    panel.innerHTML =
      `<div class="flight-info-stats">` +
      `<span class="flight-stat"><span class="flight-stat-value">${count}</span> aircraft</span>` +
      `<button class="flight-refresh-btn" onclick="manualFlightRefresh()">Refresh</button>` +
      `</div>`;
  }

  if (timeEl && OPENSKY.lastFetch) {
    const t = new Date(OPENSKY.lastFetch);
    timeEl.textContent = t.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }
}

async function manualFlightRefresh() {
  // Reset rate limit if manually triggering
  OPENSKY.retryAfter = 0;

  const btn = document.querySelector(".flight-refresh-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Loading..."; }

  const data = await fetchFlights();
  if (data) renderFlights(data);

  if (btn) { btn.disabled = false; btn.textContent = "Refresh"; }
}

window.manualFlightRefresh = manualFlightRefresh;

// ══════════════════════════════════════════════════════
// AUTO-REFRESH LOOP
// ══════════════════════════════════════════════════════

async function flightRefreshLoop() {
  if (!OPENSKY.active) return;
  const data = await fetchFlights();
  if (data) renderFlights(data);
}

function startFlightTracking() {
  if (OPENSKY.active) return;
  OPENSKY.active = true;

  // Immediate first fetch
  flightRefreshLoop();

  // Start interval
  OPENSKY.timer = setInterval(flightRefreshLoop, CONTROL_ROOM_CONFIG.opensky.refreshInterval);
  updateFlightInfo(null, 0);
}

function stopFlightTracking() {
  OPENSKY.active = false;
  if (OPENSKY.timer) {
    clearInterval(OPENSKY.timer);
    OPENSKY.timer = null;
  }
  layers.flights.clearLayers();
  OPENSKY.flightCount = 0;
  updateFlightInfo(null, 0);
}

// ══════════════════════════════════════════════════════
// INITIALIZATION
// ══════════════════════════════════════════════════════

function initOpenSky() {
  // Wire up the flights layer toggle
  const cb = document.querySelector('[data-layer="flights"]');
  if (cb) {
    cb.addEventListener("change", () => {
      if (cb.checked) {
        startFlightTracking();
      } else {
        stopFlightTracking();
      }
    });
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initOpenSky);
} else {
  initOpenSky();
}
