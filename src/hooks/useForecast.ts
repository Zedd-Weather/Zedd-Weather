import { useState, useEffect, useCallback } from 'react';
import { GoogleGenAI, Type } from '@google/genai';
import type { GeoLocation } from '../types/telemetry';
import type { ForecastDay } from '../types/forecast';
import type { RiskLevel, SectorId } from '../types/risk';
import { SECTOR_CONFIG } from '../types/risk';

const GOOGLE_WEATHER_API_KEY = import.meta.env.VITE_GOOGLE_WEATHER_API_KEY ?? '';
const GOOGLE_WEATHER_BASE = 'https://weather.googleapis.com/v1';
/** Conversion factor from km/h to m/s. */
const KMH_TO_MS = 3.6;

const apiKey = process.env.GEMINI_API_KEY || '';
const ai = new GoogleGenAI({ apiKey });

export function useForecast(piLocation: GeoLocation, activeTab: string) {
  const [forecastData, setForecastData] = useState<ForecastDay[]>([]);
  const [isFetchingForecast, setIsFetchingForecast] = useState(false);

  const fetchForecast = useCallback(async () => {
    if (!piLocation) return;
    setIsFetchingForecast(true);
    try {
      const forecastUrl =
        `${GOOGLE_WEATHER_BASE}/forecast:lookup` +
        `?key=${GOOGLE_WEATHER_API_KEY}`;

      const res = await fetch(forecastUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          location: { latitude: piLocation.lat, longitude: piLocation.lng },
          days: 7,
        }),
      });
      const data = await res.json();

      const dailyForecasts = data.forecastDays ?? [];
      if (dailyForecasts.length > 0) {
        const formatted: ForecastDay[] = dailyForecasts.map(
          (day: {
            displayDate?: string;
            daytimeForecast?: {
              temperature?: { degrees?: number };
              wind?: { speed?: { value?: number } };
              uvIndex?: number;
              precipitation?: { probability?: { percent?: number } };
            };
            overnightForecast?: {
              temperature?: { degrees?: number };
            };
          }) => ({
            date: day.displayDate
              ? new Date(day.displayDate).toLocaleDateString('en-US', {
                  weekday: 'short',
                  month: 'short',
                  day: 'numeric',
                })
              : '',
            tempMax: day.daytimeForecast?.temperature?.degrees ?? 0,
            tempMin: day.overnightForecast?.temperature?.degrees ?? 0,
            precip: day.daytimeForecast?.precipitation?.probability?.percent ?? 0,
            wind: day.daytimeForecast?.wind?.speed?.value
              ? day.daytimeForecast.wind.speed.value / KMH_TO_MS   // km/h → m/s
              : 0,
            uv: day.daytimeForecast?.uvIndex ?? 0,
          }),
        );
        setForecastData(formatted);
      }
    } catch (err) {
      console.error('Failed to fetch forecast:', err);
    } finally {
      setIsFetchingForecast(false);
    }
  }, [piLocation]);

  useEffect(() => {
    if (activeTab === 'forecast') {
      fetchForecast();
    }
  }, [activeTab, fetchForecast]);

  const analyzeForecast = useCallback(
    async (
      riskSector: SectorId,
    ): Promise<{ riskLevel: RiskLevel; report: string }> => {
      const sectorCfg = SECTOR_CONFIG[riskSector];
      const response = await ai.models.generateContent({
        model: 'gemini-2.0-flash',
        contents: `You are a Principal Edge AI and IoT Systems Architect monitoring ${sectorCfg.description}.
        Sector: ${sectorCfg.label}.
        Here is the 7-day weather forecast for the site:
        ${JSON.stringify(forecastData, null, 2)}
        
        Analyze this forecast for any upcoming risks relevant to ${sectorCfg.description}.
        Focus on: ${sectorCfg.focusAreas}.
        Provide strict mitigation directives that will be cryptographically signed to the ledger.`,
        config: {
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              riskLevel: {
                type: Type.STRING,
                description:
                  'The overall risk level based on the forecast. Must be one of: Green, Amber, Red, Black.',
                enum: ['Green', 'Amber', 'Red', 'Black'],
              },
              report: {
                type: Type.STRING,
                description:
                  'The detailed markdown report containing the analysis and mitigation directives.',
              },
            },
            required: ['riskLevel', 'report'],
          },
        },
      });
      const data = JSON.parse(response.text ?? '{}');
      return { riskLevel: data.riskLevel as RiskLevel, report: data.report as string };
    },
    [forecastData],
  );

  return {
    forecastData,
    isFetchingForecast,
    fetchForecast,
    analyzeForecast,
  };
}
