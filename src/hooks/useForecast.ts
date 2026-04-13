import { useState, useEffect, useCallback } from 'react';
import { GoogleGenAI, Type } from '@google/genai';
import type { GeoLocation } from '../types/telemetry';
import type { ForecastDay } from '../types/forecast';
import type { RiskLevel, SectorId } from '../types/risk';
import { SECTOR_CONFIG } from '../types/risk';

const API_BASE_WEATHER = 'https://api.open-meteo.com/v1/forecast';

const apiKey = process.env.GEMINI_API_KEY || '';
const ai = new GoogleGenAI({ apiKey });

export function useForecast(piLocation: GeoLocation, activeTab: string) {
  const [forecastData, setForecastData] = useState<ForecastDay[]>([]);
  const [isFetchingForecast, setIsFetchingForecast] = useState(false);

  const fetchForecast = useCallback(async () => {
    if (!piLocation) return;
    setIsFetchingForecast(true);
    try {
      const res = await fetch(
        `${API_BASE_WEATHER}?latitude=${piLocation.lat}&longitude=${piLocation.lng}&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max,uv_index_max&timezone=auto`,
      );
      const data = await res.json();
      if (data && data.daily) {
        const formatted: ForecastDay[] = data.daily.time.map((timeStr: string, i: number) => ({
          date: new Date(timeStr).toLocaleDateString('en-US', {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
          }),
          tempMax: data.daily.temperature_2m_max[i],
          tempMin: data.daily.temperature_2m_min[i],
          precip: data.daily.precipitation_probability_max[i],
          wind: data.daily.wind_speed_10m_max[i],
          uv: data.daily.uv_index_max[i],
        }));
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
