import { useState } from 'react';
import {
  Activity,
  Camera,
  Loader2,
  Video,
  ShieldCheck,
  Database,
  Terminal,
  Download,
  Upload,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { TelemetryData } from '../types/telemetry';
import type { RiskLevel, SectorId, DirectiveShard } from '../types/risk';
import { SECTOR_CONFIG } from '../types/risk';
import { RiskBadge } from './ui/RiskBadge';
import { LoadingFallback } from './ui/LoadingFallback';

interface RiskAnalysisPanelProps {
  currentTelemetry: TelemetryData;
  riskSector: SectorId;
  setRiskSector: (sector: SectorId) => void;
  isAnalyzing: boolean;
  riskReport: string | null;
  riskLevel: RiskLevel | null;
  directiveShards: DirectiveShard[];
  isSharding: boolean;
  mediaFile: File | null;
  mediaPreview: string | null;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  importFileRef: React.RefObject<HTMLInputElement | null>;
  onAutoAnalyze: () => void;
  onAnalyzeMedia: () => void;
  onShardDirectives: () => void;
  onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onExportShards: () => void;
  onImportShards: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

export default function RiskAnalysisPanel({
  currentTelemetry,
  riskSector,
  setRiskSector,
  isAnalyzing,
  riskReport,
  riskLevel,
  directiveShards,
  isSharding,
  mediaFile,
  mediaPreview,
  fileInputRef,
  importFileRef,
  onAutoAnalyze,
  onAnalyzeMedia,
  onShardDirectives,
  onFileChange,
  onExportShards,
  onImportShards,
}: RiskAnalysisPanelProps) {
  const [showVisualAnalysis, setShowVisualAnalysis] = useState(false);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  return (
    <div className="space-y-6">
      {/* Risk badge at top */}
      {riskLevel && !isAnalyzing && (
        <RiskBadge level={riskLevel} showDescription className="mb-2" />
      )}

      {/* Sector selector (dropdown) */}
      <div className="bg-[#111] border border-slate-800 rounded-xl p-4">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <label htmlFor="sector-select" className="text-sm font-medium text-slate-400">Industry Sector:</label>
          <select
            id="sector-select"
            value={riskSector}
            onChange={(e) => setRiskSector(e.target.value as SectorId)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-sm text-slate-200 appearance-none focus:outline-none focus:border-emerald-500/50 transition-colors cursor-pointer"
          >
            {(Object.keys(SECTOR_CONFIG) as SectorId[]).map((key) => (
              <option key={key} value={key}>
                {SECTOR_CONFIG[key].icon} {SECTOR_CONFIG[key].label}
              </option>
            ))}
          </select>
          <span className="text-xs text-slate-500 ml-auto hidden sm:block">
            AI analysis tailored for {SECTOR_CONFIG[riskSector].label.toLowerCase()} operations
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left column */}
        <div className="space-y-8">
          {/* Automated telemetry analysis */}
          <div className="bg-[#111] border border-slate-800 rounded-xl p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-medium flex items-center text-slate-200">
                <Activity className="w-5 h-5 mr-2 text-rose-400" />
                Automated Telemetry Analysis
              </h2>
              <button
                onClick={onAutoAnalyze}
                disabled={isAnalyzing}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg border border-slate-700 transition-colors flex items-center disabled:opacity-50"
              >
                {isAnalyzing ? (
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Activity className="w-3.5 h-3.5 mr-1.5" />
                )}
                Refresh Analysis
              </button>
            </div>
            <p className="text-sm text-slate-400 mb-4">
              The system continuously monitors live telemetry and uses AI
              to generate mitigation directives automatically.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4 mb-4">
              <div className="bg-[#1a1a1a] p-2 sm:p-3 rounded-lg border border-slate-800">
                <p className="text-[10px] sm:text-xs text-slate-500">Live Temp</p>
                <p className="text-base sm:text-lg font-semibold text-slate-200">{currentTelemetry.temp.toFixed(1)}°C</p>
              </div>
              <div className="bg-[#1a1a1a] p-2 sm:p-3 rounded-lg border border-slate-800">
                <p className="text-[10px] sm:text-xs text-slate-500">Humidity</p>
                <p className="text-base sm:text-lg font-semibold text-slate-200">{currentTelemetry.humidity.toFixed(1)}%</p>
              </div>
              <div className="bg-[#1a1a1a] p-2 sm:p-3 rounded-lg border border-slate-800">
                <p className="text-[10px] sm:text-xs text-slate-500">Pressure</p>
                <p className="text-base sm:text-lg font-semibold text-slate-200">{currentTelemetry.pressure.toFixed(1)} hPa</p>
              </div>
              <div className="bg-[#1a1a1a] p-2 sm:p-3 rounded-lg border border-slate-800">
                <p className="text-[10px] sm:text-xs text-slate-500">Precipitation</p>
                <p className="text-base sm:text-lg font-semibold text-slate-200">{currentTelemetry.precipitation.toFixed(0)} %</p>
              </div>
              <div className="bg-[#1a1a1a] p-2 sm:p-3 rounded-lg border border-slate-800">
                <p className="text-[10px] sm:text-xs text-slate-500">Tide Level</p>
                <p className="text-base sm:text-lg font-semibold text-slate-200">{currentTelemetry.tide.toFixed(2)} m</p>
              </div>
              <div className="bg-[#1a1a1a] p-2 sm:p-3 rounded-lg border border-slate-800">
                <p className="text-[10px] sm:text-xs text-slate-500">UV Index</p>
                <p className="text-base sm:text-lg font-semibold text-slate-200">{currentTelemetry.uvIndex.toFixed(1)}</p>
              </div>
              <div className="bg-[#1a1a1a] p-2 sm:p-3 rounded-lg border border-slate-800">
                <p className="text-[10px] sm:text-xs text-slate-500">Live AQI</p>
                <p className="text-base sm:text-lg font-semibold text-slate-200">{Math.round(currentTelemetry.aqi)}</p>
              </div>
            </div>
          </div>

          {/* Advanced: Visual Analysis (collapsible) */}
          <div>
            <button
              onClick={() => setShowVisualAnalysis(!showVisualAnalysis)}
              className="flex items-center space-x-2 text-sm font-medium text-slate-400 hover:text-slate-200 transition-colors mb-4"
            >
              {showVisualAnalysis ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              <Camera className="w-4 h-4" />
              <span>Advanced: Visual Analysis</span>
            </button>
            {showVisualAnalysis && (
              <div className="bg-[#111] border border-slate-800 rounded-xl p-6 animate-in fade-in slide-in-from-top-2 duration-200">
                <h2 className="text-lg font-medium flex items-center mb-6 text-slate-200">
                  <Camera className="w-5 h-5 mr-2 text-indigo-400" />
                  Add Visual Context (Optional)
                </h2>
                <p className="text-sm text-slate-400 mb-6">
                  Upload images or video of the {SECTOR_CONFIG[riskSector].label.toLowerCase()} site to cross-reference visual data with the live telemetry.
                </p>

                <div
                  className="border-2 border-dashed border-slate-700 rounded-xl p-8 text-center hover:bg-slate-800/30 transition-colors cursor-pointer"
                  onClick={() => fileInputRef.current?.click()}
                >
                  {mediaPreview ? (
                    mediaFile?.type.startsWith('video/') ? (
                      <video src={mediaPreview} controls className="max-h-64 mx-auto rounded-lg" />
                    ) : (
                      <img src={mediaPreview} alt="Preview" className="max-h-64 mx-auto rounded-lg object-contain" />
                    )
                  ) : (
                    <div className="flex flex-col items-center">
                      <Video className="w-12 h-12 text-slate-500 mb-4" />
                      <p className="text-slate-300 font-medium">Click to upload image or video</p>
                      <p className="text-slate-500 text-sm mt-2">Supports JPG, PNG, MP4, MOV</p>
                    </div>
                  )}
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={onFileChange}
                    accept="image/*,video/*"
                    className="hidden"
                  />
                </div>

                <button
                  onClick={onAnalyzeMedia}
                  disabled={!mediaFile || isAnalyzing}
                  className="w-full mt-6 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-medium rounded-lg transition-colors flex items-center justify-center"
                >
                  {isAnalyzing ? (
                    <>
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                      Analyzing Risk & Generating Directives...
                    </>
                  ) : (
                    <>
                      <Activity className="w-5 h-5 mr-2" />
                      Run Combined Analysis
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right column: Mitigation Directives */}
        <div className="bg-[#111] border border-slate-800 rounded-xl p-6 h-full flex flex-col">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-medium flex items-center text-slate-200">
              <ShieldCheck className="w-5 h-5 mr-2 text-emerald-400" />
              Mitigation Directives
            </h2>
          </div>

          <div className="flex-1 overflow-y-auto pr-2">
            {isAnalyzing ? (
              <LoadingFallback message="Running AI risk analysis..." />
            ) : riskReport ? (
              <div className="prose prose-invert prose-emerald max-w-none">
                <div className="markdown-body text-sm text-slate-300">
                  <ReactMarkdown>{riskReport}</ReactMarkdown>
                </div>
                <div className="mt-6 p-3 sm:p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <p className="text-[10px] sm:text-xs text-emerald-400 font-mono flex items-center">
                      <Terminal className="w-3 h-3 mr-2 flex-shrink-0" />
                      Directive ready for attestation (SHA-256)
                    </p>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={onExportShards}
                        disabled={directiveShards.length === 0}
                        className="px-2 sm:px-3 py-1 sm:py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white text-[10px] sm:text-xs font-medium rounded-lg transition-colors flex items-center"
                        title="Export Shards"
                      >
                        <Download className="w-3 h-3 sm:w-3.5 sm:h-3.5 mr-1 sm:mr-1.5" /> Export
                      </button>
                      <button
                        onClick={() => importFileRef.current?.click()}
                        className="px-2 sm:px-3 py-1 sm:py-1.5 bg-slate-800 hover:bg-slate-700 text-white text-[10px] sm:text-xs font-medium rounded-lg transition-colors flex items-center"
                        title="Import Shards"
                      >
                        <Upload className="w-3 h-3 sm:w-3.5 sm:h-3.5 mr-1 sm:mr-1.5" /> Import
                      </button>
                      <input type="file" ref={importFileRef} onChange={onImportShards} accept=".json" className="hidden" />
                      <button
                        onClick={onShardDirectives}
                        disabled={isSharding || directiveShards.length > 0}
                        className="px-2 sm:px-3 py-1 sm:py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-[10px] sm:text-xs font-medium rounded-lg transition-colors flex items-center"
                      >
                        {isSharding ? (
                          <><Loader2 className="w-3 h-3 sm:w-3.5 sm:h-3.5 mr-1 sm:mr-1.5 animate-spin" /> Sharding...</>
                        ) : directiveShards.length > 0 ? (
                          <><ShieldCheck className="w-3 h-3 sm:w-3.5 sm:h-3.5 mr-1 sm:mr-1.5" /> Sharded</>
                        ) : (
                          <><Database className="w-3 h-3 sm:w-3.5 sm:h-3.5 mr-1 sm:mr-1.5" /> Shard</>
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Technical Details (collapsible shard info) */}
                  {directiveShards.length > 0 && (
                    <div className="mt-4">
                      <button
                        onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                        className="flex items-center space-x-2 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                      >
                        {showTechnicalDetails ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        <span>Technical Details ({directiveShards.length} shards)</span>
                      </button>
                      {showTechnicalDetails && (
                        <div className="mt-2 space-y-2 border-t border-emerald-500/20 pt-4 animate-in fade-in slide-in-from-top-2 duration-200">
                          <p className="text-xs text-slate-400 mb-2">Shards generated and ready for decentralized storage:</p>
                          {directiveShards.map((shard) => (
                            <div key={shard.id} className="p-2 bg-[#111] border border-slate-800 rounded flex items-center justify-between">
                              <div className="flex items-center">
                                <Database className="w-3 h-3 text-emerald-500 mr-2" />
                                <span className="text-xs font-mono text-slate-300">{shard.id}</span>
                              </div>
                              <span className="text-xs font-mono text-emerald-400/70">{shard.hash}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="h-full min-h-[300px] flex items-center justify-center text-slate-500">
                <p>Waiting for initial telemetry analysis...</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
