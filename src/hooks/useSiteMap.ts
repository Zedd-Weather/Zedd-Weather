import { useState, useCallback } from 'react';
import { GoogleGenAI } from '@google/genai';
import type { GeoLocation } from '../types/telemetry';

const apiKey = process.env.GEMINI_API_KEY || '';
const ai = new GoogleGenAI({ apiKey });

export interface MapLink {
  uri: string;
  title?: string;
  placeAnswerSources?: {
    reviewSnippets?: { text: string; authorName?: string }[];
  };
}

export function useSiteMap(
  piLocation: GeoLocation,
  setPiLocation: (loc: GeoLocation) => void,
) {
  const [isFetchingMap, setIsFetchingMap] = useState(false);
  const [mapReport, setMapReport] = useState<string | null>(null);
  const [mapLinks, setMapLinks] = useState<MapLink[]>([]);
  const [isLocating, setIsLocating] = useState(false);

  const fetchSiteMapData = useCallback(
    async (overrideLocation?: GeoLocation) => {
      setIsFetchingMap(true);
      setMapReport(null);
      setMapLinks([]);

      try {
        const loc = overrideLocation || piLocation;
        const lat = loc?.lat || 37.7749;
        const lng = loc?.lng || -122.4194;

        const response = await ai.models.generateContent({
          model: 'gemini-2.0-flash',
          contents: `Find nearby emergency services and hardware stores near the coordinates ${lat}, ${lng}. Provide a brief logistics report.`,
          config: {
            tools: [{ googleMaps: {} } as any],
            toolConfig: {
              retrievalConfig: {
                latLng: { latitude: lat, longitude: lng },
              },
            } as any,
          },
        });

        setMapReport(response.text || 'Failed to fetch map data.');

        const chunks = (response as any).candidates?.[0]?.groundingMetadata
          ?.groundingChunks;
        if (chunks) {
          const links = chunks.map((chunk: any) => chunk.maps).filter(Boolean);
          const uniqueMap = new Map<string, MapLink>();
          for (const item of links as MapLink[]) {
            uniqueMap.set(item.uri, item);
          }
          const uniqueLinks: MapLink[] = Array.from(uniqueMap.values());
          setMapLinks(uniqueLinks);
        }
      } catch (error: unknown) {
        console.error('Error fetching map data:', error);
        const errStr = typeof error === 'string' ? error : JSON.stringify(error);
        if (errStr.includes('429')) {
          setMapReport(
            'Map data is temporarily unavailable due to rate limits. Please wait a moment and try again.',
          );
        } else if (
          errStr.includes('500') ||
          errStr.includes('xhr error') ||
          errStr.includes('Rpc failed')
        ) {
          setMapReport(
            'Map service is currently experiencing network issues. Please try again later.',
          );
        } else {
          const msg =
            error instanceof Error ? error.message : 'Unknown error';
          setMapReport(`An error occurred while fetching map data: ${msg}`);
        }
      } finally {
        setIsFetchingMap(false);
      }
    },
    [piLocation],
  );

  const locateMe = useCallback(async () => {
    setIsLocating(true);
    setMapReport(null);
    try {
      if ('geolocation' in navigator) {
        const position = await new Promise<GeolocationPosition>((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 10000 });
        });
        const newLocation: GeoLocation = {
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        };
        setPiLocation(newLocation);
        fetchSiteMapData(newLocation);
      } else {
        setMapReport('Geolocation is not supported by your browser.');
      }
    } catch (error) {
      console.error('Failed to get location', error);
      setMapReport(
        'Failed to get your current location. Please ensure location permissions are granted.',
      );
    } finally {
      setIsLocating(false);
    }
  }, [setPiLocation, fetchSiteMapData]);

  return {
    isFetchingMap,
    mapReport,
    mapLinks,
    isLocating,
    fetchSiteMapData,
    locateMe,
  };
}
