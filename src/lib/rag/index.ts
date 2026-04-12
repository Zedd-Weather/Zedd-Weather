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
  DEFAULT_METEOMATICS_CONFIG,
  METEOMATICS_PARAMETERS,
  HAZARD_THRESHOLDS,
  buildMeteomaticsUrl,
  buildAuthHeader,
  fetchMeteomaticsWeather,
  deriveHazardFlags,
} from './meteomatics.config';
export type {
  MeteomaticsConfig,
  MeteomaticsWeatherData,
  MeteomaticsHazardFlags,
} from './meteomatics.config';
