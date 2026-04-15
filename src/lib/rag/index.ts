/**
 * RAG module barrel export.
 */
export {
  DocumentIngestor,
  UK_LEGISLATION_SOURCES,
  DEFAULT_INGESTOR_CONFIG,
} from './DocumentIngestor';
export type {
  DocumentChunk,
  ChunkMetadata,
  IngestorConfig,
  LegislationSource,
} from './DocumentIngestor';

export {
  DEFAULT_ACCUWEATHER_CONFIG,
  HAZARD_THRESHOLDS,
  resolveLocationKey,
  buildCurrentConditionsUrl,
  fetchAccuWeatherData,
  deriveHazardFlags,
} from './accuweather.config';
export type {
  AccuWeatherConfig,
  AccuWeatherData,
  WeatherHazardFlags,
} from './accuweather.config';
