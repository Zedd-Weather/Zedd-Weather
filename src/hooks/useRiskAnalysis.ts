import { useState, useRef, useCallback } from 'react';
import { GoogleGenAI, Type } from '@google/genai';
import type { TelemetryData } from '../types/telemetry';
import type { RiskLevel, SectorId, DirectiveShard } from '../types/risk';
import { SECTOR_CONFIG } from '../types/risk';

const apiKey = process.env.GEMINI_API_KEY || '';
const ai = new GoogleGenAI({ apiKey });

export function useRiskAnalysis(currentTelemetry: TelemetryData) {
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [mediaPreview, setMediaPreview] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [riskReport, setRiskReport] = useState<string | null>(null);
  const [riskLevel, setRiskLevel] = useState<RiskLevel | null>(null);
  const [riskSector, setRiskSector] = useState<SectorId>('construction');
  const [directiveShards, setDirectiveShards] = useState<DirectiveShard[]>([]);
  const [isSharding, setIsSharding] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const autoAnalyzeRisk = useCallback(
    async (telemetry: TelemetryData) => {
      setIsAnalyzing(true);
      setDirectiveShards([]);
      try {
        const sectorCfg = SECTOR_CONFIG[riskSector];
        const response = await ai.models.generateContent({
          model: 'gemini-2.0-flash',
          contents: `You are a Principal Edge AI and IoT Systems Architect monitoring ${sectorCfg.description}.
          Sector: ${sectorCfg.label}.
          Current LIVE micro-climate telemetry:
          - Temperature: ${telemetry.temp.toFixed(1)}°C
          - Humidity: ${telemetry.humidity.toFixed(1)}%
          - Pressure: ${telemetry.pressure.toFixed(1)} hPa
          - Precipitation: ${telemetry.precipitation.toFixed(0)} %
          - Tide/Wave Level: ${telemetry.tide.toFixed(2)} m
          - UV Index: ${telemetry.uvIndex.toFixed(1)}
          - AQI: ${Math.round(telemetry.aqi)}

          Based purely on this real-time telemetry, identify any environmental risks relevant to ${sectorCfg.description}.
          Focus on: ${sectorCfg.focusAreas}.
          Provide strict mitigation directives that will be cryptographically signed to the ledger. Do not ask for images, base your analysis solely on the data provided.`,
          config: {
            responseMimeType: 'application/json',
            responseSchema: {
              type: Type.OBJECT,
              properties: {
                riskLevel: {
                  type: Type.STRING,
                  description:
                    'The overall risk level based on the telemetry. Must be one of: Green, Amber, Red, Black. Green is low risk, Black is full shutdown.',
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
        setRiskLevel(data.riskLevel as RiskLevel);
        setRiskReport(data.report as string);
      } catch (error: unknown) {
        console.error('Auto analysis failed', error);
        const errStr = typeof error === 'string' ? error : JSON.stringify(error);
        if (errStr.includes('429')) {
          setRiskReport(
            'AI Analysis is temporarily unavailable due to rate limits. Please wait a moment and try again.',
          );
        } else if (
          errStr.includes('500') ||
          errStr.includes('xhr error') ||
          errStr.includes('Rpc failed')
        ) {
          setRiskReport(
            'AI Analysis service is currently experiencing network issues. Retrying shortly...',
          );
        } else {
          setRiskReport(
            'Failed to perform automated risk analysis. Please check your connection or API key.',
          );
        }
        setRiskLevel('Amber');
      } finally {
        setIsAnalyzing(false);
      }
    },
    [riskSector],
  );

  const analyzeRisk = useCallback(async () => {
    if (!mediaFile) return;
    setIsAnalyzing(true);
    setRiskReport(null);
    setRiskLevel(null);
    setDirectiveShards([]);

    try {
      const reader = new FileReader();
      reader.onloadend = async () => {
        const base64Data = (reader.result as string).split(',')[1];

        const response = await ai.models.generateContent({
          model: 'gemini-2.0-flash',
          contents: [
            {
              inlineData: {
                data: base64Data,
                mimeType: mediaFile.type,
              },
            },
            `You are a Principal Edge AI and IoT Systems Architect analyzing ${SECTOR_CONFIG[riskSector].description}.
            Sector: ${SECTOR_CONFIG[riskSector].label}.
            Current live micro-climate telemetry from Sense HAT: 
            - Temperature: ${currentTelemetry.temp.toFixed(1)}°C
            - Humidity: ${currentTelemetry.humidity.toFixed(1)}%
            - Pressure: ${currentTelemetry.pressure.toFixed(1)} hPa
            - Precipitation: ${currentTelemetry.precipitation.toFixed(0)} %
            - Tide Level: ${currentTelemetry.tide.toFixed(2)} m
            - UV Index: ${currentTelemetry.uvIndex.toFixed(1)}
            - AQI: ${Math.round(currentTelemetry.aqi)}
            
            Analyze this media of the site. Identify any risks relevant to ${SECTOR_CONFIG[riskSector].description}.
            Focus on: ${SECTOR_CONFIG[riskSector].focusAreas}.
            Provide strict mitigation directives that will be cryptographically signed to the ledger.`,
          ],
          config: {
            responseMimeType: 'application/json',
            responseSchema: {
              type: Type.OBJECT,
              properties: {
                riskLevel: {
                  type: Type.STRING,
                  description:
                    'The overall risk level based on the telemetry and media. Must be one of: Green, Amber, Red, Black. Green is low risk, Black is full shutdown.',
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

        try {
          const data = JSON.parse(response.text || '{}');
          setRiskLevel(data.riskLevel || null);
          setRiskReport(data.report || 'Analysis failed.');
        } catch {
          setRiskReport('Failed to parse analysis response.');
        }
        setIsAnalyzing(false);
      };
      reader.readAsDataURL(mediaFile);
    } catch (error: unknown) {
      console.error('Error analyzing risk:', error);
      const errStr = typeof error === 'string' ? error : JSON.stringify(error);
      if (errStr.includes('429')) {
        setRiskReport(
          'AI Analysis is temporarily unavailable due to rate limits. Please wait a moment and try again.',
        );
      } else if (
        errStr.includes('500') ||
        errStr.includes('xhr error') ||
        errStr.includes('Rpc failed')
      ) {
        setRiskReport(
          'AI Analysis service is currently experiencing network issues. Please try again later.',
        );
      } else {
        setRiskReport('An error occurred during analysis.');
      }
      setRiskLevel('Amber');
      setIsAnalyzing(false);
    }
  }, [mediaFile, riskSector, currentTelemetry]);

  const shardDirectives = useCallback(
    async (saveToLocker: (shards: DirectiveShard[], report: string, level: RiskLevel | null) => void) => {
      if (!riskReport) return;
      setIsSharding(true);

      const chunks = riskReport.split('\n\n').filter((chunk) => chunk.trim().length > 0);

      const newShards: DirectiveShard[] = await Promise.all(
        chunks.map(async (chunk, index) => {
          const data = new TextEncoder().encode(chunk + Date.now() + index);
          const hashBuffer = await crypto.subtle.digest('SHA-256', data);
          const hashArray = Array.from(new Uint8Array(hashBuffer));
          const hexHash =
            '0x' + hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');

          return {
            id: `Shard-${index + 1}`,
            hash: hexHash,
            content: chunk,
          };
        }),
      );

      setDirectiveShards(newShards);
      saveToLocker(newShards, riskReport, riskLevel);
      setIsSharding(false);
    },
    [riskReport, riskLevel],
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files[0]) {
        const file = e.target.files[0];
        setMediaFile(file);
        if (mediaPreview) {
          URL.revokeObjectURL(mediaPreview);
        }
        setMediaPreview(URL.createObjectURL(file));
        setRiskReport(null);
      }
    },
    [mediaPreview],
  );

  return {
    mediaFile,
    mediaPreview,
    isAnalyzing,
    riskReport,
    riskLevel,
    riskSector,
    directiveShards,
    isSharding,
    fileInputRef,
    setRiskReport,
    setRiskLevel,
    setRiskSector,
    setDirectiveShards,
    setIsAnalyzing,
    autoAnalyzeRisk,
    analyzeRisk,
    shardDirectives,
    handleFileChange,
  };
}
