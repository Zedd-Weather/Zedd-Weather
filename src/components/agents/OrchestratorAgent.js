/**
 * OrchestratorAgent.js
 *
 * Coordinates the flow between weather data retrieval and legal/HSE document
 * retrieval.  Acts as the "conductor" of the multi-agent RAG pipeline:
 *
 *   Weather API  ──►  TaskContextAgent  ──►  LegalReasoningAgent  ──►  DecisionAgent
 *
 * Each step is asynchronous and emits progress via a callback so the UI can
 * show a streaming "reasoning trace" to the site manager.
 */

/**
 * @typedef {Object} OrchestratorInput
 * @property {{ temperature: number, windSpeed: number, windGusts: number,
 *              precipitation: number, humidity: number, pressure: number,
 *              visibility: number, uvIndex: number }} weather
 * @property {{ activity: string, location: string, startTime: string,
 *              workerCount: number, equipmentList: string[] }} plannedWork
 */

/**
 * @typedef {Object} OrchestratorResult
 * @property {'Green'|'Amber'|'Red'} status
 * @property {string} summary
 * @property {import('./TaskContextAgent').TaskConstraints} constraints
 * @property {import('./LegalReasoningAgent').LegalReasoning} legalReasoning
 * @property {import('./DecisionAgent').Decision} decision
 * @property {{ step: string, durationMs: number }[]} trace
 */

/**
 * @callback ProgressCallback
 * @param {string} step  Human-readable description of the current step.
 * @param {number} pct   Approximate progress 0–100.
 */

import { identifyConstraints } from './TaskContextAgent';
import { applyLegalReasoning } from './LegalReasoningAgent';
import { makeDecision } from './DecisionAgent';

/**
 * Run the full orchestration pipeline.
 *
 * @param {OrchestratorInput}  input      Weather + planned-work payload.
 * @param {ProgressCallback}   [onProgress] Optional progress callback.
 * @returns {Promise<OrchestratorResult>}
 */
export async function orchestrate(input, onProgress) {
  const trace = [];
  const tick = (step) => {
    const entry = { step, startedAt: Date.now(), durationMs: 0 };
    trace.push(entry);
    return entry;
  };

  // Step 1 – Identify task constraints
  onProgress?.('Analysing planned work inputs…', 10);
  const t1 = tick('TaskContextAgent');
  const constraints = identifyConstraints(input.weather, input.plannedWork);
  t1.durationMs = Date.now() - t1.startedAt;

  // Step 2 – Retrieve & apply legal reasoning
  onProgress?.('Retrieving UK legislation and HSE guidance…', 40);
  const t2 = tick('LegalReasoningAgent');
  const legalReasoning = await applyLegalReasoning(
    input.weather,
    constraints,
  );
  t2.durationMs = Date.now() - t2.startedAt;

  // Step 3 – Produce decision
  onProgress?.('Computing risk decision…', 80);
  const t3 = tick('DecisionAgent');
  const decision = makeDecision(constraints, legalReasoning);
  t3.durationMs = Date.now() - t3.startedAt;

  onProgress?.('Pipeline complete.', 100);

  return {
    status: decision.status,
    summary: decision.explanation,
    constraints,
    legalReasoning,
    decision,
    trace: trace.map((t) => ({ step: t.step, durationMs: t.durationMs })),
  };
}
