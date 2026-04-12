/**
 * TaskContextAgent.js
 *
 * Ingests Planned Work Inputs (activity type, location, workforce size, timing)
 * and cross-references them against the current weather data to identify
 * constraints that might affect work safety or legality.
 *
 * This agent is purely deterministic – it applies the activity-profile
 * thresholds defined in the construction models without calling an LLM.
 */

/**
 * @typedef {Object} PlannedWork
 * @property {string}   activity       Activity key (e.g. "crane_operations").
 * @property {string}   location       Free-text site description.
 * @property {string}   startTime      ISO-8601 planned start.
 * @property {number}   workerCount    Number of workers on site.
 * @property {string[]} equipmentList  Heavy equipment to be used.
 */

/**
 * @typedef {Object} TaskConstraints
 * @property {string}   activity
 * @property {string[]} haltReasons     Conditions that require a full stop.
 * @property {string[]} cautionReasons  Conditions that require extra controls.
 * @property {string[]} ppeRequired     PPE recommendations.
 * @property {boolean}  safeToStart     Overall flag.
 * @property {string}   riskBand        "low" | "medium" | "high" | "critical"
 */

// Activity-profile thresholds (mirrors Zweather/construction/models.py)
const PROFILES = {
  concrete_pouring: {
    name: 'Concrete Pouring',
    tempMin: 5, tempMax: 35, tempHaltMin: 0, tempHaltMax: 40,
    windOp: 10, windHalt: 15,
    rainSensitive: true, rainMax: 0,
  },
  crane_operations: {
    name: 'Crane Operations',
    tempMin: -10, tempMax: 40, tempHaltMin: -20, tempHaltMax: 45,
    windOp: 9, windHalt: 13,
    rainSensitive: false, rainMax: 10,
    minVisibility: 200,
  },
  roofing: {
    name: 'Roofing',
    tempMin: 2, tempMax: 38, tempHaltMin: -5, tempHaltMax: 42,
    windOp: 8, windHalt: 12,
    rainSensitive: true, rainMax: 0,
  },
  excavation: {
    name: 'Excavation',
    tempMin: -5, tempMax: 40, tempHaltMin: -15, tempHaltMax: 45,
    windOp: 15, windHalt: 20,
    rainSensitive: false, rainMax: 5,
  },
  steel_erection: {
    name: 'Steel Erection',
    tempMin: -5, tempMax: 40, tempHaltMin: -15, tempHaltMax: 45,
    windOp: 10, windHalt: 14,
    rainSensitive: true, rainMax: 2,
  },
  painting: {
    name: 'Painting / Coating',
    tempMin: 10, tempMax: 35, tempHaltMin: 5, tempHaltMax: 40,
    windOp: 6, windHalt: 10,
    rainSensitive: true, rainMax: 0,
  },
  general: {
    name: 'General Construction',
    tempMin: 0, tempMax: 38, tempHaltMin: -10, tempHaltMax: 43,
    windOp: 12, windHalt: 18,
    rainSensitive: false, rainMax: 8,
  },
};

/**
 * Identify constraints for the planned work given current weather.
 *
 * @param {Object}      weather     Current weather readings.
 * @param {PlannedWork}  plannedWork Planned work inputs.
 * @returns {TaskConstraints}
 */
export function identifyConstraints(weather, plannedWork) {
  const profile = PROFILES[plannedWork.activity] ?? PROFILES.general;
  const haltReasons = [];
  const cautionReasons = [];
  const ppeRequired = [];

  const temp = weather.temperature ?? 0;
  const wind = weather.windSpeed ?? 0;
  const gusts = weather.windGusts ?? 0;
  const rain = weather.precipitation ?? 0;
  const vis = weather.visibility ?? 10000;
  const uv = weather.uvIndex ?? 0;
  const humidity = weather.humidity ?? 0;

  // Temperature
  if (temp <= profile.tempHaltMin) {
    haltReasons.push(`Temperature ${temp}°C is below halt threshold (${profile.tempHaltMin}°C)`);
  } else if (temp < profile.tempMin) {
    cautionReasons.push(`Temperature ${temp}°C is below safe minimum (${profile.tempMin}°C)`);
  }
  if (temp >= profile.tempHaltMax) {
    haltReasons.push(`Temperature ${temp}°C exceeds halt threshold (${profile.tempHaltMax}°C)`);
  } else if (temp > profile.tempMax) {
    cautionReasons.push(`Temperature ${temp}°C exceeds safe maximum (${profile.tempMax}°C)`);
  }

  // Wind
  if (wind >= profile.windHalt || gusts >= profile.windHalt) {
    haltReasons.push(`Wind ${wind} m/s (gusts ${gusts} m/s) exceeds halt limit (${profile.windHalt} m/s)`);
  } else if (wind >= profile.windOp) {
    cautionReasons.push(`Wind ${wind} m/s is above operational limit (${profile.windOp} m/s)`);
  }

  // Rain
  if (profile.rainSensitive && rain > profile.rainMax) {
    haltReasons.push(`Precipitation ${rain} mm/h exceeds limit for ${profile.name} (max ${profile.rainMax} mm/h)`);
  }

  // Visibility
  if (profile.minVisibility && vis < profile.minVisibility) {
    haltReasons.push(`Visibility ${vis} m is below minimum (${profile.minVisibility} m)`);
  }

  // UV
  if (uv >= 11) {
    haltReasons.push(`UV index ${uv} is extreme – outdoor work must halt`);
  } else if (uv >= 6) {
    cautionReasons.push(`UV index ${uv} is high – sun protection required`);
    ppeRequired.push('UV-rated sunglasses', 'Sun cream SPF 30+', 'Wide-brim hard hat');
  }

  // Heat stress PPE
  if (temp > 30) {
    ppeRequired.push('Cooling vest', 'Electrolyte supplements');
  }

  // Cold PPE
  if (temp < 5) {
    ppeRequired.push('Insulated gloves', 'Thermal base layer');
  }

  // High humidity
  if (humidity > 85) {
    cautionReasons.push(`Humidity ${humidity}% is very high – heat stress risk elevated`);
  }

  // Always required
  ppeRequired.push('Hard hat', 'High-vis vest', 'Steel-toe boots');

  // Determine risk band
  let riskBand = 'low';
  if (haltReasons.length > 0) riskBand = 'critical';
  else if (cautionReasons.length >= 3) riskBand = 'high';
  else if (cautionReasons.length >= 1) riskBand = 'medium';

  return {
    activity: plannedWork.activity,
    haltReasons,
    cautionReasons,
    ppeRequired: [...new Set(ppeRequired)],
    safeToStart: haltReasons.length === 0,
    riskBand,
  };
}
