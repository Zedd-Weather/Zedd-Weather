/**
 * ConstructionDashboard.jsx
 *
 * Top-level dashboard that wires together the agentic RAG pipeline with
 * the construction weather UI.  Renders:
 *   • WeatherCard (risk summaries + mitigation controls)
 *   • Agent pipeline progress trace
 *   • Legal reasoning panel
 *   • RAG evaluation metrics
 *   • Natural-language compliance Q&A sidebar
 */
import { useState, useReducer, useCallback, useEffect } from 'react';
import {
  Activity,
  ShieldCheck,
  AlertTriangle,
  Loader2,
  MessageSquare,
  BarChart3,
  FileText,
  Send,
  Scale,
} from 'lucide-react';

import WeatherCard from './WeatherCard';
import { orchestrate } from './agents/OrchestratorAgent';
import { evaluateTriad, recordEvaluation } from '../lib/eval/Metrics';

// ---------------------------------------------------------------------------
// State management — useReducer replaces scattered useState calls
// ---------------------------------------------------------------------------

const initialState = {
  /** @type {'idle'|'running'|'done'|'error'} */
  pipelineStatus: 'idle',
  /** 0 – 100 */
  progress: 0,
  progressLabel: '',
  /** @type {import('./agents/DecisionAgent').Decision|null} */
  decision: null,
  /** @type {import('./agents/TaskContextAgent').TaskConstraints|null} */
  constraints: null,
  /** @type {import('./agents/LegalReasoningAgent').LegalReasoning|null} */
  legalReasoning: null,
  /** @type {{ step: string, durationMs: number }[]} */
  trace: [],
  /** @type {import('../lib/eval/Metrics').TriadScores|null} */
  evalScores: null,
  error: null,
  /** Natural-language Q&A */
  chatMessages: [],
  chatInput: '',
};

