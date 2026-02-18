import API_KEYS from "../../00_config/api_keys.js";
import GOOGLE_API_CATALOGUE from "../api_catalogue/google_api_catalogue.js";

const DEFAULT_TIMEOUT_MS = 12000;
const DEFAULT_ROUTES_FIELD_MASK =
  "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.legs";

function getGoogleApiKey() {
  const fromModule = String(API_KEYS?.GOOGLE_MAPS || "").trim();
  if (fromModule) return fromModule;
  if (typeof window === "undefined") return "";
  return String(window.GOOGLE_MAPS_API_KEY || window.GOOGLE_STREETVIEW_API_KEY || "").trim();
}

function withTimeout(ms = DEFAULT_TIMEOUT_MS) {
  const ctl = new AbortController();
  const id = setTimeout(() => ctl.abort(), ms);
  return { signal: ctl.signal, clear: () => clearTimeout(id) };
}

async function fetchJson(url, options = {}) {
  const t = withTimeout(options.timeoutMs || DEFAULT_TIMEOUT_MS);
  try {
    const resp = await fetch(url, { ...options, signal: t.signal });
    const text = await resp.text();
    let data = null;
    try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { raw: text || "" }; }
    if (!resp.ok) {
      const msg = data?.error?.message || data?.error_message || `HTTP ${resp.status}`;
      throw new Error(msg);
    }
    return data;
  } finally {
    t.clear();
  }
}

function cleanAddress(address) {
  return String(address || "").replace(/\s+/g, " ").trim();
}

class GoogleIntelligenceService {
  get catalogue() {
    return GOOGLE_API_CATALOGUE;
  }

  getApiKey() {
    return getGoogleApiKey();
  }

  isConfigured() {
    return !!this.getApiKey();
  }

  _requireKey() {
    const key = this.getApiKey();
    if (!key) throw new Error("Google API key missing");
    return key;
  }

