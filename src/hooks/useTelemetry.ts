import { useState, useEffect, useRef, useCallback } from 'react';
import type { TelemetryData, GeoLocation, HourlyWeatherPoint, HistoricalDataPoint } from '../types/telemetry';

const GOOGLE_WEATHER_API_KEY = import.meta.env.VITE_GOOGLE_WEATHER_API_KEY ?? '';
const GOOGLE_WEATHER_BASE = 'https://weather.googleapis.com/v1';

const DEFAULT_LOCATION: GeoLocation = { lat: 37.7749, lng: -122.4194 };
const DEFAULT_AQI = 42;
const DEFAULT_TIDE = 1.2;
const TELEMETRY_REFRESH_INTERVAL_MS = 60_000;

export function useTelemetry() {
  const [telemetrySource, setTelemetrySource] = useState<'onboard' | 'external'>('onboard');

  const [externalTelemetry, setExternalTelemetry] = useState<TelemetryData>({
    temp: 0,
    humidity: 0,
    pressure: 0,
    precipitation: 0,
    tide: 0,
    uvIndex: 0,
    aqi: 0,
  });

  const [onboardTelemetry, setOnboardTelemetry] = useState<TelemetryData>({
    temp: 22.5,
    humidity: 45.2,
    pressure: 1012.5,
    precipitation: 15,
    tide: DEFAULT_TIDE,
    uvIndex: 3.5,
    aqi: DEFAULT_AQI,
  });

  const [hourlyWeatherData, setHourlyWeatherData] = useState<HourlyWeatherPoint[]>([]);
  const [historicalData, setHistoricalData] = useState<HistoricalDataPoint[]>([]);
  const [historicalRange, setHistoricalRange] = useState<'7d' | '14d' | '30d'>('7d');
  const [piLocation, setPiLocation] = useState<GeoLocation>(DEFAULT_LOCATION);
  const [isFetchingHistory, setIsFetchingHistory] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);

  const currentTelemetry: TelemetryData =
    telemetrySource === 'onboard' ? onboardTelemetry : externalTelemetry;

  // Stable ref so the interval callback never goes stale
  const piLocationRef = useRef(piLocation);
  piLocationRef.current = piLocation;

  const fetchRealTelemetry = useCallback(
    async (location: GeoLocation): Promise<TelemetryData | null> => {
      try {
        const { lat, lng: lon } = location;

        // Google Weather API — current conditions
        const currentUrl =
          `${GOOGLE_WEATHER_BASE}/currentConditions:lookup` +
          `?key=${GOOGLE_WEATHER_API_KEY}`;
        const forecastUrl =
          `${GOOGLE_WEATHER_BASE}/forecast:lookup` +
          `?key=${GOOGLE_WEATHER_API_KEY}`;

        const [currentRes, forecastRes] = await Promise.all([
          fetch(currentUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              location: { latitude: lat, longitude: lon },
            }),
          }),
          fetch(forecastUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              location: { latitude: lat, longitude: lon },
              days: 1,
              hourlyForHours: 24,
            }),
          }),
        ]);

        const current = await currentRes.json();
        const forecast = await forecastRes.json();

        const newTelemetry: TelemetryData = {
          temp: current.temperature?.degrees ?? 0,
          humidity: current.humidity?.percent ?? 0,
          pressure: current.pressure?.meanSeaLevelMillibars ?? 0,
          precipitation: current.precipitation?.probability?.percent ?? 0,
          uvIndex: current.uvIndex ?? 0,
          aqi: current.airQuality?.aqi ?? DEFAULT_AQI,
          tide: DEFAULT_TIDE,
        };

        setExternalTelemetry(newTelemetry);
        setOnboardTelemetry(newTelemetry);

        // Parse hourly forecast data
        const hourlyForecasts = forecast.forecastHours ?? [];
        if (hourlyForecasts.length > 0) {
          const hourly: HourlyWeatherPoint[] = hourlyForecasts.map(
            (h: {
              displayDateTime?: string;
              temperature?: { degrees?: number };
              humidity?: { percent?: number };
              pressure?: { meanSeaLevelMillibars?: number };
            }) => ({
              time: h.displayDateTime
                ? new Date(h.displayDateTime).toLocaleTimeString('en-US', {
                    hour: '2-digit',
                    hour12: false,
                  })
                : '',
              temp: h.temperature?.degrees ?? 0,
              humidity: h.humidity?.percent ?? 0,
              pressure: h.pressure?.meanSeaLevelMillibars ?? 0,
            }),
          );
          setHourlyWeatherData(hourly);
        }

        setLastUpdated(Date.now());
        return newTelemetry;
      } catch (error) {
        console.error('Failed to fetch real telemetry:', error);
        return null;
      }
    },
    [],
  );

  const fetchHistoricalTelemetry = useCallback(
    async (days: number, location: GeoLocation) => {
      setIsFetchingHistory(true);
      try {
        const { lat, lng: lon } = location;

        // Google Weather API — historical data via history:lookup
        const historyUrl =
          `${GOOGLE_WEATHER_BASE}/history:lookup` +
          `?key=${GOOGLE_WEATHER_API_KEY}`;

        const res = await fetch(historyUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            location: { latitude: lat, longitude: lon },
            days,
            hourly: true,
          }),
        });
        const data = await res.json();

        const historyHours = data.historyHours ?? [];
        if (historyHours.length > 0) {
          const formattedData: HistoricalDataPoint[] = historyHours.map(
            (h: {
              displayDateTime?: string;
              temperature?: { degrees?: number };
              humidity?: { percent?: number };
              pressure?: { meanSeaLevelMillibars?: number };
              precipitation?: { probability?: { percent?: number } };
            }) => {
              const date = new Date(h.displayDateTime ?? '');
              return {
                time: date.toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                }),
                rawDate: date,
                temp: h.temperature?.degrees ?? 0,
                humidity: h.humidity?.percent ?? 0,
                pressure: h.pressure?.meanSeaLevelMillibars ?? 0,
                precipitation: h.precipitation?.probability?.percent ?? 0,
              };
            },
          );

          const step = days === 7 ? 6 : days === 14 ? 12 : 24;
          const sampledData = formattedData.filter((_: HistoricalDataPoint, i: number) => i % step === 0);

          setHistoricalData(sampledData);
        }
      } catch (error) {
        console.error('Failed to fetch historical telemetry:', error);
      } finally {
        setIsFetchingHistory(false);
      }
    },
    [],
  );

  const refreshTelemetry = useCallback(() => {
    return fetchRealTelemetry(piLocationRef.current);
  }, [fetchRealTelemetry]);

  // Init: geolocation + initial fetch + interval
  useEffect(() => {
    let isMounted = true;
    let interval: ReturnType<typeof setInterval> | undefined;

    const init = async () => {
      let location = DEFAULT_LOCATION;

      try {
        if ('geolocation' in navigator) {
          const position = await new Promise<GeolocationPosition>((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
          });
          location = { lat: position.coords.latitude, lng: position.coords.longitude };
        }
      } catch (geoError) {
        console.warn('Geolocation failed or denied, using default coordinates.', geoError);
      }

      if (isMounted) {
        setPiLocation(location);
        await fetchRealTelemetry(location);

        interval = setInterval(() => {
          fetchRealTelemetry(piLocationRef.current);
        }, TELEMETRY_REFRESH_INTERVAL_MS);
      }
    };

    init();

    return () => {
      isMounted = false;
      if (interval) clearInterval(interval);
    };
  }, [fetchRealTelemetry]);

  // Historical data effect
  useEffect(() => {
    if (piLocation) {
      const days = historicalRange === '7d' ? 7 : historicalRange === '14d' ? 14 : 30;
      fetchHistoricalTelemetry(days, piLocation);
    }
  }, [historicalRange, piLocation, fetchHistoricalTelemetry]);

  return {
    currentTelemetry,
    externalTelemetry,
    onboardTelemetry,
    telemetrySource,
    setTelemetrySource,
    hourlyWeatherData,
    historicalData,
    historicalRange,
    setHistoricalRange,
    piLocation,
    setPiLocation,
    isFetchingHistory,
    lastUpdated,
    refreshTelemetry,
    fetchRealTelemetry,
  };
}
