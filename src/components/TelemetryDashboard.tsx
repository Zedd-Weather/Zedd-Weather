import { useState } from 'react';
import {
  Thermometer,
  Droplets,
  Wind,
  ShieldCheck,
  Activity,
  Server,
  CloudRain,
  Waves,
  Sun,
  Loader2,
  Download,
  Database,
  Cpu,
  Terminal,
  ChevronDown,
  ChevronUp,
  RefreshCw,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  ComposedChart,
  Bar,
} from 'recharts';
import type { TelemetryData, HourlyWeatherPoint, HistoricalDataPoint, Attestation, NodeInfo, ExportMetrics } from '../types/telemetry';
import { MetricCard } from './ui/MetricCard';
import { Modal } from './ui/Modal';
import { SkeletonCard, SkeletonChart } from './ui/LoadingFallback';

interface TelemetryDashboardProps {
  currentTelemetry: TelemetryData;
  telemetrySource: 'onboard' | 'external';
  setTelemetrySource: (source: 'onboard' | 'external') => void;
  hourlyWeatherData: HourlyWeatherPoint[];
  historicalData: HistoricalDataPoint[];
  historicalRange: '7d' | '14d' | '30d';
  setHistoricalRange: (range: '7d' | '14d' | '30d') => void;
  isFetchingHistory: boolean;
  lastUpdated: number | null;
  onRefresh: () => void;
}

const NODES: NodeInfo[] = [
  { id: 'Node A', role: 'Control Plane + Storage', status: 'Active', ip: '10.0.0.14', detail: 'InfluxDB, Grafana, Open WebUI' },
  { id: 'Node B', role: 'AI Worker', status: 'Active', ip: '10.0.0.15', detail: 'Orchestration + AI Inference' },
  { id: 'Node C', role: 'Sensory Worker', status: 'Active', ip: '10.0.0.16', detail: 'Telemetry Publisher (MQTT)' },
];

