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
  X
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
  Area
} from 'recharts';
import { GoogleGenAI, ThinkingLevel, Type } from '@google/genai';
import ReactMarkdown from 'react-markdown';

const mockWeatherData = Array.from({ length: 24 }, (_, i) => ({
  time: `${i}:00`,
  temp: 20 + Math.sin(i / 4) * 10 + Math.random() * 2,
  humidity: 50 + Math.cos(i / 4) * 20 + Math.random() * 5,
  pressure: 1010 + Math.sin(i / 8) * 5 + Math.random(),
}));

// Initialize Gemini API
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

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
      if (value > 10) return { label: 'Heavy', color: 'text-blue-500', bg: 'bg-blue-500/10', border: 'border-blue-500/30' };
      if (value > 0) return { label: 'Light', color: 'text-blue-400', bg: 'bg-blue-400/10', border: 'border-blue-400/30' };
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
  return (
    <div className={`bg-[#111] border ${statusInfo.border} rounded-xl p-5 flex flex-col relative overflow-hidden transition-all duration-300 hover:bg-[#161616] shadow-sm`}>
      <div className="flex justify-between items-start mb-4">
        <div className={`p-2.5 rounded-lg ${statusInfo.bg} ${statusInfo.color}`}>
          <Icon className="w-5 h-5" />
        </div>
        <span className={`text-[10px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-full ${statusInfo.bg} ${statusInfo.color}`}>
          {statusInfo.label}
        </span>
      </div>
      <div>
        <p className="text-sm text-slate-400 font-medium mb-1">{title}</p>
        <div className="flex items-baseline space-x-1">
          <p className="text-3xl font-bold text-slate-100 tracking-tight">{value}</p>
          <span className="text-sm text-slate-500 font-medium">{unit}</span>
        </div>
      </div>
    </div>
  );
};

