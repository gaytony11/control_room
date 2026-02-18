import GOOGLE_API_CATALOGUE from "./google_api_catalogue.js";

export function getEnabledAPIs() {
  const enabled = [];
  for (const category in GOOGLE_API_CATALOGUE) {
    const section = GOOGLE_API_CATALOGUE[category] || {};
    for (const api in section) {
      const def = section[api];
      if (def && def.enabled) {
        enabled.push({
          category,
          name: api,
          endpoint: def.endpoint,
          capability: def.capability,
          method: def.method || "GET"
        });
      }
    }
  }
  return enabled;
}

export function getCapabilityMatrix() {
  return {
    geospatial: !!GOOGLE_API_CATALOGUE.geospatial_core,
    routing: !!GOOGLE_API_CATALOGUE.routing,
    imagery: !!GOOGLE_API_CATALOGUE.imagery,
    environment: !!GOOGLE_API_CATALOGUE.environment,
    device_location: !!GOOGLE_API_CATALOGUE.location_services?.geolocation,
    terrain: !!GOOGLE_API_CATALOGUE.geospatial_core?.elevation
  };
}

if (typeof window !== "undefined") {
  window.GoogleAPIDiscovery = { getEnabledAPIs, getCapabilityMatrix };
}