function formatTimeAgo(ts: number | null): string {
  if (!ts) return 'never';
  const seconds = Math.floor((Date.now() - ts) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.floor(minutes / 60)}h ago`;
}

export default function TelemetryDashboard({
  currentTelemetry,
  telemetrySource,
  setTelemetrySource,
  hourlyWeatherData,
  historicalData,
  historicalRange,
  setHistoricalRange,
  isFetchingHistory,
  lastUpdated,
  onRefresh,
}: TelemetryDashboardProps) {
  const [showAdvancedSystem, setShowAdvancedSystem] = useState(false);
  const [showAdvancedProofs, setShowAdvancedProofs] = useState(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [exportMetrics, setExportMetrics] = useState<ExportMetrics>({
    temp: true,
    humidity: true,
    pressure: true,
    precipitation: true,
  });

  const [attestations, setAttestations] = useState<Attestation[]>([]);
  const [isGeneratingProof, setIsGeneratingProof] = useState(false);
  const [isLedgerOpen, setIsLedgerOpen] = useState(false);

  const generateZeddProof = async () => {
    setIsGeneratingProof(true);
    const dataString = JSON.stringify(currentTelemetry) + Date.now();
    const data = new TextEncoder().encode(dataString);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hexHash = '0x' + hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
    setAttestations((prev) => [
      { id: hexHash, time: 'Just now', type: 'Manual Shard', verified: true },
      ...prev.slice(0, 3),
    ]);
    setIsGeneratingProof(false);
  };

  const exportHistoricalToCSV = () => {
    if (historicalData.length === 0) return;
    const headers = ['Time'];
    if (exportMetrics.temp) headers.push('Temperature (°C)');
    if (exportMetrics.humidity) headers.push('Humidity (%)');
    if (exportMetrics.pressure) headers.push('Pressure (hPa)');
    if (exportMetrics.precipitation) headers.push('Precipitation Prob. (%)');

    const rows = historicalData.map((d) => {
      const row: (string | number)[] = [d.time];
      if (exportMetrics.temp) row.push(d.temp);
      if (exportMetrics.humidity) row.push(d.humidity);
      if (exportMetrics.pressure) row.push(d.pressure);
      if (exportMetrics.precipitation) row.push(d.precipitation || 0);
      return row.join(',');
    });

    const csvContent = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `telemetry_export_${historicalRange}_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    setIsExportModalOpen(false);
  };

  return (
    <>
      {/* Header row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 space-y-4 sm:space-y-0">
        <div className="flex items-center space-x-3">
          <h2 className="text-lg sm:text-xl font-semibold text-slate-200">Current Readings</h2>
          <span className="text-xs text-slate-500">
            Updated {formatTimeAgo(lastUpdated)}
          </span>
          <button
            onClick={onRefresh}
            className="p-1.5 rounded-lg border border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
            title="Refresh data"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="flex bg-slate-900 rounded-lg p-1 border border-slate-800 self-start sm:self-auto">
          <button
            onClick={() => setTelemetrySource('onboard')}
            className={`px-3 sm:px-4 py-1 sm:py-1.5 text-[10px] sm:text-xs font-medium rounded-md transition-all ${
              telemetrySource === 'onboard'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Local Sensors
          </button>
          <button
            onClick={() => setTelemetrySource('external')}
            className={`px-3 sm:px-4 py-1 sm:py-1.5 text-[10px] sm:text-xs font-medium rounded-md transition-all ${
              telemetrySource === 'external'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Weather API
          </button>
        </div>
      </div>

      {/* Primary metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6 mb-4">
        <MetricCard title="Temperature" value={currentTelemetry.temp.toFixed(1)} unit="°C" icon={Thermometer} type="temp" />
        <MetricCard title="Humidity" value={currentTelemetry.humidity.toFixed(1)} unit="%" icon={Droplets} type="humidity" />
        <MetricCard title="Wind & Pressure" value={currentTelemetry.pressure.toFixed(1)} unit="hPa" icon={Wind} type="pressure" />
        <MetricCard title="Air Quality" value={Math.round(currentTelemetry.aqi)} unit="AQI" icon={Activity} type="aqi" />
      </div>

      {/* Secondary metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 mb-8">
        <MetricCard title="Rain Chance" value={currentTelemetry.precipitation.toFixed(0)} unit="%" icon={CloudRain} type="precip" showDescription={false} />
        <MetricCard title="Tide Level" value={currentTelemetry.tide.toFixed(2)} unit="m" icon={Waves} type="tide" showDescription={false} />
        <MetricCard title="UV Index" value={currentTelemetry.uvIndex.toFixed(1)} unit="" icon={Sun} type="uv" showDescription={false} />
        <MetricCard title="ZeddProofs" value="1,402" unit="" icon={ShieldCheck} type="proofs" showDescription={false} />
      </div>

      {/* Charts section */}
      <div className="space-y-8 mb-8">
        {/* Historical Trends */}
        <div className="bg-[#111] border border-slate-800 rounded-xl p-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 space-y-4 sm:space-y-0">
            <h2 className="text-base sm:text-lg font-medium flex items-center text-slate-200">
              <Activity className="w-4 h-4 sm:w-5 sm:h-5 mr-2 text-rose-400" />
              Historical Telemetry Trends
            </h2>
            <div className="flex items-center space-x-2 sm:space-x-4">
              <button
                onClick={() => setIsExportModalOpen(true)}
                disabled={isFetchingHistory || historicalData.length === 0}
                className="px-2 sm:px-3 py-1 sm:py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white text-[10px] sm:text-xs font-medium rounded-lg transition-colors flex items-center"
                title="Export CSV"
              >
                <Download className="w-3 h-3 sm:w-3.5 sm:h-3.5 mr-1 sm:mr-1.5" />
                <span className="hidden xs:inline">Export CSV</span>
              </button>
              <div className="flex space-x-1 sm:space-x-2">
                {(['7d', '14d', '30d'] as const).map((range) => (
                  <button
                    key={range}
                    onClick={() => setHistoricalRange(range)}
                    className={`px-2 sm:px-3 py-0.5 sm:py-1 text-[10px] sm:text-xs font-medium rounded-lg border transition-colors ${
                      historicalRange === range
                        ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400'
                        : 'bg-slate-800 border-slate-700 text-slate-400 hover:bg-slate-700 hover:text-slate-300'
                    }`}
                  >
                    {range.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {isFetchingHistory ? (
            <div className="h-64 flex items-center justify-center">
              <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={historicalData}>
                  <defs>
                    <linearGradient id="colorTempHist" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorHumidHist" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
                  <XAxis dataKey="time" stroke="#666" fontSize={10} tickLine={false} axisLine={false} minTickGap={30} />
                  <YAxis yAxisId="left" stroke="#666" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis yAxisId="right" orientation="right" stroke="#666" fontSize={10} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#000', borderColor: '#333', color: '#fff' }}
                    itemStyle={{ fontSize: '12px' }}
                    labelStyle={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}
                  />
                  <Bar yAxisId="right" dataKey="precipitation" fill="#0ea5e9" opacity={0.5} name="Precip Prob. (%)" />
                  <Area yAxisId="left" type="monotone" dataKey="temp" stroke="#f43f5e" strokeWidth={2} fillOpacity={1} fill="url(#colorTempHist)" name="Temp (°C)" />
                  <Area yAxisId="right" type="monotone" dataKey="humidity" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorHumidHist)" name="Humidity (%)" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* 24h Temperature */}
        <div className="bg-[#111] border border-slate-800 rounded-xl p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-medium flex items-center text-slate-200">
              <Activity className="w-5 h-5 mr-2 text-rose-400" />
              Temperature (24h)
            </h2>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={hourlyWeatherData}>
                <defs>
                  <linearGradient id="colorTemp" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
                <XAxis dataKey="time" stroke="#666" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#666" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#000', borderColor: '#333', color: '#fff' }}
                  itemStyle={{ color: '#f43f5e' }}
                />
                <Area type="monotone" dataKey="temp" stroke="#f43f5e" strokeWidth={2} fillOpacity={1} fill="url(#colorTemp)" name="Temp (°C)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Humidity & Pressure */}
        <div className="bg-[#111] border border-slate-800 rounded-xl p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-medium flex items-center text-slate-200">
              <Droplets className="w-5 h-5 mr-2 text-blue-400" />
              Humidity & Pressure Trends
            </h2>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={hourlyWeatherData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
                <XAxis dataKey="time" stroke="#666" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis yAxisId="left" stroke="#666" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis yAxisId="right" orientation="right" stroke="#666" fontSize={12} tickLine={false} axisLine={false} domain={['dataMin - 5', 'dataMax + 5']} />
                <Tooltip contentStyle={{ backgroundColor: '#000', borderColor: '#333', color: '#fff' }} />
                <Line yAxisId="left" type="monotone" dataKey="humidity" stroke="#3b82f6" strokeWidth={2} dot={false} name="Humidity (%)" />
                <Line yAxisId="right" type="monotone" dataKey="pressure" stroke="#64748b" strokeWidth={2} dot={false} name="Pressure (hPa)" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Advanced: System Details (collapsible) */}
      <div className="mb-8">
        <button
          onClick={() => setShowAdvancedSystem(!showAdvancedSystem)}
          className="flex items-center space-x-2 text-sm font-medium text-slate-400 hover:text-slate-200 transition-colors mb-4"
        >
          {showAdvancedSystem ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          <span>Advanced: System Details</span>
        </button>
        {showAdvancedSystem && (
          <div className="bg-[#111] border border-slate-800 rounded-xl p-6 animate-in fade-in slide-in-from-top-2 duration-200">
            <h2 className="text-lg font-medium flex items-center mb-6 text-slate-200">
              <Server className="w-5 h-5 mr-2 text-indigo-400" />
              System Architecture
            </h2>
            <div className="space-y-4">
              {NODES.map((node) => (
                <div key={node.id} className="p-4 rounded-lg bg-[#1a1a1a] border border-slate-800">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <p className="font-medium text-slate-200">{node.id}</p>
                      <p className="text-xs text-slate-400">{node.role}</p>
                    </div>
                    <span className="px-2 py-1 text-[10px] uppercase tracking-wider font-semibold bg-emerald-500/10 text-emerald-400 rounded-full">
                      {node.status}
                    </span>
                  </div>
                  <div className="mt-3 pt-3 border-t border-slate-800/50 flex items-center text-xs text-slate-400">
                    <Cpu className="w-3 h-3 mr-1.5" />
                    {node.detail}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Advanced: Attestation Details (collapsible) */}
      <div className="mb-8">
        <button
          onClick={() => setShowAdvancedProofs(!showAdvancedProofs)}
          className="flex items-center space-x-2 text-sm font-medium text-slate-400 hover:text-slate-200 transition-colors mb-4"
        >
          {showAdvancedProofs ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          <span>Advanced: Attestation Details</span>
        </button>
        {showAdvancedProofs && (
          <div className="bg-[#111] border border-slate-800 rounded-xl p-6 animate-in fade-in slide-in-from-top-2 duration-200">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-medium flex items-center text-slate-200">
                <Database className="w-5 h-5 mr-2 text-emerald-400" />
                Recent ZeddProofs
              </h2>
              <button
                onClick={generateZeddProof}
                disabled={isGeneratingProof}
                className="px-3 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-medium rounded-lg border border-emerald-500/30 transition-colors flex items-center disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isGeneratingProof ? (
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <ShieldCheck className="w-3.5 h-3.5 mr-1.5" />
                )}
                {isGeneratingProof ? 'Attesting...' : 'Attest Now'}
              </button>
            </div>
            <div className="space-y-3">
              {attestations.map((att, i) => (
                <div key={i} className="p-3 rounded-lg bg-[#1a1a1a] border border-slate-800 flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-slate-900 rounded-md border border-slate-800">
                      <Terminal className="w-4 h-4 text-emerald-500" />
                    </div>
                    <div>
                      <p className="text-sm font-mono text-slate-300">{att.id}</p>
                      <p className="text-xs text-slate-500">{att.type} • {att.time}</p>
                    </div>
                  </div>
                  {att.verified && <ShieldCheck className="w-4 h-4 text-emerald-500" />}
                </div>
              ))}
            </div>
            <button
              onClick={() => setIsLedgerOpen(true)}
              className="w-full mt-4 py-2 text-sm text-slate-400 hover:text-slate-200 border border-slate-800 rounded-lg hover:bg-slate-800/50 transition-colors"
            >
              View Full Ledger
            </button>
          </div>
        )}
      </div>

      {/* Ledger Modal */}
      <Modal
        isOpen={isLedgerOpen}
        onClose={() => setIsLedgerOpen(false)}
        title="Full ZeddProof Ledger"
        icon={<Database className="w-4 h-4 sm:w-5 sm:h-5 mr-2 text-emerald-400" />}
      >
        <div className="p-3 sm:p-6 overflow-y-auto flex-1 space-y-2 sm:space-y-3">
          {attestations.length === 0 ? (
            <div className="py-8 text-center">
              <ShieldCheck className="w-8 h-8 text-slate-600 mx-auto mb-3" />
              <p className="text-sm text-slate-500">No attestations yet. Generate a ZeddProof to populate the ledger.</p>
            </div>
          ) : (
            attestations.map((att, i) => (
              <div key={i} className="p-3 sm:p-4 rounded-lg bg-[#1a1a1a] border border-slate-800 flex items-center justify-between">
                <div className="flex items-center space-x-3 sm:space-x-4">
                  <div className="p-2 sm:p-3 bg-slate-900 rounded-md border border-slate-800">
                    <Terminal className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-500" />
                  </div>
                  <div>
                    <p className="text-xs sm:text-sm font-mono text-slate-300 break-all">
                      {att.id.slice(0, 26)}...{att.id.slice(-8)}
                    </p>
                    <p className="text-[10px] sm:text-xs text-slate-500 mt-1">{att.type} • {att.time}</p>
                  </div>
                </div>
                <div className="flex items-center space-x-1 sm:space-x-2 text-emerald-500 text-[10px] sm:text-sm font-medium">
                  <ShieldCheck className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                  <span className="hidden xs:inline">Verified</span>
                </div>
              </div>
            ))
          )}
        </div>
      </Modal>

      {/* Export Modal */}
      <Modal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        title="Export Historical Data"
        icon={<Download className="w-4 h-4 sm:w-5 sm:h-5 mr-2 text-emerald-400" />}
        maxWidth="max-w-md"
      >
        <div className="p-4 sm:p-6 space-y-4 sm:space-y-6">
          <div>
            <h3 className="text-xs sm:text-sm font-medium text-slate-300 mb-3">Select Metrics to Export</h3>
            <div className="space-y-2 sm:space-y-3">
              <label className="flex items-center space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={exportMetrics.temp}
                  onChange={(e) => setExportMetrics((prev) => ({ ...prev, temp: e.target.checked }))}
                  className="form-checkbox h-4 w-4 text-emerald-500 rounded border-slate-700 bg-slate-900 focus:ring-emerald-500 focus:ring-offset-slate-900"
                />
                <span className="text-xs sm:text-sm text-slate-400 flex items-center">
                  <Thermometer className="w-4 h-4 mr-2 text-rose-400" /> Temperature
                </span>
              </label>
              <label className="flex items-center space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={exportMetrics.humidity}
                  onChange={(e) => setExportMetrics((prev) => ({ ...prev, humidity: e.target.checked }))}
                  className="form-checkbox h-4 w-4 text-emerald-500 rounded border-slate-700 bg-slate-900 focus:ring-emerald-500 focus:ring-offset-slate-900"
                />
                <span className="text-xs sm:text-sm text-slate-400 flex items-center">
                  <Droplets className="w-4 h-4 mr-2 text-blue-400" /> Humidity
                </span>
              </label>
              <label className="flex items-center space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={exportMetrics.pressure}
                  onChange={(e) => setExportMetrics((prev) => ({ ...prev, pressure: e.target.checked }))}
                  className="form-checkbox h-4 w-4 text-emerald-500 rounded border-slate-700 bg-slate-900 focus:ring-emerald-500 focus:ring-offset-slate-900"
                />
                <span className="text-xs sm:text-sm text-slate-400 flex items-center">
                  <Wind className="w-4 h-4 mr-2 text-slate-400" /> Pressure
                </span>
              </label>
              <label className="flex items-center space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={exportMetrics.precipitation}
                  onChange={(e) => setExportMetrics((prev) => ({ ...prev, precipitation: e.target.checked }))}
                  className="form-checkbox h-4 w-4 text-emerald-500 rounded border-slate-700 bg-slate-900 focus:ring-emerald-500 focus:ring-offset-slate-900"
                />
                <span className="text-xs sm:text-sm text-slate-400 flex items-center">
                  <CloudRain className="w-4 h-4 mr-2 text-blue-300" /> Precipitation
                </span>
              </label>
            </div>
          </div>
          <div className="bg-slate-900/50 p-3 sm:p-4 rounded-lg border border-slate-800">
            <p className="text-[10px] sm:text-xs text-slate-400">
              Exporting data for the selected range: <strong className="text-emerald-400">{historicalRange.toUpperCase()}</strong>.
              The CSV will include {historicalData.length} data points.
            </p>
          </div>
        </div>
        <div className="p-4 sm:p-6 border-t border-slate-800 flex justify-end space-x-3">
          <button
            onClick={() => setIsExportModalOpen(false)}
            className="px-3 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-slate-300 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={exportHistoricalToCSV}
            disabled={!exportMetrics.temp && !exportMetrics.humidity && !exportMetrics.pressure && !exportMetrics.precipitation}
            className="px-3 sm:px-4 py-1.5 sm:py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs sm:text-sm font-medium rounded-lg transition-colors flex items-center"
          >
            <Download className="w-3.5 h-3.5 sm:w-4 sm:h-4 mr-1.5 sm:mr-2" />
            Download CSV
          </button>
        </div>
      </Modal>
    </>
  );
}
