/**
 * meteomatics.config.ts
 *
 * Configuration for the Meteomatics Weather API that replaces / augments the
 * existing OpenWeatherMap (now Open-Meteo) logic used by the telemetry layer.
 *
 * ⚠️ SERVER-SIDE ONLY — Meteomatics uses Basic-auth credentials which must
 * never be exposed in client bundles.  In the browser the Meteomatics data is
 * fetched via a backend proxy (e.g. the Node2 orchestrator).
 *
 * The Meteomatics API provides high-resolution, hyper-local forecast data that
 * is critical for construction site decision-making.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MeteomaticsConfig {
  /** Base URL for the Meteomatics API. */
  baseUrl: string;
  /** Basic-auth username. */
  user: string;
  /** Basic-auth password. */
  pass: string;
  /** Default site latitude when no override is given. */
  siteLatitude: number;
  /** Default site longitude when no override is given. */
  siteLongitude: number;
  /** Request timeout in milliseconds. */
  timeoutMs: number;
}

export interface MeteomaticsWeatherData {
  temperature: number;       // °C
  windSpeed: number;         // m/s
  windGusts: number;         // m/s
  precipitation: number;     // mm/h
  humidity: number;          // %
  pressure: number;          // hPa
  visibility: number;        // m
  uvIndex: number;
  cloudCover: number;        // %
  timestamp: string;         // ISO-8601
}

export interface MeteomaticsHazardFlags {
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

export const DEFAULT_METEOMATICS_CONFIG: MeteomaticsConfig = {
  baseUrl: process.env.METEOMATICS_URL ?? 'https://api.meteomatics.com',
  user: process.env.METEOMATICS_USER ?? '',
  pass: process.env.METEOMATICS_PASS ?? '',
  siteLatitude: parseFloat(process.env.SITE_LATITUDE ?? '51.5074'),  // London default
  siteLongitude: parseFloat(process.env.SITE_LONGITUDE ?? '-0.1278'),
  timeoutMs: 15_000,
};

/**
 * Parameters we request from Meteomatics for construction site assessment.
 * These map to the Meteomatics parameter syntax.
 */
export const METEOMATICS_PARAMETERS = [
  't_2m:C',                    // Temperature at 2 m
  'wind_speed_10m:ms',         // Wind speed at 10 m
  'wind_gusts_10m_1h:ms',     // Max wind gusts in last hour
  'precip_1h:mm',             // Precipitation last hour
  'relative_humidity_2m:p',   // Relative humidity at 2 m
  'msl_pressure:hPa',         // Mean sea level pressure
  'visibility:m',             // Visibility
  'uv:idx',                    // UV index
  'total_cloud_cover:p',      // Cloud cover
] as const;

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
// Helper – build a Meteomatics API URL for the current time-step
// ---------------------------------------------------------------------------

/**
 * Build the URL to fetch the current observation from Meteomatics.
 *
 * @param config  Optional overrides for the default config.
 * @returns       A fully-qualified Meteomatics REST URL.
 */
export function buildMeteomaticsUrl(config?: Partial<MeteomaticsConfig>): string {
  const cfg = { ...DEFAULT_METEOMATICS_CONFIG, ...config };
  const now = new Date().toISOString();
  const params = METEOMATICS_PARAMETERS.join(',');
  return `${cfg.baseUrl}/${now}/${params}/${cfg.siteLatitude},${cfg.siteLongitude}/json`;
}

/**
 * Build the Basic-auth header value for Meteomatics requests.
 */
export function buildAuthHeader(config?: Partial<MeteomaticsConfig>): string {
  const cfg = { ...DEFAULT_METEOMATICS_CONFIG, ...config };
  return 'Basic ' + btoa(`${cfg.user}:${cfg.pass}`);
}

/**
 * Fetch current weather data from the Meteomatics API.
 */
export async function fetchMeteomaticsWeather(
  config?: Partial<MeteomaticsConfig>,
): Promise<MeteomaticsWeatherData> {
  const cfg = { ...DEFAULT_METEOMATICS_CONFIG, ...config };
  const url = buildMeteomaticsUrl(cfg);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), cfg.timeoutMs);

  try {
    const res = await fetch(url, {
      headers: { Authorization: buildAuthHeader(cfg) },
      signal: controller.signal,
    });

    if (!res.ok) {
      throw new Error(`Meteomatics API error: ${res.status} ${res.statusText}`);
    }

    const json = await res.json();
    return parseMeteomaticsResponse(json);
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Derive hazard flags from raw weather data based on UK construction thresholds.
 */
export function deriveHazardFlags(
  weather: MeteomaticsWeatherData,
): MeteomaticsHazardFlags {
  return {
    highWind:
      weather.windSpeed >= HAZARD_THRESHOLDS.highWind ||
      weather.windGusts >= HAZARD_THRESHOLDS.highWind,
    extremeHeat: weather.temperature >= HAZARD_THRESHOLDS.extremeHeat,
    freezing: weather.temperature <= HAZARD_THRESHOLDS.freezing,
    heavyRain: weather.precipitation >= HAZARD_THRESHOLDS.heavyRain,
    poorVisibility: weather.visibility <= HAZARD_THRESHOLDS.poorVisibility,
    lightning: false, // Requires separate lightning API
    highUV: weather.uvIndex >= HAZARD_THRESHOLDS.highUV,
  };
}

// ---------------------------------------------------------------------------
// Internal parser
// ---------------------------------------------------------------------------

function parseMeteomaticsResponse(json: any): MeteomaticsWeatherData {
  const dataMap: Record<string, number> = {};

  for (const entry of json?.data ?? []) {
    const param: string = entry.parameter ?? '';
    const value: number = entry.coordinates?.[0]?.dates?.[0]?.value ?? 0;
    dataMap[param] = value;
  }

  return {
    temperature: dataMap['t_2m:C'] ?? 0,
    windSpeed: dataMap['wind_speed_10m:ms'] ?? 0,
    windGusts: dataMap['wind_gusts_10m_1h:ms'] ?? 0,
    precipitation: dataMap['precip_1h:mm'] ?? 0,
    humidity: dataMap['relative_humidity_2m:p'] ?? 0,
    pressure: dataMap['msl_pressure:hPa'] ?? 0,
    visibility: dataMap['visibility:m'] ?? 10000,
    uvIndex: dataMap['uv:idx'] ?? 0,
    cloudCover: dataMap['total_cloud_cover:p'] ?? 0,
    timestamp: new Date().toISOString(),
  };
}
