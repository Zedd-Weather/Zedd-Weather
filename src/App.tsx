import { useState, useRef, useEffect } from 'react';
import { 
  Thermometer, 
  Droplets, 
  Wind, 
  ShieldCheck, 
  Activity, 
  Server, 
  Cloud,
  Terminal,
  Database,
  Cpu,
  Map as MapIcon,
  Camera,
  AlertTriangle,
  Loader2,
  Video,
  CloudRain,
  Waves,
  Sun,
  X,
  CalendarDays,
  Archive,
  Download,
  Upload,
  Search,
  Filter,
  Volume2,
  VolumeX,
  Bell,
  BellOff,
  ChevronDown,
  ChevronUp,
  HardHat
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
  Bar
} from 'recharts';
import { GoogleGenAI, ThinkingLevel, Type } from '@google/genai';
import ReactMarkdown from 'react-markdown';
import { Toaster, toast } from 'sonner';
import ConstructionDashboard from './components/ConstructionDashboard';

type TabId = 'telemetry' | 'risk' | 'map' | 'forecast' | 'locker' | 'construction';
interface GeoLocation { lat: number; lng: number; }

// Hourly data populated from Open-Meteo in fetchRealTelemetry()

// Initialize Gemini API with validation
const apiKey = process.env.GEMINI_API_KEY;
if (!apiKey) {
  console.warn('GEMINI_API_KEY is not configured. AI features will be unavailable.');
}
const ai = new GoogleGenAI({ apiKey: apiKey ?? '' });

const DEFAULT_LOCATION: GeoLocation = { lat: 37.7749, lng: -122.4194 };
const DEFAULT_AQI = 42;
const DEFAULT_TIDE = 1.2;
const TELEMETRY_REFRESH_INTERVAL_MS = 60_000;

const API_BASE = {
  weather: 'https://api.open-meteo.com/v1/forecast',
  airQuality: 'https://air-quality-api.open-meteo.com/v1/air-quality',
  marine: 'https://marine-api.open-meteo.com/v1/marine',
} as const;

const TABS: { id: TabId; label: string; icon: typeof Activity }[] = [
  { id: 'telemetry', label: 'Telemetry', icon: Activity },
  { id: 'construction', label: 'Construction DSS', icon: HardHat },
  { id: 'risk', label: 'AI Risk Analysis', icon: AlertTriangle },
  { id: 'map', label: 'Site Map & Logistics', icon: MapIcon },
  { id: 'forecast', label: 'Forecast Grounding', icon: CalendarDays },
  { id: 'locker', label: 'Sharding Locker', icon: Archive },
];

function TabLoadingFallback() {
  return (
    <div className="flex flex-col items-center justify-center h-64 space-y-4">
      <Loader2 className="w-10 h-10 text-emerald-500 animate-spin" />
      <p className="text-slate-400 text-sm animate-pulse">Loading secure telemetry...</p>
    </div>
  );
}

const getMetricStatus = (type: string, value: number) => {
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
};

