import { ShieldCheck, AlertTriangle, Activity, Terminal } from 'lucide-react';
import type { RiskLevel, RiskColorConfig } from '../../types/risk';

export function getRiskColor(level: RiskLevel | string | null): RiskColorConfig {
  switch(level) {
    case 'Green': return { bg: 'bg-emerald-950/80', text: 'text-emerald-400', border: 'border-emerald-500/60 shadow-[0_0_15px_rgba(16,185,129,0.15)]', label: 'LOW RISK' };
    case 'Amber': return { bg: 'bg-amber-950/80', text: 'text-amber-400', border: 'border-amber-500/60 shadow-[0_0_15px_rgba(245,158,11,0.15)]', label: 'ELEVATED RISK' };
    case 'Red': return { bg: 'bg-rose-950/80', text: 'text-rose-400', border: 'border-rose-500/60 shadow-[0_0_15px_rgba(244,63,94,0.15)]', label: 'HIGH RISK' };
    case 'Black': return { bg: 'bg-black', text: 'text-red-500', border: 'border-red-600 shadow-[0_0_20px_rgba(220,38,38,0.3)]', label: 'FULL SHUTDOWN' };
    default: return { bg: 'bg-slate-800/80', text: 'text-slate-400', border: 'border-slate-700', label: 'ANALYZING...' };
  }
}

export function getRiskIcon(level: RiskLevel | string | null) {
  switch(level) {
    case 'Green': return <ShieldCheck className="w-5 h-5 mr-2" />;
    case 'Amber': return <AlertTriangle className="w-5 h-5 mr-2" />;
    case 'Red': return <Activity className="w-5 h-5 mr-2" />;
    case 'Black': return <Terminal className="w-5 h-5 mr-2" />;
    default: return <ShieldCheck className="w-5 h-5 mr-2" />;
  }
}

export function getRiskDescription(level: RiskLevel | string | null): string {
  switch(level) {
    case 'Green': return 'Conditions are safe. Normal operations can continue.';
    case 'Amber': return 'Some risks detected. Take precautions and monitor conditions.';
    case 'Red': return 'Dangerous conditions. Stop non-essential outdoor work immediately.';
    case 'Black': return 'Extreme danger. Full site shutdown required. Evacuate if necessary.';
    default: return 'Analyzing current conditions...';
  }
}

interface RiskBadgeProps {
  level: RiskLevel | string | null;
  showDescription?: boolean;
  className?: string;
}

export function RiskBadge({ level, showDescription = false, className = '' }: RiskBadgeProps) {
  const color = getRiskColor(level);
  return (
    <div className={className}>
      <div className={`flex items-center px-3 py-1.5 rounded-lg border ${color.bg} ${color.border} ${color.text}`}>
        {getRiskIcon(level)}
        <span className="text-sm font-bold tracking-wider">{color.label}</span>
      </div>
      {showDescription && (
        <p className="text-xs text-slate-400 mt-1.5">{getRiskDescription(level)}</p>
      )}
    </div>
  );
}
