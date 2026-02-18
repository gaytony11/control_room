import { getEnabledAPIs, getCapabilityMatrix } from "../api_catalogue/api_discovery.js";

function badge(ok) {
  return `<span class="google-api-badge ${ok ? "ok" : "down"}">${ok ? "Enabled" : "Disabled"}</span>`;
}

export function renderAPIDashboard(containerId = "google-api-dashboard-list", matrixId = "google-api-capability-matrix") {
  const apis = getEnabledAPIs();
  const matrix = getCapabilityMatrix();

  if (typeof document === "undefined") return { apis, matrix };
  const container = document.getElementById(containerId);
  const matrixEl = document.getElementById(matrixId);

  if (container) {
    container.innerHTML = apis
      .map((api) =>
        `<div class="google-api-row">
          <div class="google-api-main">
            <span class="google-api-name">${api.name}</span>
            <span class="google-api-method">${api.method}</span>
          </div>
          <div class="google-api-cap">${api.capability}</div>
          <div class="google-api-cat">${api.category.replace(/_/g, " ")}</div>
        </div>`
      )
      .join("");
  }

  if (matrixEl) {
    matrixEl.innerHTML =
      Object.entries(matrix)
        .map(([k, v]) => `<div class="google-matrix-item"><span>${k.replace(/_/g, " ")}</span>${badge(v)}</div>`)
        .join("");
  }

  return { apis, matrix };
}

async function runSelfTest(outputId = "google-api-selftest") {
  const output = document.getElementById(outputId);
  if (!output) return;
  if (!window.GoogleIntelligenceService) {
    output.textContent = "Google service unavailable";
    return;
  }
  if (!window.GoogleIntelligenceService.isConfigured()) {
    output.textContent = "Google API key missing";
    return;
  }

  output.textContent = "Running API probe...";
  try {
    const geo = await window.GoogleIntelligenceService.geocode("1 Osmond Drive, Wells, Somerset, BA5 2JX");
    const ok = geo && (geo.status === "OK" || Array.isArray(geo.results));
    output.textContent = ok
      ? `Probe OK: geocoding returned ${Array.isArray(geo.results) ? geo.results.length : 0} result(s)`
      : `Probe failed: ${geo?.status || "unknown status"}`;
  } catch (err) {
    output.textContent = `Probe error: ${String(err?.message || err)}`;
  }
}

if (typeof window !== "undefined") {
  window.renderAPIDashboard = renderAPIDashboard;
  window.runGoogleApiSelfTest = runSelfTest;

  const run = () => {
    renderAPIDashboard();
    document.getElementById("google-api-refresh-btn")?.addEventListener("click", () => renderAPIDashboard());
    document.getElementById("google-api-selftest-btn")?.addEventListener("click", () => runSelfTest());
    document.getElementById("google-api-enrich-selected-btn")?.addEventListener("click", async () => {
      const ids = Array.from(window._selectedEntityIds || []);
      if (!ids.length) {
        const out = document.getElementById("google-api-selftest");
        if (out) out.textContent = "Select one or more entities first.";
        return;
      }
      let ok = 0;
      for (const id of ids) {
        const res = await window.GoogleIntelligenceService.enrichEntityInStore(id, { includeEnvironment: true }).catch(() => null);
        if (res?.ok) ok += 1;
      }
      const out = document.getElementById("google-api-selftest");
      if (out) out.textContent = `Enriched ${ok}/${ids.length} selected entities`;
    });
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run, { once: true });
  else run();
}