function reducer(state, action) {
  switch (action.type) {
    case 'PIPELINE_START':
      return {
        ...state,
        pipelineStatus: 'running',
        progress: 0,
        progressLabel: 'Starting pipeline…',
        decision: null,
        constraints: null,
        legalReasoning: null,
        trace: [],
        evalScores: null,
        error: null,
      };

    case 'PIPELINE_PROGRESS':
      return {
        ...state,
        progress: action.pct,
        progressLabel: action.label,
      };

    case 'PIPELINE_DONE':
      return {
        ...state,
        pipelineStatus: 'done',
        progress: 100,
        progressLabel: 'Pipeline complete.',
        decision: action.result.decision,
        constraints: action.result.constraints,
        legalReasoning: action.result.legalReasoning,
        trace: action.result.trace,
      };

    case 'PIPELINE_ERROR':
      return { ...state, pipelineStatus: 'error', error: action.error };

    case 'SET_EVAL':
      return { ...state, evalScores: action.scores };

    case 'SET_CHAT_INPUT':
      return { ...state, chatInput: action.value };

    case 'ADD_CHAT_MESSAGE':
      return {
        ...state,
        chatMessages: [...state.chatMessages, action.message],
      };

    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PipelineTrace({ trace }) {
  if (!trace || trace.length === 0) return null;
  return (
    <div className="mt-3 space-y-1">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">
        Agent Trace
      </p>
      {trace.map((t, i) => (
        <div
          key={i}
          className="flex items-center justify-between text-xs text-slate-400 bg-slate-900/50 px-3 py-1.5 rounded-lg border border-slate-800/60"
        >
          <span>{t.step}</span>
          <span className="text-emerald-500 font-mono">{t.durationMs} ms</span>
        </div>
      ))}
    </div>
  );
}

function LegalPanel({ legalReasoning }) {
  if (!legalReasoning) return null;

  const statusColor =
    legalReasoning.complianceStatus === 'compliant'
      ? 'text-emerald-400'
      : legalReasoning.complianceStatus === 'partial'
        ? 'text-amber-400'
        : 'text-rose-400';

  return (
    <div className="mt-4 bg-[#111] border border-slate-800 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <Scale className="w-4 h-4 text-blue-400" />
        <h4 className="text-sm font-bold text-slate-100">Legal Reasoning</h4>
        <span
          className={`ml-auto text-[10px] uppercase tracking-wider font-bold ${statusColor}`}
        >
          {legalReasoning.complianceStatus}
        </span>
      </div>

      <p className="text-xs text-slate-300 leading-relaxed mb-3">
        {legalReasoning.reasoning}
      </p>

      {/* Referenced legislation */}
      {legalReasoning.references?.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
            Cited Legislation
          </p>
          <div className="space-y-1">
            {legalReasoning.references.map((ref) => (
              <div
                key={ref.id}
                className="text-[11px] text-slate-400 bg-slate-900/50 px-2 py-1 rounded border border-slate-800/60"
              >
                <span className="text-blue-400">[{ref.id}]</span>{' '}
                {ref.title} — {ref.section}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Compliance gaps */}
      {legalReasoning.complianceGaps?.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
            Compliance Gaps
          </p>
          {legalReasoning.complianceGaps.map((gap, i) => (
            <div
              key={i}
              className="flex items-start gap-2 text-xs text-rose-300 mb-1"
            >
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
              <span>{gap}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EvalPanel({ scores }) {
  if (!scores) return null;

  const bar = (label, value) => (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-32 text-slate-400 truncate">{label}</span>
      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-emerald-500 rounded-full transition-all"
          style={{ width: `${(value * 100).toFixed(0)}%` }}
        />
      </div>
      <span className="w-10 text-right text-slate-300 font-mono">
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );

  return (
    <div className="mt-4 bg-[#111] border border-slate-800 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 className="w-4 h-4 text-violet-400" />
        <h4 className="text-sm font-bold text-slate-100">RAG Evaluation</h4>
        <span className="ml-auto text-xs font-bold text-violet-400">
          Grade: {scores.grade}
        </span>
      </div>
      <div className="space-y-2">
        {bar('Context Relevance', scores.contextRelevance)}
        {bar('Groundedness', scores.groundedness)}
        {bar('Answer Relevance', scores.answerRelevance)}
        {bar('Overall', scores.overall)}
      </div>
    </div>
  );
}

function ChatSidebar({ messages, input, onInputChange, onSend }) {
  return (
    <div className="bg-[#111] border border-slate-800 rounded-xl flex flex-col h-80 mt-4">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800">
        <MessageSquare className="w-4 h-4 text-emerald-400" />
        <h4 className="text-sm font-bold text-slate-100">
          Compliance Assistant
        </h4>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-2 space-y-2">
        {messages.length === 0 && (
          <p className="text-xs text-slate-500 text-center mt-8">
            Ask a question about weather compliance, UK legislation, or site
            safety…
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`text-xs p-2 rounded-lg max-w-[85%] ${
              msg.role === 'user'
                ? 'ml-auto bg-emerald-900/30 text-emerald-200 border border-emerald-800/40'
                : 'bg-slate-900/80 text-slate-300 border border-slate-800/60'
            }`}
          >
            {msg.content}
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="flex items-center gap-2 px-3 py-2 border-t border-slate-800">
        <input
          type="text"
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSend()}
          placeholder="Ask about compliance…"
          className="flex-1 bg-slate-900 text-xs text-slate-200 px-3 py-2 rounded-lg border border-slate-800 focus:outline-none focus:border-emerald-500/50"
        />
        <button
          onClick={onSend}
          className="p-2 rounded-lg bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30 transition-colors"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ACTIVITIES = [
  { value: 'general', label: 'General Construction' },
  { value: 'crane_operations', label: 'Crane Operations' },
  { value: 'concrete_pouring', label: 'Concrete Pouring' },
  { value: 'roofing', label: 'Roofing' },
  { value: 'excavation', label: 'Excavation' },
  { value: 'steel_erection', label: 'Steel Erection' },
  { value: 'painting', label: 'Painting / Coating' },
];

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * @param {{ weather: Object }} props  Current weather data from the telemetry layer.
 */
export default function ConstructionDashboard({ weather }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [selectedActivity, setSelectedActivity] = useState('general');

  // Run the agentic pipeline
  const runPipeline = useCallback(async () => {
    dispatch({ type: 'PIPELINE_START' });

    try {
      const result = await orchestrate(
        {
          weather: {
            temperature: weather?.temp ?? weather?.temperature ?? 0,
            windSpeed: weather?.windSpeed ?? 0,
            windGusts: weather?.windGusts ?? 0,
            precipitation: weather?.precipitation ?? 0,
            humidity: weather?.humidity ?? 0,
            pressure: weather?.pressure ?? 0,
            visibility: weather?.visibility ?? 10000,
            uvIndex: weather?.uvIndex ?? 0,
          },
          plannedWork: {
            activity: selectedActivity,
            location: 'Construction site',
            startTime: new Date().toISOString(),
            workerCount: 25,
            equipmentList: ['crane', 'excavator'],
          },
        },
        (label, pct) => dispatch({ type: 'PIPELINE_PROGRESS', label, pct }),
      );

      dispatch({ type: 'PIPELINE_DONE', result });

      // Run evaluation
      const activityLabel = ACTIVITIES.find((a) => a.value === selectedActivity)?.label ?? selectedActivity;
      const evalInput = {
        query: `Weather assessment for ${activityLabel} activity. Temperature ${weather?.temp ?? 0}°C, wind ${weather?.windSpeed ?? 0} m/s.`,
        retrievedDocs: (result.legalReasoning?.references ?? []).map(
          (r) => r.relevantText,
        ),
        generatedAnswer: result.decision?.explanation ?? '',
      };
      const scores = evaluateTriad(evalInput);
      dispatch({ type: 'SET_EVAL', scores });
      recordEvaluation(`run-${Date.now()}`, scores);
    } catch (err) {
      dispatch({ type: 'PIPELINE_ERROR', error: err.message });
    }
  }, [weather, selectedActivity]);

  // Auto-run on mount and when weather changes significantly
  useEffect(() => {
    if (weather) runPipeline();
  }, [weather?.temp, weather?.windSpeed, selectedActivity, runPipeline]);

  // Chat handler (simple echo; in production wired to LLM)
  const handleChatSend = useCallback(() => {
    if (!state.chatInput.trim()) return;

    dispatch({
      type: 'ADD_CHAT_MESSAGE',
      message: { role: 'user', content: state.chatInput },
    });

    // Generate a contextual response from the current decision
    const response = state.decision
      ? `Based on the current assessment (${state.decision.status}): ${state.decision.actions?.[0] ?? 'Continue monitoring.'}  The legal compliance status is "${state.legalReasoning?.complianceStatus ?? 'unknown'}".`
      : 'The pipeline has not run yet. Please wait for the assessment to complete.';

    dispatch({
      type: 'ADD_CHAT_MESSAGE',
      message: { role: 'assistant', content: response },
    });
    dispatch({ type: 'SET_CHAT_INPUT', value: '' });
  }, [state.chatInput, state.decision, state.legalReasoning]);

  return (
    <div className="space-y-4">
      {/* Activity selector + Run button */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-slate-400" />
          <select
            value={selectedActivity}
            onChange={(e) => setSelectedActivity(e.target.value)}
            className="bg-slate-900 text-xs text-slate-200 px-3 py-2 rounded-lg border border-slate-800 focus:outline-none focus:border-emerald-500/50"
          >
            {ACTIVITIES.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={runPipeline}
          disabled={state.pipelineStatus === 'running'}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600/20 text-emerald-400 text-xs font-semibold border border-emerald-500/30 hover:bg-emerald-600/30 transition-colors disabled:opacity-50"
        >
          {state.pipelineStatus === 'running' ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {state.progressLabel}
            </>
          ) : (
            <>
              <Activity className="w-3.5 h-3.5" />
              Run Assessment Pipeline
            </>
          )}
        </button>
      </div>

      {/* Progress bar */}
      {state.pipelineStatus === 'running' && (
        <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-500 rounded-full transition-all duration-500"
            style={{ width: `${state.progress}%` }}
          />
        </div>
      )}

      {/* Error */}
      {state.error && (
        <div className="bg-rose-900/20 border border-rose-500/30 rounded-xl p-3 text-xs text-rose-300">
          Pipeline error: {state.error}
        </div>
      )}

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <WeatherCard
            weather={weather}
            decision={state.decision}
            constraints={state.constraints}
          />
          <PipelineTrace trace={state.trace} />
          <EvalPanel scores={state.evalScores} />
        </div>
        <div>
          <LegalPanel legalReasoning={state.legalReasoning} />
          <ChatSidebar
            messages={state.chatMessages}
            input={state.chatInput}
            onInputChange={(v) =>
              dispatch({ type: 'SET_CHAT_INPUT', value: v })
            }
            onSend={handleChatSend}
          />
        </div>
      </div>
    </div>
  );
}
