import { Loader2 } from 'lucide-react';

export function LoadingFallback({ message = 'Loading data...' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 space-y-4">
      <Loader2 className="w-10 h-10 text-emerald-500 animate-spin" />
      <p className="text-slate-400 text-sm animate-pulse">{message}</p>
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="bg-[#111] border border-slate-800 rounded-xl p-5 animate-pulse">
      <div className="flex justify-between items-start mb-4">
        <div className="w-10 h-10 rounded-lg bg-slate-800" />
        <div className="w-16 h-5 rounded-full bg-slate-800" />
      </div>
      <div className="w-20 h-3 rounded bg-slate-800 mb-2" />
      <div className="w-24 h-8 rounded bg-slate-800" />
    </div>
  );
}

export function SkeletonChart() {
  return (
    <div className="bg-[#111] border border-slate-800 rounded-xl p-6 animate-pulse">
      <div className="flex justify-between items-center mb-6">
        <div className="w-48 h-5 rounded bg-slate-800" />
        <div className="w-24 h-6 rounded bg-slate-800" />
      </div>
      <div className="h-64 bg-slate-800/50 rounded-lg" />
    </div>
  );
}