  _mapsGet(endpoint, params = {}) {
    const key = this._requireKey();
    const usp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v == null || v === "") return;
      usp.set(k, String(v));
    });
    usp.set("key", key);
    return `${endpoint}?${usp.toString()}`;
  }

  async geocode(address) {
    const endpoint = GOOGLE_API_CATALOGUE.geospatial_core.geocoding.endpoint;
    const addr = cleanAddress(address);
    if (!addr) return null;
    return fetchJson(this._mapsGet(endpoint, { address: addr }));
  }

  async reverseGeocode(lat, lng) {
    const endpoint = GOOGLE_API_CATALOGUE.geospatial_core.geocoding.endpoint;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    return fetchJson(this._mapsGet(endpoint, { latlng: `${lat},${lng}` }));
  }

  async getElevation(lat, lng) {
    const endpoint = GOOGLE_API_CATALOGUE.geospatial_core.elevation.endpoint;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    return fetchJson(this._mapsGet(endpoint, { locations: `${lat},${lng}` }));
  }

  async getNearbyPlaces(lat, lng, radius = 200) {
    const endpointBase = GOOGLE_API_CATALOGUE.geospatial_core.places.endpoint;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    const endpoint = `${endpointBase}/nearbysearch/json`;
    return fetchJson(this._mapsGet(endpoint, { location: `${lat},${lng}`, radius }));
  }

  async searchPlacesText(query, lat = null, lng = null, radius = 1000) {
    const endpointBase = GOOGLE_API_CATALOGUE.geospatial_core.places.endpoint;
    const q = String(query || "").trim();
    if (!q) return null;
    const endpoint = `${endpointBase}/textsearch/json`;
    const params = { query: q };
    if (Number.isFinite(lat) && Number.isFinite(lng)) {
      params.location = `${lat},${lng}`;
      params.radius = radius;
    }
    return fetchJson(this._mapsGet(endpoint, params));
  }

  async getPlaceDetails(placeId, fields = "name,formatted_address,geometry,types,url") {
    const endpointBase = GOOGLE_API_CATALOGUE.geospatial_core.places.endpoint;
    const pid = String(placeId || "").trim();
    if (!pid) return null;
    const endpoint = `${endpointBase}/details/json`;
    return fetchJson(this._mapsGet(endpoint, { place_id: pid, fields }));
  }

  async getDirections(origin, destination, waypoints = [], mode = "driving") {
    const endpoint = GOOGLE_API_CATALOGUE.routing.directions.endpoint;
    if (!origin || !destination) return null;
    return fetchJson(this._mapsGet(endpoint, {
      origin,
      destination,
      mode,
      waypoints: Array.isArray(waypoints) && waypoints.length ? waypoints.join("|") : undefined
    }));
  }

  async getDistanceMatrix(origins, destinations, mode = "driving") {
    const endpoint = GOOGLE_API_CATALOGUE.routing.distance_matrix.endpoint;
    if (!origins || !destinations) return null;
    return fetchJson(this._mapsGet(endpoint, {
      origins: Array.isArray(origins) ? origins.join("|") : origins,
      destinations: Array.isArray(destinations) ? destinations.join("|") : destinations,
      mode
    }));
  }

  async computeRoutes(requestBody = {}) {
    const endpoint = GOOGLE_API_CATALOGUE.routing.routes_api.endpoint;
    const key = this._requireKey();
    const headers = {
      "Content-Type": "application/json",
      "X-Goog-Api-Key": key,
      "X-Goog-FieldMask": DEFAULT_ROUTES_FIELD_MASK
    };
    return fetchJson(endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify(requestBody)
    });
  }

  async getTimezone(lat, lng, timestampSecs = Math.floor(Date.now() / 1000)) {
    const endpoint = GOOGLE_API_CATALOGUE.location_services.timezone.endpoint;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    return fetchJson(this._mapsGet(endpoint, { location: `${lat},${lng}`, timestamp: timestampSecs }));
  }

  async geolocateDevice(considerIp = true) {
    const endpoint = GOOGLE_API_CATALOGUE.location_services.geolocation.endpoint;
    const key = this._requireKey();
    const url = `${endpoint}?key=${encodeURIComponent(key)}`;
    return fetchJson(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ considerIp: !!considerIp })
    });
  }

  async getWeatherCurrent(lat, lng) {
    const endpoint = `${GOOGLE_API_CATALOGUE.environment.weather.endpoint}/v1/currentConditions:lookup`;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    return fetchJson(this._mapsGet(endpoint, { location: `${lat},${lng}` }));
  }

  async getAirQuality(lat, lng) {
    const endpoint = `${GOOGLE_API_CATALOGUE.environment.air_quality.endpoint}/v1/currentConditions:lookup`;
    const key = this._requireKey();
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    return fetchJson(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key
      },
      body: JSON.stringify({ location: { latitude: lat, longitude: lng } })
    });
  }

  async getPollenForecast(lat, lng, days = 1) {
    const endpoint = `${GOOGLE_API_CATALOGUE.environment.pollen.endpoint}/v1/forecast:lookup`;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    return fetchJson(this._mapsGet(endpoint, {
      location: `${lat},${lng}`,
      days: Math.max(1, Math.min(Number(days) || 1, 5))
    }));
  }

  async getSolarInsights(lat, lng, radiusMeters = 50) {
    const endpoint = `${GOOGLE_API_CATALOGUE.environment.solar.endpoint}/v1/buildingInsights:findClosest`;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    return fetchJson(this._mapsGet(endpoint, {
      location: `${lat},${lng}`,
      requiredQuality: "LOW",
      exactQualityRequired: false,
      radiusMeters: Math.max(10, Math.min(1000, Number(radiusMeters) || 50))
    }));
  }

  getMapTileUrl(z, x, y, scale = 1) {
    const endpoint = GOOGLE_API_CATALOGUE.imagery.map_tiles.endpoint;
    const key = this.getApiKey();
    if (!key) return "";
    return `${endpoint}/v1/2dtiles/${z}/${x}/${y}?scale=${encodeURIComponent(scale)}&key=${encodeURIComponent(key)}`;
  }

  getStreetView(lat, lng, size = "600x400") {
    const endpoint = GOOGLE_API_CATALOGUE.imagery.street_view_static.endpoint;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return "";
    return this._mapsGet(endpoint, { location: `${lat},${lng}`, size });
  }

  async getAerialView(address) {
    const endpoint = `${GOOGLE_API_CATALOGUE.imagery.aerial_view.endpoint}/v1/videos:lookupVideo`;
    const addr = cleanAddress(address);
    if (!addr) return null;
    return fetchJson(this._mapsGet(endpoint, { address: addr }));
  }

  async enrichLocation(input, options = {}) {
    const lat = Number(input?.lat);
    const lng = Number(input?.lng);
    const address = cleanAddress(input?.address || "");
    const includeEnvironment = options.includeEnvironment !== false;
    if (!this.isConfigured()) return { ok: false, reason: "NO_KEY" };
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return { ok: false, reason: "NO_COORDS" };

    const tasks = {
      geocode: address ? this.geocode(address) : this.reverseGeocode(lat, lng),
      elevation: this.getElevation(lat, lng),
      nearbyPlaces: this.getNearbyPlaces(lat, lng, options.placesRadius || 250),
      timezone: this.getTimezone(lat, lng),
      streetViewUrl: Promise.resolve(this.getStreetView(lat, lng))
    };

    if (includeEnvironment) {
      tasks.weather = this.getWeatherCurrent(lat, lng);
      tasks.airQuality = this.getAirQuality(lat, lng);
      tasks.pollen = this.getPollenForecast(lat, lng, 1);
      tasks.solar = this.getSolarInsights(lat, lng, 80);
    }

    const entries = Object.entries(tasks);
    const settled = await Promise.allSettled(entries.map(([, p]) => p));
    const out = { ok: true, failures: {} };
    settled.forEach((res, i) => {
      const key = entries[i][0];
      if (res.status === "fulfilled") out[key] = res.value;
      else {
        out[key] = null;
        out.failures[key] = String(res.reason?.message || res.reason || "failed");
      }
    });
    return out;
  }

  async enrichEntityInStore(entityId, options = {}) {
    if (!window.EntityStore) return { ok: false, reason: "NO_STORE" };
    const entity = window.EntityStore.getEntity(entityId);
    if (!entity) return { ok: false, reason: "NOT_FOUND" };
    const lat = Number(entity?.latLng?.[0]);
    const lng = Number(entity?.latLng?.[1]);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return { ok: false, reason: "NO_COORDS" };

    const intel = await this.enrichLocation({
      lat,
      lng,
      address: entity?.attributes?.address || entity?.label || ""
    }, options);
    if (!intel?.ok) return intel;

    const attrs = { ...(entity.attributes || {}) };
    const geo = intel.geocode || {};
    const geoFirst = Array.isArray(geo.results) ? geo.results[0] : null;
    const elevFirst = Array.isArray(intel.elevation?.results) ? intel.elevation.results[0] : null;
    const placeFirst = Array.isArray(intel.nearbyPlaces?.results) ? intel.nearbyPlaces.results[0] : null;
    attrs.google_enriched_at = new Date().toISOString();
    attrs.google_geocode_status = geo.status || "";
    attrs.google_formatted_address = geoFirst?.formatted_address || attrs.google_formatted_address || "";
    attrs.google_place_id = geoFirst?.place_id || attrs.google_place_id || "";
    attrs.google_elevation_m = Number.isFinite(Number(elevFirst?.elevation)) ? Number(elevFirst.elevation) : attrs.google_elevation_m;
    attrs.google_nearby_count = Array.isArray(intel.nearbyPlaces?.results) ? intel.nearbyPlaces.results.length : 0;
    attrs.google_nearby_top = placeFirst?.name || attrs.google_nearby_top || "";
    attrs.google_timezone = intel.timezone?.timeZoneId || attrs.google_timezone || "";
    attrs.google_timezone_name = intel.timezone?.timeZoneName || attrs.google_timezone_name || "";
    attrs.google_streetview_url = intel.streetViewUrl || attrs.google_streetview_url || "";
    attrs.google_weather_summary = intel.weather?.currentConditions?.weatherCondition?.description?.text || attrs.google_weather_summary || "";
    attrs.google_air_quality_index = intel.airQuality?.indexes?.[0]?.aqi || attrs.google_air_quality_index || "";
    attrs.google_pollen_index = intel.pollen?.dailyInfo?.[0]?.pollenTypeInfo?.[0]?.indexInfo?.value || attrs.google_pollen_index || "";
    attrs.google_solar_max_panels = intel.solar?.solarPotential?.maxArrayPanelsCount || attrs.google_solar_max_panels || "";
    if (Object.keys(intel.failures || {}).length) {
      attrs.google_enrichment_failures = JSON.stringify(intel.failures);
    }

    window.EntityStore.updateEntity(entityId, { attributes: attrs });
    return { ok: true, entityId, enrichment: intel };
  }
}

const instance = new GoogleIntelligenceService();

if (typeof window !== "undefined") {
  window.GoogleIntelligenceService = instance;
}

export default instance;
