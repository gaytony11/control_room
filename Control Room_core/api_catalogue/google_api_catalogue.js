const GOOGLE_API_CATALOGUE = {
  geospatial_core: {
    geocoding: {
      enabled: true,
      endpoint: "https://maps.googleapis.com/maps/api/geocode/json",
      capability: "address_to_coordinates",
      method: "GET"
    },
    places: {
      enabled: true,
      endpoint: "https://maps.googleapis.com/maps/api/place",
      capability: "place_intelligence",
      method: "GET"
    },
    elevation: {
      enabled: true,
      endpoint: "https://maps.googleapis.com/maps/api/elevation/json",
      capability: "terrain_intelligence",
      method: "GET"
    }
  },
  routing: {
    directions: {
      enabled: true,
      endpoint: "https://maps.googleapis.com/maps/api/directions/json",
      capability: "route_analysis",
      method: "GET"
    },
    distance_matrix: {
      enabled: true,
      endpoint: "https://maps.googleapis.com/maps/api/distancematrix/json",
      capability: "travel_time_analysis",
      method: "GET"
    },
    routes_api: {
      enabled: true,
      endpoint: "https://routes.googleapis.com/directions/v2:computeRoutes",
      capability: "advanced_route_analysis",
      method: "POST"
    }
  },
  environment: {
    weather: {
      enabled: true,
      endpoint: "https://weather.googleapis.com",
      capability: "environment_intelligence",
      method: "GET"
    },
    air_quality: {
      enabled: true,
      endpoint: "https://airquality.googleapis.com",
      capability: "environment_risk_assessment",
      method: "POST"
    },
    pollen: {
      enabled: true,
      endpoint: "https://pollen.googleapis.com",
      capability: "biological_environment_intelligence",
      method: "GET"
    },
    solar: {
      enabled: true,
      endpoint: "https://solar.googleapis.com",
      capability: "structure_analysis",
      method: "GET"
    }
  },
  imagery: {
    map_tiles: {
      enabled: true,
      endpoint: "https://tile.googleapis.com",
      capability: "map_tile_access",
      method: "GET"
    },
    street_view_static: {
      enabled: true,
      endpoint: "https://maps.googleapis.com/maps/api/streetview",
      capability: "ground_imagery",
      method: "GET"
    },
    aerial_view: {
      enabled: true,
      endpoint: "https://aerialview.googleapis.com",
      capability: "3d_visual_intelligence",
      method: "GET"
    }
  },
  location_services: {
    geolocation: {
      enabled: true,
      endpoint: "https://www.googleapis.com/geolocation/v1/geolocate",
      capability: "device_position_estimation",
      method: "POST"
    },
    timezone: {
      enabled: true,
      endpoint: "https://maps.googleapis.com/maps/api/timezone/json",
      capability: "timezone_resolution",
      method: "GET"
    }
  }
};

if (typeof window !== "undefined") {
  window.GOOGLE_API_CATALOGUE = GOOGLE_API_CATALOGUE;
}

export default GOOGLE_API_CATALOGUE;
