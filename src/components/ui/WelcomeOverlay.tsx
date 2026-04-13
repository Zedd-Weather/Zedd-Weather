import { useState } from 'react';
import { Cloud, MapPin, ShieldCheck, ChevronRight } from 'lucide-react';
import type { SectorId } from '../../types/risk';

const SECTOR_OPTIONS: { id: SectorId; label: string; icon: string; description: string }[] = [
  { id: 'construction', label: 'Construction', icon: '🏗️', description: 'Building sites, heavy machinery, structural work' },
  { id: 'agricultural', label: 'Agricultural', icon: '🌾', description: 'Farms, plantations, crop management' },
  { id: 'industrial', label: 'Industrial', icon: '🏭', description: 'Manufacturing plants, warehouses, refineries' },
];

interface WelcomeOverlayProps {
  onComplete: (sector: SectorId) => void;
}

export function WelcomeOverlay({ onComplete }: WelcomeOverlayProps) {
  const [step, setStep] = useState(0);
  const [selectedSector, setSelectedSector] = useState<SectorId>('construction');

  if (step === 0) {
    return (
      <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90 backdrop-blur-md p-4">
        <div className="bg-[#111] border border-slate-800 rounded-2xl w-full max-w-lg p-8 text-center">
          <div className="w-16 h-16 rounded-2xl bg-emerald-500/20 border border-emerald-500/50 flex items-center justify-center mx-auto mb-6">
            <Cloud className="w-8 h-8 text-emerald-400" />
          </div>
          <h1 className="text-2xl font-bold text-slate-100 mb-3">Welcome to Zedd Weather</h1>
          <p className="text-slate-400 text-sm leading-relaxed mb-8">
            Zedd Weather monitors your site&apos;s weather conditions in real time and alerts you
            to safety risks. It works with sensors on-site or live weather data from the internet.
          </p>
          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
              <Cloud className="w-5 h-5 text-blue-400 mx-auto mb-2" />
              <p className="text-xs text-slate-400">Live weather tracking</p>
            </div>
            <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
              <ShieldCheck className="w-5 h-5 text-emerald-400 mx-auto mb-2" />
              <p className="text-xs text-slate-400">AI safety analysis</p>
            </div>
            <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
              <MapPin className="w-5 h-5 text-amber-400 mx-auto mb-2" />
              <p className="text-xs text-slate-400">Location-aware alerts</p>
            </div>
          </div>
          <button
            onClick={() => setStep(1)}
            className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg transition-colors flex items-center justify-center"
          >
            Get Started
            <ChevronRight className="w-4 h-4 ml-2" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90 backdrop-blur-md p-4">
      <div className="bg-[#111] border border-slate-800 rounded-2xl w-full max-w-lg p-8">
        <h2 className="text-xl font-bold text-slate-100 mb-2">What type of site do you manage?</h2>
        <p className="text-slate-400 text-sm mb-6">
          This helps us tailor risk analysis and alerts to your industry.
        </p>
        <div className="space-y-3 mb-8">
          {SECTOR_OPTIONS.map((option) => (
            <button
              key={option.id}
              onClick={() => setSelectedSector(option.id)}
              className={`w-full p-4 rounded-xl border text-left transition-all flex items-start space-x-4 ${
                selectedSector === option.id
                  ? 'bg-emerald-500/10 border-emerald-500/50 ring-1 ring-emerald-500/30'
                  : 'bg-slate-900 border-slate-800 hover:border-slate-700'
              }`}
            >
              <span className="text-2xl">{option.icon}</span>
              <div>
                <p className={`font-medium ${selectedSector === option.id ? 'text-emerald-400' : 'text-slate-200'}`}>
                  {option.label}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">{option.description}</p>
              </div>
            </button>
          ))}
        </div>
        <button
          onClick={() => {
            localStorage.setItem('zedd_onboarded', 'true');
            localStorage.setItem('zedd_default_sector', selectedSector);
            onComplete(selectedSector);
          }}
          className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg transition-colors flex items-center justify-center"
        >
          Start Monitoring
          <ChevronRight className="w-4 h-4 ml-2" />
        </button>
      </div>
    </div>
  );
}
