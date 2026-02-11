// ================== tfl_live.js ==================
// TfL API Integration: Line Status, Live Arrivals, Santander Cycles

const TFL = {
  base: CONTROL_ROOM_CONFIG.tfl.baseUrl,
  arrivalCache: new Map(),  // naptanId -> { data, ts }
  statusTimer: null,
  bikesTimer: null,
  bikesLoaded: false
};

// Official TfL line colours
const TFL_LINE_COLOURS = {
  bakerloo: "#a45a2a",
  central: "#da291c",
  circle: "#ffcd00",
  district: "#007a33",
  "hammersmith-city": "#e89cae",
  jubilee: "#7C878e",
  metropolitan: "#840b55",
  northern: "#000000",
  piccadilly: "#10069f",
  victoria: "#00a3e0",
  "waterloo-city": "#6eceb2",
  dlr: "#00b2a9",
  "elizabeth-line": "#753bbd",
  elizabeth: "#753bbd",
  "london-overground": "#e87722",
  overground: "#e87722",
  tram: "#78be20",
  "lioness": "#ef9600",
  "mildmay": "#2774ae",
  "suffragette": "#5ba763",
  "weaver": "#893b67",
  "windrush": "#d22730",
  "liberty": "#606667"
};

// ══════════════════════════════════════════════════════
// LINE STATUS
// ══════════════════════════════════════════════════════