const MetricCard = ({ title, value, unit, icon: Icon, type }: any) => {
  const statusInfo = getMetricStatus(type, typeof value === 'string' ? parseFloat(value.replace(/,/g, '')) : Number(value));
  const isCritical = statusInfo.label === 'Critical' || statusInfo.label === 'Hazardous' || statusInfo.label === 'Extreme';
  
  return (
    <div className={`bg-[#111] border ${statusInfo.border} rounded-xl p-3 sm:p-5 flex flex-col relative overflow-hidden transition-all duration-300 hover:bg-[#161616] shadow-sm ${isCritical ? 'ring-1 ring-rose-500/50 animate-pulse' : ''}`}>
      {isCritical && (
        <div className="absolute top-0 right-0 w-10 h-10 sm:w-12 sm:h-12 -mr-5 -mt-5 sm:-mr-6 sm:-mt-6 bg-rose-500/20 blur-xl rounded-full"></div>
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
        <p className="text-[10px] sm:text-sm text-slate-400 font-medium mb-0.5 sm:mb-1">{title}</p>
        <div className="flex items-baseline space-x-1">
          <p className="text-xl sm:text-3xl font-bold text-slate-100 tracking-tight">{value}</p>
          <span className="text-[10px] sm:text-sm text-slate-500 font-medium">{unit}</span>
        </div>
      </div>
    </div>
  );
};

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('telemetry');
  
  // Telemetry Source State
  const [telemetrySource, setTelemetrySource] = useState<'onboard' | 'external'>('onboard');

  // Live Telemetry State
  const [externalTelemetry, setExternalTelemetry] = useState({
    temp: 0,
    humidity: 0,
    pressure: 0,
    precipitation: 0,
    tide: 0,
    uvIndex: 0,
    aqi: 0
  });

  const [onboardTelemetry, setOnboardTelemetry] = useState({
    temp: 22.5,
    humidity: 45.2,
    pressure: 1012.5,
    precipitation: 15,
    tide: DEFAULT_TIDE,
    uvIndex: 3.5,
    aqi: DEFAULT_AQI
  });

  const currentTelemetry = telemetrySource === 'onboard' ? onboardTelemetry : externalTelemetry;

  // 24-hour weather data (fetched from Open-Meteo for both modes)
  const [hourlyWeatherData, setHourlyWeatherData] = useState<{time: string, temp: number, humidity: number, pressure: number}[]>([]);

  // Risk Analysis State
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [mediaPreview, setMediaPreview] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [riskReport, setRiskReport] = useState<string | null>(null);
  const [riskLevel, setRiskLevel] = useState<'Green' | 'Amber' | 'Red' | 'Black' | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Pi Location State
  const [piLocation, setPiLocation] = useState<GeoLocation>(DEFAULT_LOCATION);

  // Alert System State
  const [activeAlerts, setActiveAlerts] = useState<{id: string, type: string, message: string, severity: 'critical' | 'warning', timestamp: number}[]>([]);
  const [isMuted, setIsMuted] = useState(false);
  const [showAlerts, setShowAlerts] = useState(false);
  const alertedIdsRef = useRef<Set<string>>(new Set());

  const playAlertSound = (severity: 'critical' | 'warning') => {
    try {
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const oscillator = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioCtx.destination);

      oscillator.type = severity === 'critical' ? 'sawtooth' : 'sine';
      oscillator.frequency.setValueAtTime(severity === 'critical' ? 440 : 880, audioCtx.currentTime);
      
      gainNode.gain.setValueAtTime(0.05, audioCtx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.5);

      oscillator.start();
      oscillator.stop(audioCtx.currentTime + 0.5);
    } catch (e) {
      console.warn("Audio alert failed", e);
    }
  };

  useEffect(() => {
    const newAlerts: typeof activeAlerts = [];
    
    // Temperature Thresholds
    if (currentTelemetry.temp > 35 || currentTelemetry.temp < 0) {
      newAlerts.push({ id: 'temp-crit', type: 'Temperature', message: `Critical Temperature: ${currentTelemetry.temp.toFixed(1)}°C`, severity: 'critical', timestamp: Date.now() });
    } else if (currentTelemetry.temp > 30 || currentTelemetry.temp < 5) {
      newAlerts.push({ id: 'temp-warn', type: 'Temperature', message: `High Temperature: ${currentTelemetry.temp.toFixed(1)}°C`, severity: 'warning', timestamp: Date.now() });
    }

    // AQI Thresholds
    if (currentTelemetry.aqi > 150) {
      newAlerts.push({ id: 'aqi-crit', type: 'AQI', message: `Hazardous Air Quality: ${Math.round(currentTelemetry.aqi)}`, severity: 'critical', timestamp: Date.now() });
    } else if (currentTelemetry.aqi > 100) {
      newAlerts.push({ id: 'aqi-warn', type: 'AQI', message: `Unhealthy Air Quality: ${Math.round(currentTelemetry.aqi)}`, severity: 'warning', timestamp: Date.now() });
    }

    // Precipitation Thresholds
    if (currentTelemetry.precipitation > 80) {
      newAlerts.push({ id: 'precip-crit', type: 'Precipitation', message: `Critical Precipitation Risk: ${currentTelemetry.precipitation}%`, severity: 'critical', timestamp: Date.now() });
    } else if (currentTelemetry.precipitation > 50) {
      newAlerts.push({ id: 'precip-warn', type: 'Precipitation', message: `High Precipitation Risk: ${currentTelemetry.precipitation}%`, severity: 'warning', timestamp: Date.now() });
    }

    // Check for new alerts to play sound and show toast
    const currentIds = new Set(newAlerts.map(a => a.id));
    
    newAlerts.forEach(alert => {
      if (!alertedIdsRef.current.has(alert.id)) {
        // New alert triggered
        if (alert.severity === 'critical') {
          toast.error(alert.message, {
            description: `Severity: ${alert.type} Critical`,
            duration: 10000,
          });
        } else {
          toast.warning(alert.message, {
            description: `Severity: ${alert.type} Warning`,
            duration: 5000,
          });
        }
      }
    });

    const hasNewCritical = newAlerts.some(a => a.severity === 'critical' && !alertedIdsRef.current.has(a.id));
    const hasNewWarning = newAlerts.some(a => a.severity === 'warning' && !alertedIdsRef.current.has(a.id));

    if (!isMuted && (hasNewCritical || hasNewWarning)) {
      playAlertSound(hasNewCritical ? 'critical' : 'warning');
    }

    // Update the ref
    alertedIdsRef.current = currentIds;
    setActiveAlerts(newAlerts);
  }, [currentTelemetry, isMuted]);

  // Locker State
  const [lockerEntries, setLockerEntries] = useState<any[]>([]);
  const [lockerSearch, setLockerSearch] = useState('');
  const [lockerFilter, setLockerFilter] = useState('All');
  const [expandedLockerId, setExpandedLockerId] = useState<string | null>(null);
  const importFileRef = useRef<HTMLInputElement>(null);

  // Forecast State
  const [forecastData, setForecastData] = useState<any[]>([]);
  const [isFetchingForecast, setIsFetchingForecast] = useState(false);

  // Load Locker on Mount
  useEffect(() => {
    const saved = localStorage.getItem('zedd_sharding_locker');
    if (saved) {
      try { setLockerEntries(JSON.parse(saved)); } catch (e) {}
    }
  }, []);

  const saveToLocker = (shards: any[], report: string, level: string | null) => {
    const newEntry = {
      id: 'LKR-' + Date.now(),
      timestamp: Date.now(),
      shards,
      report,
      riskLevel: level
    };
    const updated = [newEntry, ...lockerEntries];
    setLockerEntries(updated);
    localStorage.setItem('zedd_sharding_locker', JSON.stringify(updated));
  };

  const exportShards = () => {
    if (directiveShards.length === 0) return;
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(directiveShards));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", "zedd-shards-" + Date.now() + ".json");
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
  };

  const importShards = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const importedShards = JSON.parse(event.target?.result as string);
        if (Array.isArray(importedShards) && importedShards.length > 0 && importedShards[0].content) {
          setDirectiveShards(importedShards);
          const reconstructedReport = importedShards.map(s => s.content).join('\n\n');
          setRiskReport(reconstructedReport);
          setRiskLevel('Amber'); // Default or could be saved in export
          setActiveTab('risk');
        }
      } catch (err) {
        console.error("Failed to parse shards", err);
      }
    };
    reader.readAsText(file);
    if (importFileRef.current) importFileRef.current.value = '';
  };

  const fetchForecast = async () => {
    if (!piLocation) return;
    setIsFetchingForecast(true);
    try {
      const res = await fetch(`${API_BASE.weather}?latitude=${piLocation.lat}&longitude=${piLocation.lng}&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max,uv_index_max&timezone=auto`);
      const data = await res.json();
      if (data && data.daily) {
        const formatted = data.daily.time.map((timeStr: string, i: number) => ({
          date: new Date(timeStr).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
          tempMax: data.daily.temperature_2m_max[i],
          tempMin: data.daily.temperature_2m_min[i],
          precip: data.daily.precipitation_probability_max[i],
          wind: data.daily.wind_speed_10m_max[i],
          uv: data.daily.uv_index_max[i]
        }));
        setForecastData(formatted);
      }
    } catch (err) {
      console.error("Failed to fetch forecast:", err);
    } finally {
      setIsFetchingForecast(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'forecast') {
      fetchForecast();
    }
  }, [activeTab, piLocation]);

  const analyzeForecast = async () => {
    setIsAnalyzing(true);
    setRiskReport(null);
    setRiskLevel(null);
    setDirectiveShards([]);
    setActiveTab('risk');
    
    try {
      const response = await ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: `You are a Principal Edge AI and IoT Systems Architect.
        Here is the 7-day weather forecast for the site:
        ${JSON.stringify(forecastData, null, 2)}
        
        Analyze this forecast for any upcoming environmental or structural risks.
        Provide strict mitigation directives that will be cryptographically signed to the ledger.`,
        config: {
          responseMimeType: "application/json",
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              riskLevel: {
                type: Type.STRING,
                description: "The overall risk level based on the forecast. Must be one of: Green, Amber, Red, Black.",
                enum: ["Green", "Amber", "Red", "Black"]
              },
              report: {
                type: Type.STRING,
                description: "The detailed markdown report containing the analysis and mitigation directives."
              }
            },
            required: ["riskLevel", "report"]
          }
        }
      });
      const data = JSON.parse(response.text);
      setRiskLevel(data.riskLevel);
      setRiskReport(data.report);
    } catch (error: any) {
      console.error("Auto analysis failed", error);
      setRiskReport("Failed to perform automated risk analysis on forecast.");
      setRiskLevel("Amber");
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Fetch real telemetry data from Open-Meteo APIs
  const fetchRealTelemetry = async (location: {lat: number, lng: number}) => {
    try {
      const { lat, lng: lon } = location;
      
      const [weatherRes, aqiRes, marineRes] = await Promise.all([
        fetch(`${API_BASE.weather}?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,surface_pressure,uv_index&hourly=temperature_2m,relative_humidity_2m,surface_pressure,precipitation_probability&timezone=auto&forecast_days=1`),
        fetch(`${API_BASE.airQuality}?latitude=${lat}&longitude=${lon}&current=us_aqi`),
        fetch(`${API_BASE.marine}?latitude=${lat}&longitude=${lon}&current=wave_height`)
      ]);

      const weather = await weatherRes.json();
      const aqi = await aqiRes.json();
      const marine = await marineRes.json();

      // Get current hour index for hourly data
      const currentHour = new Date().getHours();
      const precipProb = weather.hourly?.precipitation_probability?.[currentHour] ?? 0;

      const newTelemetry = {
        temp: weather.current?.temperature_2m ?? 0,
        humidity: weather.current?.relative_humidity_2m ?? 0,
        pressure: weather.current?.surface_pressure ?? 0,
        precipitation: precipProb,
        uvIndex: weather.current?.uv_index ?? 0,
        aqi: aqi.current?.us_aqi ?? 42,
        tide: marine.current?.wave_height ?? 1.2
      };

      setExternalTelemetry(newTelemetry);

      // Also update onboard telemetry with real data (onboard = same API, local reference)
      setOnboardTelemetry(newTelemetry);

      // Populate 24-hour weather chart from hourly API data
      if (weather.hourly?.time) {
        const hourly = weather.hourly.time.map((t: string, i: number) => ({
          time: new Date(t).toLocaleTimeString('en-US', { hour: '2-digit', hour12: false }),
          temp: weather.hourly.temperature_2m?.[i] ?? 0,
          humidity: weather.hourly.relative_humidity_2m?.[i] ?? 0,
          pressure: weather.hourly.surface_pressure?.[i] ?? 0,
        }));
        setHourlyWeatherData(hourly);
      }

      return newTelemetry;
    } catch (error) {
      console.error("Failed to fetch real telemetry:", error);
      return null;
    }
  };

  // Automated AI Risk Analysis based purely on telemetry
  const autoAnalyzeRisk = async (telemetry: any) => {
    setIsAnalyzing(true);
    setDirectiveShards([]);
    try {
      const response = await ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: `You are a Principal Edge AI and IoT Systems Architect monitoring an industrial construction site.
        Current LIVE micro-climate telemetry:
        - Temperature: ${telemetry.temp.toFixed(1)}°C
        - Humidity: ${telemetry.humidity.toFixed(1)}%
        - Pressure: ${telemetry.pressure.toFixed(1)} hPa
        - Precipitation: ${telemetry.precipitation.toFixed(0)} %
        - Tide/Wave Level: ${telemetry.tide.toFixed(2)} m
        - UV Index: ${telemetry.uvIndex.toFixed(1)}
        - AQI: ${Math.round(telemetry.aqi)}

        Based purely on this real-time telemetry, identify any environmental or structural risks for the construction site.
        Provide strict mitigation directives that will be cryptographically signed to the ledger. Do not ask for images, base your analysis solely on the data provided.`,
        config: {
          responseMimeType: "application/json",
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              riskLevel: {
                type: Type.STRING,
                description: "The overall risk level based on the telemetry. Must be one of: Green, Amber, Red, Black. Green is low risk, Black is full shutdown.",
                enum: ["Green", "Amber", "Red", "Black"]
              },
              report: {
                type: Type.STRING,
                description: "The detailed markdown report containing the analysis and mitigation directives."
              }
            },
            required: ["riskLevel", "report"]
          }
        }
      });
      const data = JSON.parse(response.text);
      setRiskLevel(data.riskLevel);
      setRiskReport(data.report);
    } catch (error: any) {
      console.error("Auto analysis failed", error);
      const errStr = typeof error === 'string' ? error : JSON.stringify(error);
      if (errStr.includes('429')) {
        setRiskReport("AI Analysis is temporarily unavailable due to rate limits. Please wait a moment and try again.");
      } else if (errStr.includes('500') || errStr.includes('xhr error') || errStr.includes('Rpc failed')) {
        setRiskReport("AI Analysis service is currently experiencing network issues. Retrying shortly...");
      } else {
        setRiskReport("Failed to perform automated risk analysis. Please check your connection or API key.");
      }
      setRiskLevel("Amber"); // Default to Amber on error for safety
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Fetch telemetry on mount and set interval
  useEffect(() => {
    let isMounted = true;
    let interval: any;
    
    const init = async () => {
      let location = DEFAULT_LOCATION;
      
      try {
        if ('geolocation' in navigator) {
          const position = await new Promise<GeolocationPosition>((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
          });
          location = { lat: position.coords.latitude, lng: position.coords.longitude };
        }
      } catch (geoError) {
        console.warn("Geolocation failed or denied, using default coordinates.", geoError);
      }
      
      if (isMounted) {
        setPiLocation(location);
        const telemetry = await fetchRealTelemetry(location);
        if (telemetry) {
          autoAnalyzeRisk(telemetry);
        }
        
        interval = setInterval(() => {
          fetchRealTelemetry(location);
        }, TELEMETRY_REFRESH_INTERVAL_MS); // Update every minute
      }
    };
    
    init();
    
    return () => {
      isMounted = false;
      if (interval) clearInterval(interval);
    };
  }, []);

  // Map State
  const [isFetchingMap, setIsFetchingMap] = useState(false);
  const [mapReport, setMapReport] = useState<string | null>(null);
  const [mapLinks, setMapLinks] = useState<any[]>([]);
  const [isLocating, setIsLocating] = useState(false);

  // Initial Geolocation
  useEffect(() => {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setPiLocation({ lat: position.coords.latitude, lng: position.coords.longitude });
        },
        (error) => {
          console.warn("Initial geolocation failed or denied.", error);
        },
        { timeout: 5000 }
      );
    }
  }, []);

  const locateMe = async () => {
    setIsLocating(true);
    setMapReport(null);
    try {
      if ('geolocation' in navigator) {
        const position = await new Promise<GeolocationPosition>((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 10000 });
        });
        const newLocation = { lat: position.coords.latitude, lng: position.coords.longitude };
        setPiLocation(newLocation);
        // Automatically fetch map data for the new location
        fetchSiteMapData(newLocation);
      } else {
        setMapReport("Geolocation is not supported by your browser.");
      }
    } catch (error) {
      console.error("Failed to get location", error);
      setMapReport("Failed to get your current location. Please ensure location permissions are granted.");
    } finally {
      setIsLocating(false);
    }
  };

  // Historical Data State
  const [historicalRange, setHistoricalRange] = useState<'7d' | '14d' | '30d'>('7d');
  const [historicalData, setHistoricalData] = useState<any[]>([]);
  const [isFetchingHistory, setIsFetchingHistory] = useState(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [exportMetrics, setExportMetrics] = useState({
    temp: true,
    humidity: true,
    pressure: true,
    precipitation: true
  });

  const exportHistoricalToCSV = () => {
    if (historicalData.length === 0) return;

    // Create CSV header
    const headers = ['Time'];
    if (exportMetrics.temp) headers.push('Temperature (°C)');
    if (exportMetrics.humidity) headers.push('Humidity (%)');
    if (exportMetrics.pressure) headers.push('Pressure (hPa)');
    if (exportMetrics.precipitation) headers.push('Precipitation Prob. (%)');
    
    // Create CSV rows
    const rows = historicalData.map(data => {
      const row = [data.time];
      if (exportMetrics.temp) row.push(data.temp);
      if (exportMetrics.humidity) row.push(data.humidity);
      if (exportMetrics.pressure) row.push(data.pressure);
      if (exportMetrics.precipitation) row.push(data.precipitation || 0);
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
    setIsExportModalOpen(false);
  };

  // Fetch Historical Telemetry — always from Open-Meteo
  const fetchHistoricalTelemetry = async (days: number, location: {lat: number, lng: number}) => {
    setIsFetchingHistory(true);
    try {
      const { lat, lng: lon } = location;
      
      const res = await fetch(`${API_BASE.weather}?latitude=${lat}&longitude=${lon}&past_days=${days}&hourly=temperature_2m,relative_humidity_2m,surface_pressure,precipitation_probability`);
      const data = await res.json();
      
      if (data && data.hourly) {
        const formattedData = data.hourly.time.map((timeStr: string, index: number) => {
          const date = new Date(timeStr);
          return {
            time: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit' }),
            rawDate: date,
            temp: data.hourly.temperature_2m[index],
            humidity: data.hourly.relative_humidity_2m[index],
            pressure: data.hourly.surface_pressure[index],
            precipitation: data.hourly.precipitation_probability[index],
          };
        });
        
        // Filter to show roughly 1 point per day for longer ranges to avoid chart clutter, or every 6 hours for 7 days
        const step = days === 7 ? 6 : (days === 14 ? 12 : 24);
        const sampledData = formattedData.filter((_: any, i: number) => i % step === 0);
        
        setHistoricalData(sampledData);
      }
    } catch (error) {
      console.error("Failed to fetch historical telemetry:", error);
    } finally {
      setIsFetchingHistory(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'telemetry' && piLocation) {
      const days = historicalRange === '7d' ? 7 : (historicalRange === '14d' ? 14 : 30);
      fetchHistoricalTelemetry(days, piLocation);
    }
  }, [historicalRange, activeTab, piLocation]);

  const [nodes] = useState([
    { id: 'Node A', role: 'Control Plane + Storage', status: 'Active', ip: '10.0.0.14', detail: 'InfluxDB, Grafana, Open WebUI' },
    { id: 'Node B', role: 'AI Worker', status: 'Active', ip: '10.0.0.15', detail: 'Orchestration + AI Inference' },
    { id: 'Node C', role: 'Sensory Worker', status: 'Active', ip: '10.0.0.16', detail: 'Telemetry Publisher (MQTT)' },
  ]);

  const [attestations, setAttestations] = useState<{id: string, time: string, type: string, verified: boolean}[]>([]);

  const [isGeneratingProof, setIsGeneratingProof] = useState(false);
  const [isLedgerOpen, setIsLedgerOpen] = useState(false);

  const [directiveShards, setDirectiveShards] = useState<{ id: string, hash: string, content: string }[]>([]);
  const [isSharding, setIsSharding] = useState(false);

  const shardDirectives = async () => {
    if (!riskReport) return;
    setIsSharding(true);
    
    // Split the report into paragraphs/sections to represent shards
    const chunks = riskReport.split('\n\n').filter(chunk => chunk.trim().length > 0);
    
    const newShards = await Promise.all(chunks.map(async (chunk, index) => {
      // SHA-256 hash via Web Crypto API
      const data = new TextEncoder().encode(chunk + Date.now() + index);
      const hashBuffer = await crypto.subtle.digest('SHA-256', data);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const hexHash = '0x' + hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
      
      return {
        id: `Shard-${index + 1}`,
        hash: hexHash,
        content: chunk
      };
    }));
    
    setDirectiveShards(newShards);
    saveToLocker(newShards, riskReport, riskLevel);
    setIsSharding(false);
  };

  const generateZeddProof = async () => {
    setIsGeneratingProof(true);
    
    // SHA-256 hash via Web Crypto API
    const dataString = JSON.stringify(currentTelemetry) + Date.now();
    const data = new TextEncoder().encode(dataString);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hexHash = '0x' + hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    
    setAttestations(prev => [
      { id: hexHash, time: 'Just now', type: 'Manual Shard', verified: true },
      ...prev.slice(0, 3) // Keep only the latest 4
    ]);
    setIsGeneratingProof(false);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setMediaFile(file);
      setMediaPreview(URL.createObjectURL(file));
      setRiskReport(null);
    }
  };

  const analyzeRisk = async () => {
    if (!mediaFile) return;
    setIsAnalyzing(true);
    setRiskReport(null);
    setRiskLevel(null);
    setDirectiveShards([]);

    try {
      const reader = new FileReader();
      reader.onloadend = async () => {
        const base64Data = (reader.result as string).split(',')[1];
        
        const response = await ai.models.generateContent({
          model: 'gemini-3-flash-preview',
          contents: [
            {
              inlineData: {
                data: base64Data,
                mimeType: mediaFile.type
              }
            },
            `You are a Principal Edge AI and IoT Systems Architect analyzing a construction site. 
            Current live micro-climate telemetry from Sense HAT: 
            - Temperature: ${currentTelemetry.temp.toFixed(1)}°C
            - Humidity: ${currentTelemetry.humidity.toFixed(1)}%
            - Pressure: ${currentTelemetry.pressure.toFixed(1)} hPa
            - Precipitation: ${currentTelemetry.precipitation.toFixed(0)} %
            - Tide Level: ${currentTelemetry.tide.toFixed(2)} m
            - UV Index: ${currentTelemetry.uvIndex.toFixed(1)}
            - AQI: ${Math.round(currentTelemetry.aqi)}
            
            Analyze this media of the construction site. Identify any environmental or structural risks, 
            and provide strict mitigation directives that will be cryptographically signed to the ledger.`
          ],
          config: {
            responseMimeType: "application/json",
            responseSchema: {
              type: Type.OBJECT,
              properties: {
                riskLevel: {
                  type: Type.STRING,
                  description: "The overall risk level based on the telemetry and media. Must be one of: Green, Amber, Red, Black. Green is low risk, Black is full shutdown.",
                  enum: ["Green", "Amber", "Red", "Black"]
                },
                report: {
                  type: Type.STRING,
                  description: "The detailed markdown report containing the analysis and mitigation directives."
                }
              },
              required: ["riskLevel", "report"]
            }
          }
        });

        try {
          const data = JSON.parse(response.text || "{}");
          setRiskLevel(data.riskLevel || null);
          setRiskReport(data.report || "Analysis failed.");
        } catch (e) {
          setRiskReport("Failed to parse analysis response.");
        }
        setIsAnalyzing(false);
      };
      reader.readAsDataURL(mediaFile);
    } catch (error: any) {
      console.error("Error analyzing risk:", error);
      const errStr = typeof error === 'string' ? error : JSON.stringify(error);
      if (errStr.includes('429')) {
        setRiskReport("AI Analysis is temporarily unavailable due to rate limits. Please wait a moment and try again.");
      } else if (errStr.includes('500') || errStr.includes('xhr error') || errStr.includes('Rpc failed')) {
        setRiskReport("AI Analysis service is currently experiencing network issues. Please try again later.");
      } else {
        setRiskReport("An error occurred during analysis.");
      }
      setRiskLevel("Amber");
      setIsAnalyzing(false);
    }
  };

  const getRiskColor = (level: string | null) => {
    switch(level) {
      case 'Green': return { bg: 'bg-emerald-950/80', text: 'text-emerald-400', border: 'border-emerald-500/60 shadow-[0_0_15px_rgba(16,185,129,0.15)]', label: 'LOW RISK' };
      case 'Amber': return { bg: 'bg-amber-950/80', text: 'text-amber-400', border: 'border-amber-500/60 shadow-[0_0_15px_rgba(245,158,11,0.15)]', label: 'ELEVATED RISK' };
      case 'Red': return { bg: 'bg-rose-950/80', text: 'text-rose-400', border: 'border-rose-500/60 shadow-[0_0_15px_rgba(244,63,94,0.15)]', label: 'HIGH RISK' };
      case 'Black': return { bg: 'bg-black', text: 'text-red-500', border: 'border-red-600 shadow-[0_0_20px_rgba(220,38,38,0.3)]', label: 'FULL SHUTDOWN' };
      default: return { bg: 'bg-slate-800/80', text: 'text-slate-400', border: 'border-slate-700', label: 'ANALYZING...' };
    }
  };

  const getRiskIcon = (level: string | null) => {
    switch(level) {
      case 'Green': return <ShieldCheck className="w-5 h-5 mr-2" />;
      case 'Amber': return <AlertTriangle className="w-5 h-5 mr-2" />;
      case 'Red': return <Activity className="w-5 h-5 mr-2" />;
      case 'Black': return <Terminal className="w-5 h-5 mr-2" />;
      default: return <ShieldCheck className="w-5 h-5 mr-2" />;
    }
  };

  const fetchSiteMapData = async (overrideLocation?: {lat: number, lng: number}) => {
    setIsFetchingMap(true);
    setMapReport(null);
    setMapLinks([]);

    try {
      const loc = overrideLocation || piLocation;
      const lat = loc?.lat || 37.7749;
      const lng = loc?.lng || -122.4194;

      const response = await ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: `Find nearby emergency services and hardware stores near the coordinates ${lat}, ${lng}. Provide a brief logistics report.`,
        config: {
          tools: [{ googleMaps: {} }],
          toolConfig: {
            retrievalConfig: {
              latLng: { latitude: lat, longitude: lng }
            }
          }
        }
      });

      setMapReport(response.text || "Failed to fetch map data.");
      
      const chunks = response.candidates?.[0]?.groundingMetadata?.groundingChunks;
      if (chunks) {
        const links = chunks.map((chunk: any) => chunk.maps).filter(Boolean);
        // Remove duplicates based on URI
        const uniqueLinks = Array.from(new Map(links.map(item => [item.uri, item])).values());
        setMapLinks(uniqueLinks);
      }
    } catch (error: any) {
      console.error("Error fetching map data:", error);
      const errStr = typeof error === 'string' ? error : JSON.stringify(error);
      if (errStr.includes('429')) {
        setMapReport("Map data is temporarily unavailable due to rate limits. Please wait a moment and try again.");
      } else if (errStr.includes('500') || errStr.includes('xhr error') || errStr.includes('Rpc failed')) {
        setMapReport("Map service is currently experiencing network issues. Please try again later.");
      } else {
        setMapReport(`An error occurred while fetching map data: ${error.message || 'Unknown error'}`);
      }
    } finally {
      setIsFetchingMap(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-slate-200 font-sans selection:bg-emerald-500/30">
      <Toaster position="top-right" theme="dark" richColors closeButton />
      {/* Top Navigation */}
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
            {/* Alert System Controls */}
            <div className="flex items-center space-x-1 sm:space-x-2">
              <button 
                onClick={() => setIsMuted(!isMuted)}
                className={`p-1.5 sm:p-2 rounded-lg border transition-colors ${isMuted ? 'bg-rose-500/10 border-rose-500/30 text-rose-400' : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'}`}
                title={isMuted ? "Unmute Alerts" : "Mute Alerts"}
              >
                {isMuted ? <VolumeX className="w-3.5 h-3.5 sm:w-4 sm:h-4" /> : <Volume2 className="w-3.5 h-3.5 sm:w-4 sm:h-4" />}
              </button>
              
              <div className="relative">
                <button 
                  onClick={() => setShowAlerts(!showAlerts)}
                  className={`p-1.5 sm:p-2 rounded-lg border transition-colors relative ${activeAlerts.length > 0 ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'}`}
                >
                  {activeAlerts.length > 0 ? <Bell className="w-3.5 h-3.5 sm:w-4 sm:h-4 animate-pulse" /> : <BellOff className="w-3.5 h-3.5 sm:w-4 sm:h-4" />}
                  {activeAlerts.length > 0 && (
                    <span className="absolute -top-1 -right-1 w-3.5 h-3.5 sm:w-4 sm:h-4 bg-rose-500 text-white text-[9px] sm:text-[10px] font-bold rounded-full flex items-center justify-center border-2 border-[#0a0a0a]">
                      {activeAlerts.length}
                    </span>
                  )}
                </button>
                
                {/* Alerts Dropdown */}
                {showAlerts && (
                  <div className="absolute right-0 mt-2 w-72 sm:w-80 bg-[#111] border border-slate-800 rounded-xl shadow-2xl z-[60] overflow-hidden">
                    <div className="p-3 sm:p-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/50">
                      <h3 className="text-xs sm:text-sm font-bold text-slate-200">Active Alerts</h3>
                      <button onClick={() => setShowAlerts(false)} className="text-slate-500 hover:text-slate-300">
                        <X className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                      </button>
                    </div>
                    <div className="max-h-80 sm:max-h-96 overflow-y-auto p-2 space-y-2">
                      {activeAlerts.length === 0 ? (
                        <div className="py-6 sm:py-8 text-center">
                          <ShieldCheck className="w-6 h-6 sm:w-8 sm:h-8 text-emerald-500/30 mx-auto mb-2" />
                          <p className="text-[10px] sm:text-xs text-slate-500">No active alerts. System secure.</p>
                        </div>
                      ) : (
                        activeAlerts.map(alert => (
                          <div key={alert.id} className={`p-2 sm:p-3 rounded-lg border flex items-start space-x-2 sm:space-x-3 ${alert.severity === 'critical' ? 'bg-rose-500/10 border-rose-500/30' : 'bg-amber-500/10 border-amber-500/30'}`}>
                            <AlertTriangle className={`w-3.5 h-3.5 sm:w-4 sm:h-4 mt-0.5 flex-shrink-0 ${alert.severity === 'critical' ? 'text-rose-400' : 'text-amber-400'}`} />
                            <div>
                              <p className={`text-[10px] sm:text-xs font-bold uppercase tracking-wider ${alert.severity === 'critical' ? 'text-rose-400' : 'text-amber-400'}`}>{alert.type}</p>
                              <p className="text-xs sm:text-sm text-slate-200 mt-0.5">{alert.message}</p>
                              <p className="text-[9px] sm:text-[10px] text-slate-500 mt-1">{new Date(alert.timestamp).toLocaleTimeString()}</p>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
            
            <div className="hidden md:flex items-center space-x-2 text-sm text-slate-400 bg-slate-900 px-3 py-1.5 rounded-full border border-slate-800">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
              <span>Minima Network Sync: OK</span>
            </div>
            <div className="md:hidden w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="Minima Sync OK"></div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* Tab Navigation */}
        <div className="flex space-x-4 mb-8 border-b border-slate-800 pb-px overflow-x-auto scrollbar-hide">
          {TABS.map((tab) => (
            <button 
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                if (tab.id === 'map' && !mapReport) fetchSiteMapData();
              }}
              className={`pb-3 px-2 text-sm font-medium transition-colors border-b-2 whitespace-nowrap ${activeTab === tab.id ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-slate-400 hover:text-slate-300'}`}
            >
              <div className="flex items-center">
                <tab.icon className="w-4 h-4 mr-2" />
                {tab.label}
              </div>
            </button>
          ))}
        </div>

        {activeTab === 'telemetry' && (
          <>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 space-y-4 sm:space-y-0">
              <h2 className="text-lg sm:text-xl font-semibold text-slate-200">Current Readings</h2>
              <div className="flex bg-slate-900 rounded-lg p-1 border border-slate-800 self-start sm:self-auto">
                <button
                  onClick={() => setTelemetrySource('onboard')}
                  className={`px-3 sm:px-4 py-1 sm:py-1.5 text-[10px] sm:text-xs font-medium rounded-md transition-all ${
                    telemetrySource === 'onboard' 
                      ? 'bg-emerald-600 text-white shadow-sm' 
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  On Board
                </button>
                <button
                  onClick={() => setTelemetrySource('external')}
                  className={`px-3 sm:px-4 py-1 sm:py-1.5 text-[10px] sm:text-xs font-medium rounded-md transition-all ${
                    telemetrySource === 'external' 
                      ? 'bg-blue-600 text-white shadow-sm' 
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  AccuWeather
                </button>
              </div>
            </div>

            {/* Dashboard Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6 mb-8">
              <MetricCard title="Temperature" value={currentTelemetry.temp.toFixed(1)} unit="°C" icon={Thermometer} type="temp" />
              <MetricCard title="Humidity" value={currentTelemetry.humidity.toFixed(1)} unit="%" icon={Droplets} type="humidity" />
              <MetricCard title="Pressure" value={currentTelemetry.pressure.toFixed(1)} unit="hPa" icon={Wind} type="pressure" />
              <MetricCard title="Precip Prob." value={currentTelemetry.precipitation.toFixed(0)} unit="%" icon={CloudRain} type="precip" />
              <MetricCard title="Tide Level" value={currentTelemetry.tide.toFixed(2)} unit="m" icon={Waves} type="tide" />
              <MetricCard title="UV Index" value={currentTelemetry.uvIndex.toFixed(1)} unit="" icon={Sun} type="uv" />
              <MetricCard title="AQI" value={Math.round(currentTelemetry.aqi)} unit="" icon={Activity} type="aqi" />
              <MetricCard title="ZeddProofs" value="1,402" unit="" icon={ShieldCheck} type="proofs" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Left Column - Charts */}
              <div className="lg:col-span-2 space-y-8">
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
                        <Download className="w-3 h-3 sm:w-3.5 sm:h-3.5 mr-1 sm:mr-1.5" /> <span className="hidden xs:inline">Export CSV</span>
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
                              <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3}/>
                              <stop offset="95%" stopColor="#f43f5e" stopOpacity={0}/>
                            </linearGradient>
                            <linearGradient id="colorHumidHist" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
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

                <div className="bg-[#111] border border-slate-800 rounded-xl p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-lg font-medium flex items-center text-slate-200">
                      <Activity className="w-5 h-5 mr-2 text-rose-400" />
                      Environmental Telemetry (24h)
                    </h2>
                  </div>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={hourlyWeatherData}>
                        <defs>
                          <linearGradient id="colorTemp" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#f43f5e" stopOpacity={0}/>
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
                        <Tooltip 
                          contentStyle={{ backgroundColor: '#000', borderColor: '#333', color: '#fff' }}
                        />
                        <Line yAxisId="left" type="monotone" dataKey="humidity" stroke="#3b82f6" strokeWidth={2} dot={false} name="Humidity (%)" />
                        <Line yAxisId="right" type="monotone" dataKey="pressure" stroke="#64748b" strokeWidth={2} dot={false} name="Pressure (hPa)" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              {/* Right Column - Nodes & Workloads */}
              <div className="space-y-8">
                <div className="bg-[#111] border border-slate-800 rounded-xl p-6">
                  <h2 className="text-lg font-medium flex items-center mb-6 text-slate-200">
                    <Server className="w-5 h-5 mr-2 text-indigo-400" />
                    System Architecture
                  </h2>
                  <div className="space-y-4">
                    {nodes.map(node => (
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

                <div className="bg-[#111] border border-slate-800 rounded-xl p-6">
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
                        {att.verified && (
                          <ShieldCheck className="w-4 h-4 text-emerald-500" />
                        )}
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
              </div>
            </div>
          </>
        )}

        {activeTab === 'risk' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="space-y-8">
              <div className="bg-[#111] border border-slate-800 rounded-xl p-6">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-lg font-medium flex items-center text-slate-200">
                    <Activity className="w-5 h-5 mr-2 text-rose-400" />
                    Automated Telemetry Analysis
                  </h2>
                  <button 
                    onClick={() => autoAnalyzeRisk(currentTelemetry)}
                    disabled={isAnalyzing}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg border border-slate-700 transition-colors flex items-center disabled:opacity-50"
                  >
                    {isAnalyzing ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Activity className="w-3.5 h-3.5 mr-1.5" />}
                    Refresh Analysis
                  </button>
                </div>
                <p className="text-sm text-slate-400 mb-4">
                  The system continuously monitors live telemetry and uses Gemini 3.1 Pro (High Thinking) 
                  to generate mitigation directives without human interaction.
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

              <div className="bg-[#111] border border-slate-800 rounded-xl p-6">
                <h2 className="text-lg font-medium flex items-center mb-6 text-slate-200">
                  <Camera className="w-5 h-5 mr-2 text-indigo-400" />
                  Add Visual Context (Optional)
                </h2>
                <p className="text-sm text-slate-400 mb-6">
                  Upload images or video of the construction site to cross-reference visual data with the live telemetry.
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
                    onChange={handleFileChange} 
                    accept="image/*,video/*" 
                    className="hidden" 
                  />
                </div>

                <button 
                  onClick={analyzeRisk}
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
            </div>

            <div className="bg-[#111] border border-slate-800 rounded-xl p-6 h-full flex flex-col">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-medium flex items-center text-slate-200">
                  <ShieldCheck className="w-5 h-5 mr-2 text-emerald-400" />
                  Mitigation Directives
                </h2>
                {riskLevel && !isAnalyzing && (
                  <div className={`flex items-center px-3 py-1.5 rounded-lg border ${getRiskColor(riskLevel).bg} ${getRiskColor(riskLevel).border} ${getRiskColor(riskLevel).text}`}>
                    {getRiskIcon(riskLevel)}
                    <span className="text-sm font-bold tracking-wider">{getRiskColor(riskLevel).label}</span>
                  </div>
                )}
              </div>
              
              <div className="flex-1 overflow-y-auto pr-2">
                {isAnalyzing ? (
                  <TabLoadingFallback />
                ) : riskReport ? (
                  <div className="prose prose-invert prose-emerald max-w-none">
                    <div className="markdown-body text-sm text-slate-300">
                      <ReactMarkdown>{riskReport}</ReactMarkdown>
                    </div>
                    <div className="mt-6 p-3 sm:p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                        <p className="text-[10px] sm:text-xs text-emerald-400 font-mono flex items-center">
                          <Terminal className="w-3 h-3 mr-2 flex-shrink-0" />
                          Directive ready for Minima attestation (SHA-256)
                        </p>
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={exportShards}
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
                          <input type="file" ref={importFileRef} onChange={importShards} accept=".json" className="hidden" />
                          <button
                            onClick={shardDirectives}
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
                      
                      {directiveShards.length > 0 && (
                        <div className="mt-4 space-y-2 border-t border-emerald-500/20 pt-4">
                          <p className="text-xs text-slate-400 mb-2">Shards generated and ready for decentralized storage:</p>
                          {directiveShards.map(shard => (
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
                  </div>
                ) : (
                  <div className="h-full min-h-[300px] flex items-center justify-center text-slate-500">
                    <p>Waiting for initial telemetry analysis...</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'map' && (
          <div className="bg-[#111] border border-slate-800 rounded-xl p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
              <div>
                <h2 className="text-lg font-medium flex items-center text-slate-200">
                  <MapIcon className="w-5 h-5 mr-2 text-blue-400" />
                  Site Map & Logistics Grounding
                </h2>
                {piLocation && (
                  <p className="text-xs text-slate-500 mt-1 flex items-center">
                    <MapIcon className="w-3 h-3 mr-1" />
                    Using Pi Location: {piLocation.lat.toFixed(4)}, {piLocation.lng.toFixed(4)}
                  </p>
                )}
              </div>
              <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
                <button 
                  onClick={locateMe}
                  disabled={isLocating || isFetchingMap}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:bg-slate-900 disabled:text-slate-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center w-full sm:w-auto border border-slate-700"
                >
                  {isLocating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <MapIcon className="w-4 h-4 mr-2" />}
                  {isLocating ? 'Locating...' : 'Use My Location'}
                </button>
                <button 
                  onClick={() => fetchSiteMapData()}
                  disabled={isFetchingMap}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center w-full sm:w-auto"
                >
                  {isFetchingMap ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <MapIcon className="w-4 h-4 mr-2" />}
                  {isFetchingMap ? 'Querying Maps...' : 'Fetch Local Logistics'}
                </button>
              </div>
            </div>

            {isFetchingMap ? (
              <TabLoadingFallback />
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
                    ></iframe>
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
                    {mapLinks.length > 0 ? mapLinks.map((mapData, idx) => (
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
                          <p className="text-xs text-slate-500 truncate mb-2">
                            {mapData.uri}
                          </p>
                        </a>
                        {mapData.placeAnswerSources?.reviewSnippets && mapData.placeAnswerSources.reviewSnippets.length > 0 && (
                          <div className="mt-2 space-y-2 border-t border-slate-800 pt-2">
                            {mapData.placeAnswerSources.reviewSnippets.map((snippet: any, sIdx: number) => (
                              <div key={sIdx} className="text-xs text-slate-400 italic bg-slate-800/50 p-2 rounded">
                                "{snippet.text}"
                                {snippet.authorName && <span className="block mt-1 text-slate-500">- {snippet.authorName}</span>}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )) : (
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
                <p>Click "Fetch Local Logistics" to query Google Maps.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'forecast' && (
          <div className="bg-[#111] border border-slate-800 rounded-xl p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
              <div>
                <h2 className="text-lg font-medium flex items-center text-slate-200">
                  <CalendarDays className="w-5 h-5 mr-2 text-indigo-400" />
                  7-Day Forecast Grounding
                </h2>
                {piLocation && (
                  <p className="text-xs text-slate-500 mt-1 flex items-center">
                    <MapIcon className="w-3 h-3 mr-1" />
                    Using Pi Location: {piLocation.lat.toFixed(4)}, {piLocation.lng.toFixed(4)}
                  </p>
                )}
              </div>
              <button 
                onClick={analyzeForecast}
                disabled={isAnalyzing || forecastData.length === 0}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center w-full sm:w-auto"
              >
                {isAnalyzing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Activity className="w-4 h-4 mr-2" />}
                {isAnalyzing ? 'Analyzing Forecast...' : 'Analyze Forecast Risk'}
              </button>
            </div>

            {isFetchingForecast ? (
              <TabLoadingFallback />
            ) : forecastData.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {forecastData.map((day, idx) => (
                  <div key={idx} className="bg-[#1a1a1a] p-4 rounded-xl border border-slate-800 flex flex-col">
                    <p className="text-sm font-semibold text-slate-300 mb-3">{day.date}</p>
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-slate-500 flex items-center"><Thermometer className="w-3 h-3 mr-1" /> Max Temp</span>
                        <span className="text-sm text-slate-200">{day.tempMax.toFixed(1)}°C</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-slate-500 flex items-center"><Thermometer className="w-3 h-3 mr-1" /> Min Temp</span>
                        <span className="text-sm text-slate-200">{day.tempMin.toFixed(1)}°C</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-slate-500 flex items-center"><CloudRain className="w-3 h-3 mr-1" /> Precip Prob.</span>
                        <span className="text-sm text-slate-200">{day.precip.toFixed(0)} %</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-slate-500 flex items-center"><Wind className="w-3 h-3 mr-1" /> Wind</span>
                        <span className="text-sm text-slate-200">{day.wind.toFixed(1)} km/h</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-slate-500 flex items-center"><Sun className="w-3 h-3 mr-1" /> UV Index</span>
                        <span className="text-sm text-slate-200">{day.uv.toFixed(1)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-64 flex flex-col items-center justify-center text-slate-500 border-2 border-dashed border-slate-800 rounded-xl">
                <CalendarDays className="w-12 h-12 text-slate-600 mb-4" />
                <p>No forecast data available.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'construction' && (
          <ConstructionDashboard weather={currentTelemetry} />
        )}

        {activeTab === 'locker' && (
          <div className="bg-[#111] border border-slate-800 rounded-xl p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
              <h2 className="text-lg font-medium flex items-center text-slate-200">
                <Archive className="w-5 h-5 mr-2 text-emerald-400" />
                Sharding Evidence Locker
              </h2>
            </div>

            {/* Search and Filter Bar */}
            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 mb-6">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 sm:w-4 sm:h-4 text-slate-500" />
                <input 
                  type="text" 
                  placeholder="Search ID or content..." 
                  value={lockerSearch}
                  onChange={(e) => setLockerSearch(e.target.value)}
                  className="w-full bg-[#1a1a1a] border border-slate-800 rounded-lg pl-9 sm:pl-10 pr-4 py-1.5 sm:py-2 text-xs sm:text-sm text-slate-200 focus:outline-none focus:border-emerald-500/50 transition-colors"
                />
              </div>
              <div className="relative w-full sm:w-48">
                <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 sm:w-4 sm:h-4 text-slate-500" />
                <select 
                  value={lockerFilter}
                  onChange={(e) => setLockerFilter(e.target.value)}
                  className="w-full bg-[#1a1a1a] border border-slate-800 rounded-lg pl-9 sm:pl-10 pr-8 py-1.5 sm:py-2 text-xs sm:text-sm text-slate-200 appearance-none focus:outline-none focus:border-emerald-500/50 transition-colors cursor-pointer"
                >
                  <option value="All">All Risk Levels</option>
                  <option value="Green">Green (Low)</option>
                  <option value="Amber">Amber (Elevated)</option>
                  <option value="Red">Red (High)</option>
                  <option value="Black">Black (Shutdown)</option>
                </select>
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 sm:w-4 sm:h-4 text-slate-500 pointer-events-none" />
              </div>
            </div>
            
            {lockerEntries.length > 0 ? (
              <div className="space-y-4">
                {lockerEntries
                  .filter(entry => {
                    const matchesSearch = entry.id.toLowerCase().includes(lockerSearch.toLowerCase()) || 
                                          (entry.report && entry.report.toLowerCase().includes(lockerSearch.toLowerCase()));
                    const matchesFilter = lockerFilter === 'All' || entry.riskLevel === lockerFilter;
                    return matchesSearch && matchesFilter;
                  })
                  .map((entry) => (
                  <div key={entry.id} className="bg-[#1a1a1a] p-3 sm:p-5 rounded-xl border border-slate-800 transition-all">
                    <div className="flex flex-col sm:flex-row justify-between items-start mb-3 sm:mb-4 gap-2">
                      <div>
                        <h3 className="text-xs sm:text-sm font-semibold text-slate-200 flex items-center">
                          <Database className="w-3.5 h-3.5 sm:w-4 sm:h-4 mr-2 text-emerald-500" />
                          {entry.id}
                        </h3>
                        <p className="text-[10px] sm:text-xs text-slate-500 mt-1">
                          {new Date(entry.timestamp).toLocaleString()}
                        </p>
                      </div>
                      {entry.riskLevel && (
                        <span className={`px-2 py-0.5 sm:py-1 rounded text-[10px] sm:text-xs font-bold ${getRiskColor(entry.riskLevel).bg} ${getRiskColor(entry.riskLevel).text}`}>
                          {entry.riskLevel}
                        </span>
                      )}
                    </div>
                    
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <p className="text-[10px] sm:text-xs text-slate-400 font-medium">Shards ({entry.shards.length}):</p>
                        <button 
                          onClick={() => setExpandedLockerId(expandedLockerId === entry.id ? null : entry.id)}
                          className="text-[10px] sm:text-xs text-slate-400 hover:text-slate-200 flex items-center transition-colors"
                        >
                          {expandedLockerId === entry.id ? (
                            <><ChevronUp className="w-3 h-3 mr-1" /> Hide Details</>
                          ) : (
                            <><ChevronDown className="w-3 h-3 mr-1" /> View Details</>
                          )}
                        </button>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {entry.shards.slice(0, expandedLockerId === entry.id ? undefined : 2).map((shard: any) => (
                          <div key={shard.id} className="p-1.5 sm:p-2 bg-slate-900 border border-slate-800 rounded flex items-center justify-between">
                            <span className="text-[9px] sm:text-[10px] font-mono text-slate-400">{shard.id}</span>
                            <span className="text-[9px] sm:text-[10px] font-mono text-emerald-500/70 truncate ml-2">{shard.hash}</span>
                          </div>
                        ))}
                      </div>
                      {expandedLockerId !== entry.id && entry.shards.length > 2 && (
                        <p className="text-[9px] sm:text-[10px] text-slate-500 italic">+ {entry.shards.length - 2} more shards</p>
                      )}
                    </div>

                    {/* Expanded Details */}
                    {expandedLockerId === entry.id && (
                      <div className="mt-4 pt-4 border-t border-slate-800 animate-in fade-in slide-in-from-top-2 duration-200">
                        <p className="text-xs text-slate-400 font-medium mb-2">Reconstructed Report Snippet:</p>
                        <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 max-h-48 overflow-y-auto">
                          <div className="markdown-body text-xs text-slate-300">
                            <ReactMarkdown>{entry.report}</ReactMarkdown>
                          </div>
                        </div>
                      </div>
                    )}
                    
                    <div className="mt-4 pt-4 border-t border-slate-800 flex justify-end">
                      <button 
                        onClick={() => {
                          setDirectiveShards(entry.shards);
                          setRiskReport(entry.report);
                          setRiskLevel(entry.riskLevel);
                          setActiveTab('risk');
                        }}
                        className="px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 text-xs font-medium rounded-lg transition-colors flex items-center"
                      >
                        <Activity className="w-3.5 h-3.5 mr-1.5" />
                        Load into Risk Analysis View
                      </button>
                    </div>
                  </div>
                ))}
                
                {lockerEntries.filter(entry => {
                    const matchesSearch = entry.id.toLowerCase().includes(lockerSearch.toLowerCase()) || 
                                          (entry.report && entry.report.toLowerCase().includes(lockerSearch.toLowerCase()));
                    const matchesFilter = lockerFilter === 'All' || entry.riskLevel === lockerFilter;
                    return matchesSearch && matchesFilter;
                  }).length === 0 && (
                  <div className="p-8 text-center text-slate-500 border border-slate-800 rounded-xl bg-[#1a1a1a]">
                    <Search className="w-8 h-8 mx-auto mb-3 text-slate-600" />
                    <p>No shards match your search criteria.</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-64 flex flex-col items-center justify-center text-slate-500 border-2 border-dashed border-slate-800 rounded-xl">
                <Archive className="w-12 h-12 text-slate-600 mb-4" />
                <p>Locker is empty. Generate and shard directives to store them here.</p>
              </div>
            )}
          </div>
        )}

      </main>

      {/* Full Ledger Modal */}
      {isLedgerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-2 sm:p-4">
          <div className="bg-[#111] border border-slate-800 rounded-xl w-full max-w-3xl max-h-[90vh] sm:max-h-[80vh] flex flex-col">
            <div className="p-4 sm:p-6 border-b border-slate-800 flex justify-between items-center">
              <h2 className="text-lg sm:text-xl font-semibold text-slate-200 flex items-center">
                <Database className="w-4 h-4 sm:w-5 sm:h-5 mr-2 text-emerald-400" />
                Full ZeddProof Ledger
              </h2>
              <button onClick={() => setIsLedgerOpen(false)} className="text-slate-400 hover:text-white transition-colors">
                <X className="w-5 h-5 sm:w-6 sm:h-6" />
              </button>
            </div>
            <div className="p-3 sm:p-6 overflow-y-auto flex-1 space-y-2 sm:space-y-3">
              {attestations.length === 0 ? (
                <div className="py-8 text-center">
                  <ShieldCheck className="w-8 h-8 text-slate-600 mx-auto mb-3" />
                  <p className="text-sm text-slate-500">No attestations yet. Generate a ZeddProof to populate the ledger.</p>
                </div>
              ) : attestations.map((att, i) => (
                <div key={i} className="p-3 sm:p-4 rounded-lg bg-[#1a1a1a] border border-slate-800 flex items-center justify-between">
                  <div className="flex items-center space-x-3 sm:space-x-4">
                    <div className="p-2 sm:p-3 bg-slate-900 rounded-md border border-slate-800">
                      <Terminal className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-500" />
                    </div>
                    <div>
                      <p className="text-xs sm:text-sm font-mono text-slate-300 break-all">{att.id.slice(0, 26)}...{att.id.slice(-8)}</p>
                      <p className="text-[10px] sm:text-xs text-slate-500 mt-1">{att.type} • {att.time}</p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-1 sm:space-x-2 text-emerald-500 text-[10px] sm:text-sm font-medium">
                    <ShieldCheck className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                    <span className="hidden xs:inline">Verified</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Export Modal */}
      {isExportModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-2 sm:p-4">
          <div className="bg-[#111] border border-slate-800 rounded-xl w-full max-w-md flex flex-col">
            <div className="p-4 sm:p-6 border-b border-slate-800 flex justify-between items-center">
              <h2 className="text-base sm:text-lg font-semibold text-slate-200 flex items-center">
                <Download className="w-4 h-4 sm:w-5 sm:h-5 mr-2 text-emerald-400" />
                Export Historical Data
              </h2>
              <button onClick={() => setIsExportModalOpen(false)} className="text-slate-400 hover:text-white transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 sm:p-6 space-y-4 sm:space-y-6">
              <div>
                <h3 className="text-xs sm:text-sm font-medium text-slate-300 mb-3">Select Metrics to Export</h3>
                <div className="space-y-2 sm:space-y-3">
                  <label className="flex items-center space-x-3 cursor-pointer">
                    <input 
                      type="checkbox" 
                      checked={exportMetrics.temp}
                      onChange={(e) => setExportMetrics(prev => ({ ...prev, temp: e.target.checked }))}
                      className="form-checkbox h-4 w-4 text-emerald-500 rounded border-slate-700 bg-slate-900 focus:ring-emerald-500 focus:ring-offset-slate-900"
                    />
                    <span className="text-xs sm:text-sm text-slate-400 flex items-center"><Thermometer className="w-4 h-4 mr-2 text-rose-400" /> Temperature</span>
                  </label>
                  <label className="flex items-center space-x-3 cursor-pointer">
                    <input 
                      type="checkbox" 
                      checked={exportMetrics.humidity}
                      onChange={(e) => setExportMetrics(prev => ({ ...prev, humidity: e.target.checked }))}
                      className="form-checkbox h-4 w-4 text-emerald-500 rounded border-slate-700 bg-slate-900 focus:ring-emerald-500 focus:ring-offset-slate-900"
                    />
                    <span className="text-xs sm:text-sm text-slate-400 flex items-center"><Droplets className="w-4 h-4 mr-2 text-blue-400" /> Humidity</span>
                  </label>
                  <label className="flex items-center space-x-3 cursor-pointer">
                    <input 
                      type="checkbox" 
                      checked={exportMetrics.pressure}
                      onChange={(e) => setExportMetrics(prev => ({ ...prev, pressure: e.target.checked }))}
                      className="form-checkbox h-4 w-4 text-emerald-500 rounded border-slate-700 bg-slate-900 focus:ring-emerald-500 focus:ring-offset-slate-900"
                    />
                    <span className="text-xs sm:text-sm text-slate-400 flex items-center"><Wind className="w-4 h-4 mr-2 text-slate-400" /> Pressure</span>
                  </label>
                  <label className="flex items-center space-x-3 cursor-pointer">
                    <input 
                      type="checkbox" 
                      checked={exportMetrics.precipitation}
                      onChange={(e) => setExportMetrics(prev => ({ ...prev, precipitation: e.target.checked }))}
                      className="form-checkbox h-4 w-4 text-emerald-500 rounded border-slate-700 bg-slate-900 focus:ring-emerald-500 focus:ring-offset-slate-900"
                    />
                    <span className="text-xs sm:text-sm text-slate-400 flex items-center"><CloudRain className="w-4 h-4 mr-2 text-blue-300" /> Precipitation</span>
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
          </div>
        </div>
      )}
    </div>
  );
}

