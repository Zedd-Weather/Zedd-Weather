import { useState, useEffect } from 'react';
import {
  Cloud,
  AlertTriangle,
  ShieldCheck,
  Bell,
  BellOff,
  Volume2,
  VolumeX,
  X,
  Activity,
  CalendarDays,
  ChevronDown,
  Map as MapIcon,
  Archive,
} from 'lucide-react';
import { Toaster } from 'sonner';

import { useTelemetry } from './hooks/useTelemetry';
import { useAlerts } from './hooks/useAlerts';
import { useForecast } from './hooks/useForecast';
import { useRiskAnalysis } from './hooks/useRiskAnalysis';
import { useLocker } from './hooks/useLocker';
import { useSiteMap } from './hooks/useSiteMap';

import TelemetryDashboard from './components/TelemetryDashboard';
import RiskAnalysisPanel from './components/RiskAnalysisPanel';
import SiteMapPanel from './components/SiteMapPanel';
import ForecastPanel from './components/ForecastPanel';
import ShardingLocker from './components/ShardingLocker';
import ConstructionDashboard from './components/ConstructionDashboard';
import { WelcomeOverlay } from './components/ui/WelcomeOverlay';
import type { SectorId } from './types/risk';

type TabId = 'weather' | 'safety' | 'forecast' | 'more';
type MoreSubTab = 'locker' | 'sitemap';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('weather');
  const [moreSubTab, setMoreSubTab] = useState<MoreSubTab>('locker');
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const [showConstruction, setShowConstruction] = useState(false);
  const [showWelcome, setShowWelcome] = useState(() => !localStorage.getItem('zedd_onboarded'));

  // ─── Hooks ───
  const telemetry = useTelemetry();
  const alerts = useAlerts(telemetry.currentTelemetry);
  const forecast = useForecast(telemetry.piLocation, activeTab === 'forecast' ? 'forecast' : '');
  const risk = useRiskAnalysis(telemetry.currentTelemetry);
  const locker = useLocker();
  const siteMap = useSiteMap(telemetry.piLocation, telemetry.setPiLocation);

  // Auto-analyze on first telemetry load
  useEffect(() => {
    if (telemetry.lastUpdated && !risk.riskReport && !risk.isAnalyzing) {
      risk.autoAnalyzeRisk(telemetry.currentTelemetry);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [telemetry.lastUpdated]);

  // Refresh telemetry data when switching to the weather tab
  useEffect(() => {
    if (activeTab === 'weather' && telemetry.piLocation) {
      telemetry.fetchRealTelemetry(telemetry.piLocation);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  // ─── Tab definitions ───
  const TABS: { id: TabId; label: string; icon: typeof Activity }[] = [
    { id: 'weather', label: 'Weather Now', icon: Activity },
    { id: 'safety', label: 'Safety Risks', icon: AlertTriangle },
    { id: 'forecast', label: 'Week Ahead', icon: CalendarDays },
    { id: 'more', label: 'More', icon: ChevronDown },
  ];

  // ─── Handlers that bridge hooks ───
  const handleShardDirectives = () => {
    risk.shardDirectives(locker.saveToLocker);
  };

  const handleImportShards = (e: React.ChangeEvent<HTMLInputElement>) => {
    locker.importShards(e, {
      setDirectiveShards: risk.setDirectiveShards,
      setRiskReport: risk.setRiskReport,
      setRiskLevel: risk.setRiskLevel,
      setActiveTab: (tab: string) => setActiveTab(tab as TabId),
    });
  };

  const handleExportShards = () => {
    locker.exportShards(risk.directiveShards);
  };

  const handleLoadLockerEntry = (entry: { shards: any[]; report: string; riskLevel: any }) => {
    risk.setDirectiveShards(entry.shards);
    risk.setRiskReport(entry.report);
    risk.setRiskLevel(entry.riskLevel);
    setActiveTab('safety');
  };

  const handleAnalyzeForecast = async () => {
    risk.setIsAnalyzing(true);
    risk.setRiskReport(null);
    risk.setRiskLevel(null);
    risk.setDirectiveShards([]);
    setActiveTab('safety');
    try {
      const result = await forecast.analyzeForecast(risk.riskSector);
      risk.setRiskLevel(result.riskLevel);
      risk.setRiskReport(result.report);
    } catch {
      risk.setRiskReport('Failed to analyze forecast.');
      risk.setRiskLevel('Amber');
    } finally {
      risk.setIsAnalyzing(false);
    }
  };

  const handleWelcomeComplete = (sector: SectorId) => {
    risk.setRiskSector(sector);
    setShowWelcome(false);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-slate-200 font-sans selection:bg-emerald-500/30">
      <Toaster position="top-right" theme="dark" richColors closeButton />
      {showWelcome && <WelcomeOverlay onComplete={handleWelcomeComplete} />}

      {/* ─── Header ─── */}
      <header className="border-b border-slate-800 bg-[#0a0a0a]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-2 sm:space-x-3">
            <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/50 flex items-center justify-center flex-shrink-0">
              <Cloud className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-400" />
            </div>
            <span className="text-lg sm:text-xl font-bold tracking-tight text-slate-100 truncate">
              Zedd Weather
            </span>
            <span className="hidden xs:inline-block px-2 py-0.5 rounded text-[10px] uppercase tracking-wider font-semibold bg-slate-800 text-slate-400 ml-1 sm:ml-2">
              Enterprise
            </span>
          </div>

          <div className="flex items-center space-x-2 sm:space-x-4">
            {/* Alert controls */}
            <div className="flex items-center space-x-1 sm:space-x-2">
              <button
                onClick={() => alerts.setIsMuted(!alerts.isMuted)}
                className={`p-1.5 sm:p-2 rounded-lg border transition-colors ${
                  alerts.isMuted
                    ? 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
                title={alerts.isMuted ? 'Unmute Alerts' : 'Mute Alerts'}
              >
                {alerts.isMuted ? <VolumeX className="w-3.5 h-3.5 sm:w-4 sm:h-4" /> : <Volume2 className="w-3.5 h-3.5 sm:w-4 sm:h-4" />}
              </button>
              <div className="relative">
                <button
                  onClick={() => alerts.setShowAlerts(!alerts.showAlerts)}
                  className={`p-1.5 sm:p-2 rounded-lg border transition-colors relative ${
                    alerts.activeAlerts.length > 0
                      ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                      : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {alerts.activeAlerts.length > 0 ? (
                    <Bell className="w-3.5 h-3.5 sm:w-4 sm:h-4 animate-pulse" />
                  ) : (
                    <BellOff className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                  )}
                  {alerts.activeAlerts.length > 0 && (
                    <span className="absolute -top-1 -right-1 w-3.5 h-3.5 sm:w-4 sm:h-4 bg-rose-500 text-white text-[9px] sm:text-[10px] font-bold rounded-full flex items-center justify-center border-2 border-[#0a0a0a]">
                      {alerts.activeAlerts.length}
                    </span>
                  )}
                </button>

                {/* Alerts Dropdown */}
                {alerts.showAlerts && (
                  <div className="absolute right-0 mt-2 w-72 sm:w-80 bg-[#111] border border-slate-800 rounded-xl shadow-2xl z-[60] overflow-hidden">
                    <div className="p-3 sm:p-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/50">
                      <h3 className="text-xs sm:text-sm font-bold text-slate-200">Active Alerts</h3>
                      <button onClick={() => alerts.setShowAlerts(false)} className="text-slate-500 hover:text-slate-300">
                        <X className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                      </button>
                    </div>
                    <div className="max-h-80 sm:max-h-96 overflow-y-auto p-2 space-y-2">
                      {alerts.activeAlerts.length === 0 ? (
                        <div className="py-6 sm:py-8 text-center">
                          <ShieldCheck className="w-6 h-6 sm:w-8 sm:h-8 text-emerald-500/30 mx-auto mb-2" />
                          <p className="text-[10px] sm:text-xs text-slate-500">No active alerts. System secure.</p>
                        </div>
                      ) : (
                        alerts.activeAlerts.map((alert) => (
                          <div
                            key={alert.id}
                            className={`p-2 sm:p-3 rounded-lg border flex items-start space-x-2 sm:space-x-3 ${
                              alert.severity === 'critical'
                                ? 'bg-rose-500/10 border-rose-500/30'
                                : 'bg-amber-500/10 border-amber-500/30'
                            }`}
                          >
                            <AlertTriangle
                              className={`w-3.5 h-3.5 sm:w-4 sm:h-4 mt-0.5 flex-shrink-0 ${
                                alert.severity === 'critical' ? 'text-rose-400' : 'text-amber-400'
                              }`}
                            />
                            <div>
                              <p
                                className={`text-[10px] sm:text-xs font-bold uppercase tracking-wider ${
                                  alert.severity === 'critical' ? 'text-rose-400' : 'text-amber-400'
                                }`}
                              >
                                {alert.type}
                              </p>
                              <p className="text-xs sm:text-sm text-slate-200 mt-0.5">{alert.message}</p>
                              <p className="text-[9px] sm:text-[10px] text-slate-500 mt-1">
                                {new Date(alert.timestamp).toLocaleTimeString()}
                              </p>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Connection indicator */}
            <div className="hidden md:flex items-center space-x-2 text-sm text-slate-400 bg-slate-900 px-3 py-1.5 rounded-full border border-slate-800">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Connected</span>
            </div>
            <div className="md:hidden w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="Connected" />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* ─── Tab Navigation ─── */}
        <div className="flex space-x-4 mb-8 border-b border-slate-800 pb-px overflow-x-auto scrollbar-hide">
          {TABS.map((tab) => (
            <div key={tab.id} className="relative">
              <button
                onClick={() => {
                  if (tab.id === 'more') {
                    setShowMoreMenu(!showMoreMenu);
                  } else {
                    setActiveTab(tab.id);
                    setShowMoreMenu(false);
                    setShowConstruction(false);
                  }
                }}
                className={`pb-3 px-2 text-sm font-medium transition-colors border-b-2 whitespace-nowrap flex items-center ${
                  activeTab === tab.id
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-slate-400 hover:text-slate-300'
                }`}
              >
                <tab.icon className="w-4 h-4 mr-2" />
                {tab.label}
              </button>

              {/* More dropdown */}
              {tab.id === 'more' && showMoreMenu && (
                <div className="absolute top-full left-0 mt-1 w-48 bg-[#111] border border-slate-800 rounded-lg shadow-xl z-50 overflow-hidden">
                  <button
                    onClick={() => {
                      setActiveTab('more');
                      setMoreSubTab('locker');
                      setShowMoreMenu(false);
                    }}
                    className="w-full px-4 py-2.5 text-sm text-left text-slate-300 hover:bg-slate-800 flex items-center"
                  >
                    <Archive className="w-4 h-4 mr-2 text-emerald-400" />
                    Sharding Locker
                  </button>
                  <button
                    onClick={() => {
                      setActiveTab('more');
                      setMoreSubTab('sitemap');
                      setShowMoreMenu(false);
                      if (!siteMap.mapReport) siteMap.fetchSiteMapData();
                    }}
                    className="w-full px-4 py-2.5 text-sm text-left text-slate-300 hover:bg-slate-800 flex items-center"
                  >
                    <MapIcon className="w-4 h-4 mr-2 text-blue-400" />
                    Site Map
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Construction toggle on Safety tab */}
        {activeTab === 'safety' && (
          <div className="flex items-center space-x-3 mb-6">
            <div className="flex bg-slate-900 rounded-lg p-1 border border-slate-800">
              <button
                onClick={() => setShowConstruction(false)}
                className={`px-3 sm:px-4 py-1 sm:py-1.5 text-[10px] sm:text-xs font-medium rounded-md transition-all ${
                  !showConstruction ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Risk Analysis
              </button>
              <button
                onClick={() => setShowConstruction(true)}
                className={`px-3 sm:px-4 py-1 sm:py-1.5 text-[10px] sm:text-xs font-medium rounded-md transition-all ${
                  showConstruction ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Construction DSS
              </button>
            </div>
          </div>
        )}

        {/* ─── Tab Content ─── */}

        {activeTab === 'weather' && (
          <TelemetryDashboard
            currentTelemetry={telemetry.currentTelemetry}
            telemetrySource={telemetry.telemetrySource}
            setTelemetrySource={telemetry.setTelemetrySource}
            hourlyWeatherData={telemetry.hourlyWeatherData}
            historicalData={telemetry.historicalData}
            historicalRange={telemetry.historicalRange}
            setHistoricalRange={telemetry.setHistoricalRange}
            isFetchingHistory={telemetry.isFetchingHistory}
            lastUpdated={telemetry.lastUpdated}
            onRefresh={() => telemetry.refreshTelemetry()}
          />
        )}

        {activeTab === 'safety' && !showConstruction && (
          <RiskAnalysisPanel
            currentTelemetry={telemetry.currentTelemetry}
            riskSector={risk.riskSector}
            setRiskSector={risk.setRiskSector}
            isAnalyzing={risk.isAnalyzing}
            riskReport={risk.riskReport}
            riskLevel={risk.riskLevel}
            directiveShards={risk.directiveShards}
            isSharding={risk.isSharding}
            mediaFile={risk.mediaFile}
            mediaPreview={risk.mediaPreview}
            fileInputRef={risk.fileInputRef}
            importFileRef={locker.importFileRef}
            onAutoAnalyze={() => risk.autoAnalyzeRisk(telemetry.currentTelemetry)}
            onAnalyzeMedia={() => risk.analyzeRisk()}
            onShardDirectives={handleShardDirectives}
            onFileChange={risk.handleFileChange}
            onExportShards={handleExportShards}
            onImportShards={handleImportShards}
          />
        )}

        {activeTab === 'safety' && showConstruction && (
          <ConstructionDashboard weather={telemetry.currentTelemetry} />
        )}

        {activeTab === 'forecast' && (
          <ForecastPanel
            piLocation={telemetry.piLocation}
            forecastData={forecast.forecastData}
            isFetchingForecast={forecast.isFetchingForecast}
            isAnalyzing={risk.isAnalyzing}
            onAnalyzeForecast={handleAnalyzeForecast}
          />
        )}

        {activeTab === 'more' && moreSubTab === 'locker' && (
          <ShardingLocker
            lockerEntries={locker.lockerEntries}
            lockerSearch={locker.lockerSearch}
            setLockerSearch={locker.setLockerSearch}
            lockerFilter={locker.lockerFilter}
            setLockerFilter={locker.setLockerFilter}
            expandedLockerId={locker.expandedLockerId}
            setExpandedLockerId={locker.setExpandedLockerId}
            onLoadEntry={handleLoadLockerEntry}
          />
        )}

        {activeTab === 'more' && moreSubTab === 'sitemap' && (
          <SiteMapPanel
            piLocation={telemetry.piLocation}
            isFetchingMap={siteMap.isFetchingMap}
            mapReport={siteMap.mapReport}
            mapLinks={siteMap.mapLinks}
            isLocating={siteMap.isLocating}
            onLocateMe={siteMap.locateMe}
            onFetchMapData={() => siteMap.fetchSiteMapData()}
          />
        )}
      </main>
    </div>
  );
}
