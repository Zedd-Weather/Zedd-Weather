import type { LucideIcon } from 'lucide-react';

export function getMetricStatus(type: string, value: number) {
  switch(type) {
    case 'temp':
      if (value > 35 || value < 0) return { label: 'Critical', color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/30' };
      if (value > 30 || value < 5) return { label: 'Warning', color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30' };
      return { label: 'Normal', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' };
    case 'aqi':
      if (value > 150) return { label: 'Hazardous', color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/30' };
      if (value > 100) return { label: 'Unhealthy', color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/30' };
      if (value > 50) return { label: 'Moderate', color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30' };
      return { label: 'Good', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' };
    case 'uv':
      if (value > 8) return { label: 'Extreme', color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/30' };
      if (value > 5) return { label: 'High', color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30' };
      return { label: 'Low', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' };
    case 'precip':
      if (value > 50) return { label: 'High Prob', color: 'text-blue-500', bg: 'bg-blue-500/10', border: 'border-blue-500/30' };
      if (value > 20) return { label: 'Possible', color: 'text-blue-400', bg: 'bg-blue-400/10', border: 'border-blue-400/30' };
      return { label: 'Clear', color: 'text-slate-400', bg: 'bg-slate-500/10', border: 'border-slate-800' };
    case 'pressure':
      if (value < 990) return { label: 'Low (Storm)', color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30' };
      if (value > 1030) return { label: 'High (Clear)', color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/30' };
      return { label: 'Stable', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' };
    case 'humidity':
      if (value > 80) return { label: 'Humid', color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/30' };
      if (value < 30) return { label: 'Dry', color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30' };
      return { label: 'Comfortable', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' };
    case 'tide':
      if (value > 2.5) return { label: 'High Tide', color: 'text-cyan-400', bg: 'bg-cyan-500/10', border: 'border-cyan-500/30' };
      return { label: 'Normal', color: 'text-cyan-500', bg: 'bg-cyan-500/10', border: 'border-cyan-500/30' };
    case 'proofs':
      return { label: 'Secured', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' };
    default:
      return { label: 'Active', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' };
  }
}

export function getMetricDescription(type: string, value: number): string {
  switch(type) {
    case 'temp':
      if (value > 35) return `It's dangerously hot at ${value.toFixed(1)}°C — limit outdoor work`;
      if (value > 30) return `It's quite warm at ${value.toFixed(1)}°C — stay hydrated`;
      if (value < 0) return `Freezing conditions at ${value.toFixed(1)}°C — take frost precautions`;
      if (value < 5) return `It's cold at ${value.toFixed(1)}°C — wear warm clothing`;
      return `Temperature is comfortable at ${value.toFixed(1)}°C`;
    case 'humidity':
      if (value > 80) return `Very humid at ${value.toFixed(0)}% — equipment may corrode faster`;
      if (value < 30) return `Air is very dry at ${value.toFixed(0)}% — fire risk increased`;
      return `Humidity is comfortable at ${value.toFixed(0)}%`;
    case 'aqi':
      if (value > 150) return `Air quality is hazardous (AQI ${Math.round(value)}) — wear respiratory protection`;
      if (value > 100) return `Air quality is unhealthy (AQI ${Math.round(value)}) — sensitive workers should limit exposure`;
      if (value > 50) return `Air quality is moderate (AQI ${Math.round(value)})`;
      return `Air quality is good (AQI ${Math.round(value)})`;
    case 'uv':
      if (value > 8) return `Extreme UV (${value.toFixed(1)}) — avoid prolonged sun exposure`;
      if (value > 5) return `High UV (${value.toFixed(1)}) — apply sunscreen and wear hats`;
      return `Low UV (${value.toFixed(1)}) — sun protection optional`;
    case 'precip':
      if (value > 50) return `${value.toFixed(0)}% chance of rain — plan for wet conditions`;
      if (value > 20) return `${value.toFixed(0)}% chance of rain — keep covers ready`;
      return `${value.toFixed(0)}% chance of rain — clear skies expected`;
    case 'pressure':
      if (value < 990) return `Low pressure (${value.toFixed(0)} hPa) — storm conditions possible`;
      if (value > 1030) return `High pressure (${value.toFixed(0)} hPa) — clear weather expected`;
      return `Stable pressure at ${value.toFixed(0)} hPa`;
    default:
      return '';
  }
}

interface MetricCardProps {
  title: string;
  value: string | number;
  unit: string;
  icon: LucideIcon;
  type: string;
  showDescription?: boolean;
}

export function MetricCard({ title, value, unit, icon: Icon, type, showDescription = true }: MetricCardProps) {
  const parsed = typeof value === 'string' ? parseFloat(value.replace(/,/g, '')) : Number(value);
  const numValue = Number.isFinite(parsed) ? parsed : 0;
  const statusInfo = getMetricStatus(type, numValue);
  const description = getMetricDescription(type, numValue);
  const isCritical = statusInfo.label === 'Critical' || statusInfo.label === 'Hazardous' || statusInfo.label === 'Extreme';

  return (
    <div className={`bg-[#111] border ${statusInfo.border} rounded-xl p-3 sm:p-5 flex flex-col relative overflow-hidden transition-all duration-300 hover:bg-[#161616] shadow-sm ${isCritical ? 'ring-1 ring-rose-500/50 animate-pulse' : ''}`}>
      {isCritical && (
        <div className="absolute top-0 right-0 w-10 h-10 sm:w-12 sm:h-12 -mr-5 -mt-5 sm:-mr-6 sm:-mt-6 bg-rose-500/20 blur-xl rounded-full" />
      )}
      <div className="flex justify-between items-start mb-2 sm:mb-4">
        <div className={`p-1.5 sm:p-2.5 rounded-lg ${statusInfo.bg} ${statusInfo.color}`}>
          <Icon className="w-4 h-4 sm:w-5 sm:h-5" />
        </div>
        <span className={`text-[8px] sm:text-[10px] uppercase tracking-wider font-bold px-1.5 sm:px-2.5 py-0.5 sm:py-1 rounded-full ${statusInfo.bg} ${statusInfo.color}`}>
          {statusInfo.label}
        </span>
      </div>
      <div>
        <p className="text-xs sm:text-sm text-slate-400 font-medium mb-0.5 sm:mb-1">{title}</p>
        <div className="flex items-baseline space-x-1">
          <p className="text-xl sm:text-3xl font-bold text-slate-100 tracking-tight">{value}</p>
          <span className="text-[10px] sm:text-sm text-slate-500 font-medium">{unit}</span>
        </div>
        {showDescription && description && (
          <p className="text-xs text-slate-500 mt-1.5 leading-relaxed hidden sm:block">{description}</p>
        )}
      </div>
    </div>
  );
}
