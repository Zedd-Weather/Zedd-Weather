/**
 * WeatherCard.jsx
 *
 * Replaces raw weather data display with "Risk Summaries" and
 * "Mitigation Controls" for the construction decision pipeline.
 */
import { useState, useMemo } from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  Activity,
  Wind,
  Thermometer,
  Droplets,
  Sun,
  Eye,
  CloudRain,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

/**
 * Status badge colours.
 */
const STATUS_STYLES = {
  Green: {
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/40',
    text: 'text-emerald-400',
    label: 'LOW RISK',
    Icon: ShieldCheck,
  },
  Amber: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/40',
    text: 'text-amber-400',
    label: 'ELEVATED',
    Icon: AlertTriangle,
  },
  Red: {
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/40',
    text: 'text-rose-400',
    label: 'HIGH RISK',
    Icon: Activity,
  },
};

/**
 * Single hazard row inside the risk summary panel.
 */
function HazardRow({ icon: Icon, label, value, unit, status }) {
  const colour =
    status === 'halt'
      ? 'text-rose-400'
      : status === 'caution'
        ? 'text-amber-400'
        : 'text-emerald-400';

  return (
    <div className="flex items-center justify-between py-1.5 border-b border-slate-800/60 last:border-0">
      <div className="flex items-center gap-2">
        <Icon className={`w-4 h-4 ${colour}`} />
        <span className="text-xs text-slate-300">{label}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className={`text-sm font-semibold ${colour}`}>{value}</span>
        <span className="text-[10px] text-slate-500">{unit}</span>
      </div>
    </div>
  );
}

/**
 * WeatherCard with Risk Summaries + Mitigation Controls.
 *
 * @param {{ weather: Object, decision: Object|null, constraints: Object|null }} props
 */
export default function WeatherCard({ weather, decision, constraints }) {
  const [expanded, setExpanded] = useState(false);

  const status = decision?.status ?? 'Green';
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.Green;

  // Derive per-parameter status from constraints
  const paramStatus = useMemo(() => {
    const halts = (constraints?.haltReasons ?? []).join(' ').toLowerCase();
    const cautions = (constraints?.cautionReasons ?? []).join(' ').toLowerCase();
    const flag = (keyword) =>
      halts.includes(keyword) ? 'halt' : cautions.includes(keyword) ? 'caution' : 'ok';
    return {
      temp: flag('temperature'),
      wind: flag('wind'),
      rain: flag('precipitation') || flag('rain'),
      uv: flag('uv'),
      visibility: flag('visibility'),
      humidity: flag('humidity'),
    };
  }, [constraints]);

  return (
    <div
      className={`rounded-xl border ${style.border} ${style.bg} p-4 transition-all duration-300`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <style.Icon className={`w-5 h-5 ${style.text}`} />
          <h3 className="text-sm font-bold text-slate-100">Site Weather Risk</h3>
        </div>
        <span
          className={`text-[10px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-full ${style.bg} ${style.text} border ${style.border}`}
        >
          {style.label}
        </span>
      </div>

      {/* Risk Summary — key weather parameters */}
      <div className="space-y-0.5">
        <HazardRow
          icon={Thermometer}
          label="Temperature"
          value={(weather?.temperature ?? weather?.temp ?? 0).toFixed(1)}
          unit="°C"
          status={paramStatus.temp}
        />
        <HazardRow
          icon={Wind}
          label="Wind Speed"
          value={(weather?.windSpeed ?? 0).toFixed(1)}
          unit="m/s"
          status={paramStatus.wind}
        />
        <HazardRow
          icon={CloudRain}
          label="Precipitation"
          value={(weather?.precipitation ?? 0).toFixed(1)}
          unit="mm/h"
          status={paramStatus.rain}
        />
        <HazardRow
          icon={Sun}
          label="UV Index"
          value={(weather?.uvIndex ?? 0).toFixed(1)}
          unit=""
          status={paramStatus.uv}
        />
        <HazardRow
          icon={Eye}
          label="Visibility"
          value={Math.round(weather?.visibility ?? 10000)}
          unit="m"
          status={paramStatus.visibility}
        />
        <HazardRow
          icon={Droplets}
          label="Humidity"
          value={(weather?.humidity ?? 0).toFixed(0)}
          unit="%"
          status={paramStatus.humidity}
        />
      </div>

      {/* Mitigation Controls (collapsible) */}
      {decision && (
        <div className="mt-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 transition-colors w-full"
          >
            {expanded ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
            <span>
              Mitigation Controls ({decision.actions?.length ?? 0})
            </span>
          </button>

          {expanded && (
            <div className="mt-2 space-y-1.5 pl-1">
              {decision.actions?.map((action, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 text-xs text-slate-300"
                >
                  <span className="text-emerald-500 font-bold mt-px">
                    {i + 1}.
                  </span>
                  <span>{action}</span>
                </div>
              ))}

              {/* PPE requirements */}
              {constraints?.ppeRequired?.length > 0 && (
                <div className="mt-2 pt-2 border-t border-slate-800/60">
                  <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
                    PPE Required
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {constraints.ppeRequired.map((ppe, i) => (
                      <span
                        key={i}
                        className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700"
                      >
                        {ppe}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Next review */}
              {decision.reviewTime && (
                <p className="text-[10px] text-slate-500 mt-2">
                  Next review:{' '}
                  {new Date(decision.reviewTime).toLocaleTimeString()} (
                  confidence: {((decision.confidence ?? 0) * 100).toFixed(0)}%)
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
