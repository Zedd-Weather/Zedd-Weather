import {
  Map as MapIcon,
  Loader2,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { GeoLocation } from '../types/telemetry';
import type { MapLink } from '../hooks/useSiteMap';
import { LoadingFallback } from './ui/LoadingFallback';

interface SiteMapPanelProps {
  piLocation: GeoLocation;
  isFetchingMap: boolean;
  mapReport: string | null;
  mapLinks: MapLink[];
  isLocating: boolean;
  onLocateMe: () => void;
  onFetchMapData: () => void;
}

export default function SiteMapPanel({
  piLocation,
  isFetchingMap,
  mapReport,
  mapLinks,
  isLocating,
  onLocateMe,
  onFetchMapData,
}: SiteMapPanelProps) {
  return (
    <div className="bg-[#111] border border-slate-800 rounded-xl p-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
        <div>
          <h2 className="text-lg font-medium flex items-center text-slate-200">
            <MapIcon className="w-5 h-5 mr-2 text-blue-400" />
            Site Map & Nearby Services
          </h2>
          {piLocation && (
            <p className="text-xs text-slate-500 mt-1 flex items-center">
              <MapIcon className="w-3 h-3 mr-1" />
              Location: {piLocation.lat.toFixed(4)}, {piLocation.lng.toFixed(4)}
            </p>
          )}
        </div>
        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
          <button
            onClick={onLocateMe}
            disabled={isLocating || isFetchingMap}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:bg-slate-900 disabled:text-slate-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center w-full sm:w-auto border border-slate-700"
          >
            {isLocating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <MapIcon className="w-4 h-4 mr-2" />}
            {isLocating ? 'Locating...' : 'Use My Location'}
          </button>
          <button
            onClick={onFetchMapData}
            disabled={isFetchingMap}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center w-full sm:w-auto"
          >
            {isFetchingMap ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <MapIcon className="w-4 h-4 mr-2" />}
            {isFetchingMap ? 'Querying Maps...' : 'Fetch Local Services'}
          </button>
        </div>
      </div>

      {isFetchingMap ? (
        <LoadingFallback message="Searching for nearby services..." />
      ) : mapReport ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div className="h-[300px] sm:h-[400px] w-full bg-[#1a1a1a] rounded-xl border border-slate-800 overflow-hidden">
              <iframe
                width="100%"
                height="100%"
                style={{ border: 0 }}
                loading="lazy"
                allowFullScreen
                referrerPolicy="no-referrer-when-downgrade"
                src={`https://maps.google.com/maps?q=${piLocation?.lat || 37.7749},${piLocation?.lng || -122.4194}&z=14&output=embed`}
              />
            </div>
            <div className="prose prose-invert prose-blue max-w-none bg-[#1a1a1a] p-6 rounded-xl border border-slate-800">
              <div className="markdown-body text-sm text-slate-300">
                <ReactMarkdown>{mapReport}</ReactMarkdown>
              </div>
            </div>
          </div>
          <div className="bg-[#1a1a1a] p-6 rounded-xl border border-slate-800">
            <h3 className="text-sm font-medium text-slate-400 mb-4 uppercase tracking-wider flex items-center">
              <MapIcon className="w-4 h-4 mr-2" />
              Map Links & Sources
            </h3>
            <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
              {mapLinks.length > 0 ? (
                mapLinks.map((mapData, idx) => (
                  <div key={idx} className="block p-4 bg-slate-900 border border-slate-800 rounded-lg text-sm transition-all group">
                    <a
                      href={mapData.uri}
                      target="_blank"
                      rel="noreferrer"
                      className="hover:text-blue-300 transition-colors"
                    >
                      <p className="text-blue-400 font-medium mb-1 line-clamp-2">
                        {mapData.title || 'View on Google Maps'}
                      </p>
                      <p className="text-xs text-slate-500 truncate mb-2">{mapData.uri}</p>
                    </a>
                    {mapData.placeAnswerSources?.reviewSnippets &&
                      mapData.placeAnswerSources.reviewSnippets.length > 0 && (
                        <div className="mt-2 space-y-2 border-t border-slate-800 pt-2">
                          {mapData.placeAnswerSources.reviewSnippets.map((snippet, sIdx) => (
                            <div key={sIdx} className="text-xs text-slate-400 italic bg-slate-800/50 p-2 rounded">
                              &quot;{snippet.text}&quot;
                              {snippet.authorName && (
                                <span className="block mt-1 text-slate-500">- {snippet.authorName}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                  </div>
                ))
              ) : (
                <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg text-center">
                  <p className="text-sm text-slate-500">No specific map links found.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="h-64 flex flex-col items-center justify-center text-slate-500 border-2 border-dashed border-slate-800 rounded-xl">
          <MapIcon className="w-12 h-12 text-slate-600 mb-4" />
          <p>Click &quot;Fetch Local Services&quot; to query Google Maps.</p>
        </div>
      )}
    </div>
  );
}