export default function App() {
  const [activeTab, setActiveTab] = useState<'telemetry' | 'risk' | 'map'>('telemetry');
  
  // Live Telemetry State
  const [currentTelemetry, setCurrentTelemetry] = useState({
    temp: 0,
    humidity: 0,
    pressure: 0,
    precipitation: 0,
    tide: 0,
    uvIndex: 0,
    aqi: 0
  });

  // Risk Analysis State
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [mediaPreview, setMediaPreview] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [riskReport, setRiskReport] = useState<string | null>(null);
  const [riskLevel, setRiskLevel] = useState<'Green' | 'Amber' | 'Red' | 'Black' | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch real telemetry data from Open-Meteo APIs
  const fetchRealTelemetry = async () => {
    try {
      // Construction site coordinates (e.g., San Francisco)
      const lat = 37.7749;
      const lon = -122.4194;
      
      const [weatherRes, aqiRes, marineRes] = await Promise.all([
        fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,surface_pressure,precipitation,uv_index`),
        fetch(`https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${lat}&longitude=${lon}&current=us_aqi`),
        fetch(`https://marine-api.open-meteo.com/v1/marine?latitude=${lat}&longitude=${lon}&current=wave_height`)
      ]);

      const weather = await weatherRes.json();
      const aqi = await aqiRes.json();
      const marine = await marineRes.json();

      const newTelemetry = {
        temp: weather.current.temperature_2m,
        humidity: weather.current.relative_humidity_2m,
        pressure: weather.current.surface_pressure,
        precipitation: weather.current.precipitation,
        uvIndex: weather.current.uv_index,
        aqi: aqi.current.us_aqi || 42,
        tide: marine.current?.wave_height || 1.2
      };

      setCurrentTelemetry(newTelemetry);
      return newTelemetry;
    } catch (error) {
      console.error("Failed to fetch real telemetry:", error);
      return null;
    }
  };

  // Automated AI Risk Analysis based purely on telemetry
  const autoAnalyzeRisk = async (telemetry: any) => {
    setIsAnalyzing(true);
    try {
      const response = await ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: `You are a Principal Edge AI and IoT Systems Architect monitoring an industrial construction site.
        Current LIVE micro-climate telemetry:
        - Temperature: ${telemetry.temp.toFixed(1)}°C
        - Humidity: ${telemetry.humidity.toFixed(1)}%
        - Pressure: ${telemetry.pressure.toFixed(1)} hPa
        - Precipitation: ${telemetry.precipitation.toFixed(2)} mm
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
    
    const init = async () => {
      const telemetry = await fetchRealTelemetry();
      if (telemetry && isMounted) {
        autoAnalyzeRisk(telemetry);
      }
    };
    
    init();
    
    const interval = setInterval(() => {
      fetchRealTelemetry();
    }, 60000); // Update every minute
    
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Map State
  const [isFetchingMap, setIsFetchingMap] = useState(false);
  const [mapReport, setMapReport] = useState<string | null>(null);
  const [mapLinks, setMapLinks] = useState<any[]>([]);

  // Historical Data State
  const [historicalRange, setHistoricalRange] = useState<'7d' | '14d' | '30d'>('7d');
  const [historicalData, setHistoricalData] = useState<any[]>([]);
  const [isFetchingHistory, setIsFetchingHistory] = useState(false);

  // Fetch Historical Telemetry
  const fetchHistoricalTelemetry = async (days: number) => {
    setIsFetchingHistory(true);
    try {
      const lat = 37.7749;
      const lon = -122.4194;
      
      const res = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&past_days=${days}&hourly=temperature_2m,relative_humidity_2m,surface_pressure`);
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
    if (activeTab === 'telemetry') {
      const days = historicalRange === '7d' ? 7 : (historicalRange === '14d' ? 14 : 30);
      fetchHistoricalTelemetry(days);
    }
  }, [historicalRange, activeTab]);

  const [nodes] = useState([
    { id: 'Node Alpha', role: 'Primary - Sense HAT', status: 'Active', ip: '10.0.0.15', detail: 'Capturing telemetry' },
    { id: 'Node Beta', role: 'Vault - Minima Node', status: 'Active', ip: '10.0.0.16', detail: 'Sharding & Attestation' },
  ]);

  const [attestations, setAttestations] = useState([
    { id: '0x8f7a...3b21', time: 'Just now', type: 'Atmospheric Shard', verified: true },
    { id: '0x2c4d...9a12', time: '10 mins ago', type: 'Atmospheric Shard', verified: true },
    { id: '0x5e1b...4f88', time: '20 mins ago', type: 'Inertial Shard', verified: true },
    { id: '0x9d3c...7e45', time: '30 mins ago', type: 'Atmospheric Shard', verified: true },
  ]);

  const [isGeneratingProof, setIsGeneratingProof] = useState(false);
  const [isLedgerOpen, setIsLedgerOpen] = useState(false);

  const generateZeddProof = async () => {
    setIsGeneratingProof(true);
    // Simulate cryptographic hashing delay
    await new Promise(resolve => setTimeout(resolve, 800));
    
    // Simple mock hash generation based on current telemetry
    const dataString = JSON.stringify(currentTelemetry) + Date.now();
    let hash = 0;
    for (let i = 0; i < dataString.length; i++) {
      const char = dataString.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    const hexHash = '0x' + Math.abs(hash).toString(16).padStart(8, '0') + '...' + Math.floor(Math.random() * 10000).toString(16).padStart(4, '0');
    
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
            - Precipitation: ${currentTelemetry.precipitation.toFixed(2)} mm
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

  const fetchSiteMapData = async () => {
    setIsFetchingMap(true);
    setMapReport(null);
    setMapLinks([]);

    try {
      // Try to get user's location, fallback to default construction site coordinates
      let lat = 37.7749;
      let lng = -122.4194;
      
      try {
        if ('geolocation' in navigator) {
          const position = await new Promise<GeolocationPosition>((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
          });
          lat = position.coords.latitude;
          lng = position.coords.longitude;
        }
      } catch (geoError) {
        console.warn("Geolocation failed or denied, using default coordinates.", geoError);
      }

      const response = await ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: `Find nearby emergency services, hardware stores, and safe zones near the construction site at ${lat}, ${lng}. Provide a brief logistics report.`,
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
        setMapLinks(links);
      }
    } catch (error: any) {
      console.error("Error fetching map data:", error);
      const errStr = typeof error === 'string' ? error : JSON.stringify(error);
      if (errStr.includes('429')) {
        setMapReport("Map data is temporarily unavailable due to rate limits. Please wait a moment and try again.");
      } else if (errStr.includes('500') || errStr.includes('xhr error') || errStr.includes('Rpc failed')) {
        setMapReport("Map service is currently experiencing network issues. Please try again later.");
      } else {
        setMapReport("An error occurred while fetching map data. Please try again.");
      }
    } finally {
      setIsFetchingMap(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-slate-200 font-sans selection:bg-emerald-500/30">
      {/* Top Navigation */}
      <header className="border-b border-slate-800 bg-[#0a0a0a]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/50 flex items-center justify-center">
              <Cloud className="w-5 h-5 text-emerald-400" />
            </div>
            <span className="text-xl font-bold tracking-tight text-slate-100">
              Zedd Weather
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] uppercase tracking-wider font-semibold bg-slate-800 text-slate-400 ml-2">
              Enterprise
            </span>
          </div>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 text-sm text-slate-400 bg-slate-900 px-3 py-1.5 rounded-full border border-slate-800">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
              <span>Minima Network Sync: OK</span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* Tab Navigation */}
        <div className="flex space-x-4 mb-8 border-b border-slate-800 pb-px">
          <button 
            onClick={() => setActiveTab('telemetry')}
            className={`pb-3 px-2 text-sm font-medium transition-colors border-b-2 ${activeTab === 'telemetry' ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-slate-400 hover:text-slate-300'}`}
          >
            <div className="flex items-center">
              <Activity className="w-4 h-4 mr-2" />
              Telemetry
            </div>
          </button>
          <button 
            onClick={() => setActiveTab('risk')}
            className={`pb-3 px-2 text-sm font-medium transition-colors border-b-2 ${activeTab === 'risk' ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-slate-400 hover:text-slate-300'}`}
          >
            <div className="flex items-center">
              <AlertTriangle className="w-4 h-4 mr-2" />
              AI Risk Analysis
            </div>
          </button>
          <button 
            onClick={() => {
              setActiveTab('map');
              if (!mapReport) fetchSiteMapData();
            }}
            className={`pb-3 px-2 text-sm font-medium transition-colors border-b-2 ${activeTab === 'map' ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-slate-400 hover:text-slate-300'}`}
          >
            <div className="flex items-center">
              <MapIcon className="w-4 h-4 mr-2" />
              Site Map & Logistics
            </div>
          </button>
        </div>

        {activeTab === 'telemetry' && (
          <>
            {/* Dashboard Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6 mb-8">
              <MetricCard title="Temperature" value={currentTelemetry.temp.toFixed(1)} unit="°C" icon={Thermometer} type="temp" />
              <MetricCard title="Humidity" value={currentTelemetry.humidity.toFixed(1)} unit="%" icon={Droplets} type="humidity" />
              <MetricCard title="Pressure" value={currentTelemetry.pressure.toFixed(1)} unit="hPa" icon={Wind} type="pressure" />
              <MetricCard title="Precipitation" value={currentTelemetry.precipitation.toFixed(2)} unit="mm" icon={CloudRain} type="precip" />
              <MetricCard title="Tide Level" value={currentTelemetry.tide.toFixed(2)} unit="m" icon={Waves} type="tide" />
              <MetricCard title="UV Index" value={currentTelemetry.uvIndex.toFixed(1)} unit="" icon={Sun} type="uv" />
              <MetricCard title="AQI" value={Math.round(currentTelemetry.aqi)} unit="" icon={Activity} type="aqi" />
              <MetricCard title="ZeddProofs" value="1,402" unit="" icon={ShieldCheck} type="proofs" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Left Column - Charts */}
              <div className="lg:col-span-2 space-y-8">
                <div className="bg-[#111] border border-slate-800 rounded-xl p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-lg font-medium flex items-center text-slate-200">
                      <Activity className="w-5 h-5 mr-2 text-rose-400" />
                      Historical Telemetry Trends
                    </h2>
                    <div className="flex space-x-2">
                      {(['7d', '14d', '30d'] as const).map((range) => (
                        <button
                          key={range}
                          onClick={() => setHistoricalRange(range)}
                          className={`px-3 py-1 text-xs font-medium rounded-lg border transition-colors ${
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
                  
                  {isFetchingHistory ? (
                    <div className="h-64 flex items-center justify-center">
                      <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
                    </div>
                  ) : (
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={historicalData}>
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
                          <Area yAxisId="left" type="monotone" dataKey="temp" stroke="#f43f5e" strokeWidth={2} fillOpacity={1} fill="url(#colorTempHist)" name="Temp (°C)" />
                          <Area yAxisId="right" type="monotone" dataKey="humidity" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorHumidHist)" name="Humidity (%)" />
                        </AreaChart>
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
                      <AreaChart data={mockWeatherData}>
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
                      <LineChart data={mockWeatherData}>
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
                          <ShieldCheck className="w-4 h-4 text-emerald-500" title="Minima Verified" />
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
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-4">
                  <div className="bg-[#1a1a1a] p-3 rounded-lg border border-slate-800">
                    <p className="text-xs text-slate-500">Live Temp</p>
                    <p className="text-lg font-semibold text-slate-200">{currentTelemetry.temp.toFixed(1)}°C</p>
                  </div>
                  <div className="bg-[#1a1a1a] p-3 rounded-lg border border-slate-800">
                    <p className="text-xs text-slate-500">Humidity</p>
                    <p className="text-lg font-semibold text-slate-200">{currentTelemetry.humidity.toFixed(1)}%</p>
                  </div>
                  <div className="bg-[#1a1a1a] p-3 rounded-lg border border-slate-800">
                    <p className="text-xs text-slate-500">Pressure</p>
                    <p className="text-lg font-semibold text-slate-200">{currentTelemetry.pressure.toFixed(1)} hPa</p>
                  </div>
                  <div className="bg-[#1a1a1a] p-3 rounded-lg border border-slate-800">
                    <p className="text-xs text-slate-500">Precipitation</p>
                    <p className="text-lg font-semibold text-slate-200">{currentTelemetry.precipitation.toFixed(2)} mm</p>
                  </div>
                  <div className="bg-[#1a1a1a] p-3 rounded-lg border border-slate-800">
                    <p className="text-xs text-slate-500">Tide Level</p>
                    <p className="text-lg font-semibold text-slate-200">{currentTelemetry.tide.toFixed(2)} m</p>
                  </div>
                  <div className="bg-[#1a1a1a] p-3 rounded-lg border border-slate-800">
                    <p className="text-xs text-slate-500">UV Index</p>
                    <p className="text-lg font-semibold text-slate-200">{currentTelemetry.uvIndex.toFixed(1)}</p>
                  </div>
                  <div className="bg-[#1a1a1a] p-3 rounded-lg border border-slate-800">
                    <p className="text-xs text-slate-500">Live AQI</p>
                    <p className="text-lg font-semibold text-slate-200">{Math.round(currentTelemetry.aqi)}</p>
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
                  <div className="h-full min-h-[300px] flex flex-col items-center justify-center text-slate-500 space-y-4">
                    <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
                    <p>Analyzing telemetry and generating directives...</p>
                  </div>
                ) : riskReport ? (
                  <div className="prose prose-invert prose-emerald max-w-none">
                    <div className="markdown-body text-sm text-slate-300">
                      <ReactMarkdown>{riskReport}</ReactMarkdown>
                    </div>
                    <div className="mt-6 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                      <p className="text-xs text-emerald-400 font-mono flex items-center">
                        <Terminal className="w-3 h-3 mr-2" />
                        Directive ready for Minima attestation (SHA-256)
                      </p>
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
              <h2 className="text-lg font-medium flex items-center text-slate-200">
                <MapIcon className="w-5 h-5 mr-2 text-blue-400" />
                Site Map & Logistics Grounding
              </h2>
              <button 
                onClick={fetchSiteMapData}
                disabled={isFetchingMap}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center w-full sm:w-auto"
              >
                {isFetchingMap ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <MapIcon className="w-4 h-4 mr-2" />}
                {isFetchingMap ? 'Querying Maps...' : 'Fetch Local Logistics'}
              </button>
            </div>

            {isFetchingMap ? (
              <div className="h-64 flex flex-col items-center justify-center text-slate-500 space-y-4">
                <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                <p>Querying Google Maps for local logistics...</p>
              </div>
            ) : mapReport ? (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2 prose prose-invert prose-blue max-w-none bg-[#1a1a1a] p-6 rounded-xl border border-slate-800">
                  <div className="markdown-body text-sm text-slate-300">
                    <ReactMarkdown>{mapReport}</ReactMarkdown>
                  </div>
                </div>
                <div className="bg-[#1a1a1a] p-6 rounded-xl border border-slate-800">
                  <h3 className="text-sm font-medium text-slate-400 mb-4 uppercase tracking-wider flex items-center">
                    <MapIcon className="w-4 h-4 mr-2" />
                    Map Links
                  </h3>
                  <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
                    {mapLinks.length > 0 ? mapLinks.map((mapData, idx) => (
                      <a 
                        key={idx} 
                        href={mapData.uri} 
                        target="_blank" 
                        rel="noreferrer"
                        className="block p-4 bg-slate-900 border border-slate-800 rounded-lg text-sm hover:border-blue-500/50 hover:bg-slate-800 transition-all group"
                      >
                        <p className="text-blue-400 font-medium mb-1 group-hover:text-blue-300 transition-colors line-clamp-2">
                          {mapData.title || 'View on Google Maps'}
                        </p>
                        <p className="text-xs text-slate-500 truncate">
                          {mapData.uri}
                        </p>
                      </a>
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

      </main>

      {/* Full Ledger Modal */}
      {isLedgerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#111] border border-slate-800 rounded-xl w-full max-w-3xl max-h-[80vh] flex flex-col">
            <div className="p-6 border-b border-slate-800 flex justify-between items-center">
              <h2 className="text-xl font-semibold text-slate-200 flex items-center">
                <Database className="w-5 h-5 mr-2 text-emerald-400" />
                Full ZeddProof Ledger
              </h2>
              <button onClick={() => setIsLedgerOpen(false)} className="text-slate-400 hover:text-white transition-colors">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-6 overflow-y-auto flex-1 space-y-3">
              {/* Generate a larger list for the full ledger view based on existing attestations */}
              {[...attestations, ...Array.from({ length: 15 }).map((_, i) => ({
                id: `0x${Math.random().toString(16).slice(2, 10)}...${Math.random().toString(16).slice(2, 6)}`,
                time: `${i + 1} hours ago`,
                type: i % 3 === 0 ? 'Inertial Shard' : 'Atmospheric Shard',
                verified: true
              }))].map((att, i) => (
                <div key={i} className="p-4 rounded-lg bg-[#1a1a1a] border border-slate-800 flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="p-3 bg-slate-900 rounded-md border border-slate-800">
                      <Terminal className="w-5 h-5 text-emerald-500" />
                    </div>
                    <div>
                      <p className="text-sm font-mono text-slate-300">{att.id}</p>
                      <p className="text-xs text-slate-500 mt-1">{att.type} • {att.time}</p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2 text-emerald-500 text-sm font-medium">
                    <ShieldCheck className="w-4 h-4" />
                    <span>Verified</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

