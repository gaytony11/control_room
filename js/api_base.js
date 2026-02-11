// ================== api_base.js ==================
// Shared API base URL helper.
// Set window.CONTROL_ROOM_API_BASE (e.g. https://control-room-proxy.<subdomain>.workers.dev)
// to route all internal API calls through a hosted proxy.

(function bootstrapApiBase() {
  const defaultHostedProxy = "https://control-room-proxy.ben-wilson2092.workers.dev";
  const raw = String(window.CONTROL_ROOM_API_BASE || defaultHostedProxy).trim();
  const normalized = raw.replace(/\/+$/, "");
  window.__CONTROL_ROOM_API_BASE = normalized;
})();

function apiUrl(path) {
  const p = String(path || "");
  if (!p) return p;
  if (/^https?:\/\//i.test(p)) return p;
  const base = window.__CONTROL_ROOM_API_BASE || "";
  if (!base) return p;
  const withSlash = p.startsWith("/") ? p : `/${p}`;
  return `${base}${withSlash}`;
}