async function fetchTflLineStatus() {
  try {
    const modes = "tube,dlr,overground,elizabeth-line,tram";
    const r = await fetch(`${TFL.base}/Line/Mode/${modes}/Status`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const lines = await r.json();
    renderLineStatus(lines);
    return lines;
  } catch (e) {
    console.warn("TfL line status fetch failed:", e);
    const grid = document.getElementById("tfl-status-grid");
    if (grid) grid.innerHTML = '<div class="tfl-status-loading">Status unavailable</div>';
    return null;
  }
}

function getStatusBadge(severity) {
  if (severity === 10) return { text: "Good", cls: "tfl-badge-good" };
  if (severity === 9) return { text: "Minor Delays", cls: "tfl-badge-minor" };
  if (severity >= 6 && severity <= 8) return { text: "Severe", cls: "tfl-badge-severe" };
  if (severity >= 3 && severity <= 5) return { text: "Part Closed", cls: "tfl-badge-severe" };
  if (severity <= 2) return { text: "Suspended", cls: "tfl-badge-closed" };
  if (severity === 16 || severity === 20) return { text: "Closed", cls: "tfl-badge-closed" };
  return { text: "Info", cls: "tfl-badge-info" };
}

function renderLineStatus(lines) {
  const grid = document.getElementById("tfl-status-grid");
  const timeEl = document.getElementById("tfl-status-time");
  if (!grid) return;

  grid.innerHTML = "";

  // Sort: disrupted lines first, then alphabetically
  const sorted = [...lines].sort((a, b) => {
    const sa = a.lineStatuses?.[0]?.statusSeverity ?? 10;
    const sb = b.lineStatuses?.[0]?.statusSeverity ?? 10;
    if (sa !== sb) return sa - sb;  // lower severity (worse) first
    return a.name.localeCompare(b.name);
  });

  for (const line of sorted) {
    const status = line.lineStatuses?.[0];
    const severity = status?.statusSeverity ?? 10;
    const badge = getStatusBadge(severity);
    const colour = TFL_LINE_COLOURS[line.id] || "#64748b";
    const reason = status?.reason || "";

    const row = document.createElement("div");
    row.className = "tfl-status-row";
    if (reason) row.title = reason;

    row.innerHTML =
      `<span class="tfl-status-dot" style="background:${colour}"></span>` +
      `<span class="tfl-status-name">${escapeHtml(line.name)}</span>` +
      `<span class="tfl-status-badge ${badge.cls}">${badge.text}</span>`;

    grid.appendChild(row);
  }

  if (timeEl) {
    const now = new Date();
    timeEl.textContent = now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  }
}

function startLineStatusPolling() {
  fetchTflLineStatus();
  TFL.statusTimer = setInterval(fetchTflLineStatus, CONTROL_ROOM_CONFIG.tfl.statusRefresh);
}

// ══════════════════════════════════════════════════════
// LIVE ARRIVALS (on-demand per station)
// ══════════════════════════════════════════════════════

// NaPTAN ID cache: stationName -> naptanId
const NAPTAN_CACHE = {};

async function resolveNaptanId(stationName) {
  const key = stationName.toLowerCase().trim();
  if (NAPTAN_CACHE[key]) return NAPTAN_CACHE[key];

  try {
    const q = encodeURIComponent(stationName);
    const r = await fetch(`${TFL.base}/StopPoint/Search/${q}?modes=tube,dlr,overground,elizabeth-line,tram&maxResults=3`);
    if (!r.ok) return null;
    const data = await r.json();
    const matches = data.matches || [];
    if (matches.length > 0) {
      NAPTAN_CACHE[key] = matches[0].id;
      return matches[0].id;
    }
  } catch (e) {
    console.warn("NaPTAN resolve failed:", stationName, e);
  }
  return null;
}

async function fetchArrivals(naptanId) {
  // Check cache
  const cached = TFL.arrivalCache.get(naptanId);
  if (cached && Date.now() - cached.ts < CONTROL_ROOM_CONFIG.tfl.arrivalCache) {
    return cached.data;
  }

  try {
    const r = await fetch(`${TFL.base}/StopPoint/${naptanId}/Arrivals`);
    if (!r.ok) return [];
    const data = await r.json();

    // Sort by timeToStation ascending
    data.sort((a, b) => (a.timeToStation || 999) - (b.timeToStation || 999));

    TFL.arrivalCache.set(naptanId, { data, ts: Date.now() });

    // LRU cleanup
    if (TFL.arrivalCache.size > 30) {
      const oldest = TFL.arrivalCache.keys().next().value;
      TFL.arrivalCache.delete(oldest);
    }

    return data;
  } catch (e) {
    console.warn("Arrivals fetch failed:", naptanId, e);
    return [];
  }
}

function formatArrivalTime(seconds) {
  if (seconds < 30) return "Due";
  if (seconds < 60) return "<1 min";
  const mins = Math.round(seconds / 60);
  return `${mins} min`;
}

function renderArrivalsHtml(arrivals) {
  if (!arrivals || arrivals.length === 0) {
    return '<div class="tfl-arrivals"><div class="tfl-arrivals-empty">No upcoming arrivals</div></div>';
  }

  const shown = arrivals.slice(0, 6);
  let html = '<div class="tfl-arrivals"><div class="tfl-arrivals-title">Live Arrivals</div>';

  for (const a of shown) {
    const lineId = (a.lineId || "").toLowerCase();
    const colour = TFL_LINE_COLOURS[lineId] || "#64748b";
    const dest = a.towards || a.destinationName || "Unknown";
    const time = formatArrivalTime(a.timeToStation || 0);
    const platform = a.platformName ? ` (${a.platformName})` : "";

    html +=
      `<div class="tfl-arrival-row">` +
      `<span class="tfl-arrival-line" style="background:${colour}"></span>` +
      `<span class="tfl-arrival-dest" title="${escapeHtml(dest + platform)}">${escapeHtml(dest)}</span>` +
      `<span class="tfl-arrival-time">${time}</span>` +
      `</div>`;
  }

  if (arrivals.length > 6) {
    html += `<div class="tfl-arrivals-empty">+${arrivals.length - 6} more</div>`;
  }

  html += "</div>";
  return html;
}

// Public: build enhanced popup for a TfL station
async function buildTflStationPopup(stationName, linesInfo) {
  let basePopup =
    `<strong>${escapeHtml(stationName)}</strong>` +
    `<span class="popup-label">Lines</span> ${escapeHtml(linesInfo)}`;

  // Start with loading state
  const loadingHtml = basePopup +
    '<div class="tfl-arrivals"><div class="tfl-arrivals-loading">Loading arrivals...</div></div>';

  return {
    loadingHtml,
    fetchFull: async () => {
      const naptanId = await resolveNaptanId(stationName);
      if (!naptanId) {
        return basePopup + '<div class="tfl-arrivals"><div class="tfl-arrivals-empty">Arrivals unavailable</div></div>';
      }
      const arrivals = await fetchArrivals(naptanId);
      return basePopup + renderArrivalsHtml(arrivals);
    }
  };
}

// ══════════════════════════════════════════════════════
// SANTANDER CYCLES (BIKE DOCKS)
// ══════════════════════════════════════════════════════

async function fetchBikePoints() {
  try {
    setStatus("Loading Santander Cycles...");
    const r = await fetch(`${TFL.base}/BikePoint`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const docks = await r.json();

    // Clear existing
    layers.bikes.clearLayers();

    let count = 0;
    for (const dock of docks) {
      if (!dock.lat || !dock.lon) continue;

      // Extract bike/dock counts from additionalProperties
      const props = {};
      if (dock.additionalProperties) {
        for (const p of dock.additionalProperties) {
          props[p.key] = p.value;
        }
      }

      const bikes = parseInt(props.NbBikes || "0", 10);
      const ebikes = parseInt(props.NbEBikes || "0", 10);
      const empty = parseInt(props.NbEmptyDocks || "0", 10);
      const total = parseInt(props.NbDocks || "0", 10);

      // Colour based on availability
      let colour = "#22c55e";  // green = plenty
      if (bikes === 0) colour = "#ef4444";  // red = empty
      else if (bikes <= 3) colour = "#f59e0b";  // amber = low

      const marker = L.circleMarker([dock.lat, dock.lon], {
        radius: 4,
        color: colour,
        fillColor: colour,
        fillOpacity: 0.85,
        weight: 1.5,
        className: "bike-dock-marker"
      });

      const name = dock.commonName || "Bike Dock";
      marker.bindPopup(
        `<strong>${escapeHtml(name)}</strong>` +
        `<span class="popup-label">Santander Cycles</span><br>` +
        `<span class="popup-label">Bikes</span> <strong>${bikes}</strong>` +
        (ebikes > 0 ? ` (${ebikes} e-bikes)` : "") + `<br>` +
        `<span class="popup-label">Empty Docks</span> <strong>${empty}</strong> / ${total}`
      );

      marker.addTo(layers.bikes);
      count++;
    }

    TFL.bikesLoaded = true;
    setStatus(`${count} bike docks loaded`);
    console.log(`Santander Cycles: ${count} docks loaded`);
    return count;
  } catch (e) {
    console.warn("Santander Cycles fetch failed:", e);
    setStatus("Bike docks unavailable");
    return 0;
  }
}

function startBikePolling() {
  // Only load once layer is enabled (on-demand via toggle handler)
  TFL.bikesTimer = setInterval(() => {
    if (map.hasLayer(layers.bikes)) {
      fetchBikePoints();
    }
  }, CONTROL_ROOM_CONFIG.tfl.bikesRefresh);
}

// ══════════════════════════════════════════════════════
// INITIALIZATION
// ══════════════════════════════════════════════════════

function initTflLive() {
  // Start line status polling immediately
  startLineStatusPolling();

  // Set up bikes layer toggle — load on first enable
  const bikesCb = document.querySelector('[data-layer="bikes"]');
  if (bikesCb) {
    bikesCb.addEventListener("change", () => {
      if (bikesCb.checked && !TFL.bikesLoaded) {
        fetchBikePoints();
        startBikePolling();
      }
    });
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initTflLive);
} else {
  initTflLive();
}
