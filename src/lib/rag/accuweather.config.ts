/**
 * accuweather.config.ts
 *
 * Configuration for the AccuWeather API that provides high-resolution,
 * hyper-local forecast data critical for construction site decision-making.
 *
 * ⚠️ SERVER-SIDE ONLY — AccuWeather uses an API key which must never be
 * exposed in client bundles.  In the browser the AccuWeather data is
 * fetched via a backend proxy (e.g. the Node2 orchestrator).
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AccuWeatherConfig {
  /** Base URL for the AccuWeather API. */
  baseUrl: string;
  /** AccuWeather API key. */
  apiKey: string;
  /** Default site latitude when no override is given. */
  siteLatitude: number;
  /** Default site longitude when no override is given. */
  siteLongitude: number;
  /** Request timeout in milliseconds. */
  timeoutMs: number;
}

export interface AccuWeatherData {
  temperature: number;       // °C
  windSpeed: number;         // m/s
  windGusts: number;         // m/s
  precipitation: number;     // mm
  humidity: number;          // %
  pressure: number;          // hPa
  visibility: number;        // m (converted from km)
  uvIndex: number;
  cloudCover: number;        // %
  timestamp: string;         // ISO-8601
}

export interface WeatherHazardFlags {
  highWind: boolean;
  extremeHeat: boolean;
  freezing: boolean;
  heavyRain: boolean;
  poorVisibility: boolean;
  lightning: boolean;
  highUV: boolean;
}

// ---------------------------------------------------------------------------
// Default configuration — sourced from environment variables
// ---------------------------------------------------------------------------

export const DEFAULT_ACCUWEATHER_CONFIG: AccuWeatherConfig = {
  baseUrl: process.env.ACCUWEATHER_URL ?? 'https://dataservice.accuweather.com',
  apiKey: process.env.ACCUWEATHER_API_KEY ?? '',
  siteLatitude: parseFloat(process.env.SITE_LATITUDE ?? '51.5074'),  // London default
  siteLongitude: parseFloat(process.env.SITE_LONGITUDE ?? '-0.1278'),
  timeoutMs: 15_000,
};

/**
 * Thresholds used to derive hazard flags from raw weather data.
 * Based on HSE / CDM 2015 guidance for UK construction sites.
 */
export const HAZARD_THRESHOLDS = {
  /** Wind speed (m/s) above which crane operations should cease. */
  highWind: 13.0,
  /** Temperature (°C) above which heat-stress protocols activate. */
  extremeHeat: 30.0,
  /** Temperature (°C) below which cold-weather protocols activate. */
  freezing: 2.0,
  /** Precipitation (mm/h) above which exposed work should stop. */
  heavyRain: 4.0,
  /** Visibility (m) below which heavy plant operations halt. */
  poorVisibility: 200,
  /** UV index at or above which sun-protection measures are required. */
  highUV: 6,
} as const;

// ---------------------------------------------------------------------------
// Helper – resolve a location key from lat/lon
// ---------------------------------------------------------------------------

/**
 * Resolve geographic coordinates to an AccuWeather location key.
 */
export async function resolveLocationKey(
  config?: Partial<AccuWeatherConfig>,
): Promise<string | null> {
  const cfg = { ...DEFAULT_ACCUWEATHER_CONFIG, ...config };
  const url =
    `${cfg.baseUrl}/locations/v1/cities/geoposition/search` +
    `?apikey=${cfg.apiKey}&q=${cfg.siteLatitude},${cfg.siteLongitude}`;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), cfg.timeoutMs);

  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) {
      throw new Error(`AccuWeather location lookup error: ${res.status} ${res.statusText}`);
    }
    const json = await res.json();
    return json?.Key ?? null;
  } finally {
    clearTimeout(timeout);
  }
}

// ---------------------------------------------------------------------------
// Helper – build an AccuWeather current-conditions URL
// ---------------------------------------------------------------------------

/**
 * Build the URL to fetch current conditions from AccuWeather.
 *
 * @param locationKey  An AccuWeather location key.
 * @param config       Optional overrides for the default config.
 * @returns            A fully-qualified AccuWeather REST URL.
 */
export function buildCurrentConditionsUrl(
  locationKey: string,
  config?: Partial<AccuWeatherConfig>,
): string {
  const cfg = { ...DEFAULT_ACCUWEATHER_CONFIG, ...config };
  return (
    `${cfg.baseUrl}/currentconditions/v1/${locationKey}` +
    `?apikey=${cfg.apiKey}&details=true`
  );
}

/**
 * Fetch current weather data from the AccuWeather API.
 */
export async function fetchAccuWeatherData(
  config?: Partial<AccuWeatherConfig>,
): Promise<AccuWeatherData> {
  const cfg = { ...DEFAULT_ACCUWEATHER_CONFIG, ...config };

  const locationKey = await resolveLocationKey(cfg);
  if (!locationKey) {
    throw new Error('AccuWeather: could not resolve location key');
  }

  const url = buildCurrentConditionsUrl(locationKey, cfg);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), cfg.timeoutMs);

  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) {
      throw new Error(`AccuWeather API error: ${res.status} ${res.statusText}`);
    }
    const json = await res.json();
    return parseAccuWeatherResponse(json);
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Derive hazard flags from raw weather data based on UK construction thresholds.
 */
export function deriveHazardFlags(
  weather: AccuWeatherData,
): WeatherHazardFlags {
  return {
    highWind:
      weather.windSpeed >= HAZARD_THRESHOLDS.highWind ||
      weather.windGusts >= HAZARD_THRESHOLDS.highWind,
    extremeHeat: weather.temperature >= HAZARD_THRESHOLDS.extremeHeat,
    freezing: weather.temperature <= HAZARD_THRESHOLDS.freezing,
    heavyRain: weather.precipitation >= HAZARD_THRESHOLDS.heavyRain,
    poorVisibility: weather.visibility <= HAZARD_THRESHOLDS.poorVisibility,
    lightning: false, // Requires separate API
    highUV: weather.uvIndex >= HAZARD_THRESHOLDS.highUV,
  };
}

// ---------------------------------------------------------------------------
// Internal parser
// ---------------------------------------------------------------------------

function parseAccuWeatherResponse(json: unknown): AccuWeatherData {
  // AccuWeather current-conditions returns an array of observation objects
  const obs = Array.isArray(json) ? json[0] : json;

  return {
    temperature: obs?.Temperature?.Metric?.Value ?? 0,
    windSpeed: ((obs?.Wind?.Speed?.Metric?.Value ?? 0) as number) / 3.6, // km/h → m/s
    windGusts: ((obs?.WindGust?.Speed?.Metric?.Value ?? 0) as number) / 3.6,
    precipitation: obs?.PrecipitationSummary?.Precipitation?.Metric?.Value ?? 0,
    humidity: obs?.RelativeHumidity ?? 0,
    pressure: obs?.Pressure?.Metric?.Value ?? 0,
    visibility: (obs?.Visibility?.Metric?.Value ?? 10) * 1000, // km → m
    uvIndex: obs?.UVIndex ?? 0,
    cloudCover: obs?.CloudCover ?? 0,
    timestamp: new Date().toISOString(),
  };
}
