/**
 * Metrics.js
 *
 * Evaluation logic for the RAG pipeline using the RAG Triad:
 *   1. Context Relevance  – Are the retrieved documents relevant to the query?
 *   2. Groundedness        – Is the LLM's answer grounded in the retrieved context?
 *   3. Answer Relevance    – Does the answer actually address the user's question?
 *
 * These metrics allow construction companies to quantify the quality of the
 * Decision Support System's outputs and track safety performance over time.
 */

/**
 * @typedef {Object} EvalInput
 * @property {string}   query           The original user question / weather context.
 * @property {string[]} retrievedDocs   The text of retrieved document chunks.
 * @property {string}   generatedAnswer The LLM-generated reasoning / decision.
 */

/**
 * @typedef {Object} TriadScores
 * @property {number} contextRelevance   0 – 1
 * @property {number} groundedness       0 – 1
 * @property {number} answerRelevance    0 – 1
 * @property {number} overall            Weighted average
 * @property {string} grade              'A' | 'B' | 'C' | 'D' | 'F'
 */

/**
 * @typedef {Object} MetricDetail
 * @property {number}   score     0 – 1
 * @property {string}   rationale Brief explanation of the score.
 * @property {string[]} evidence  Supporting evidence snippets.
 */

// ---------------------------------------------------------------------------
// Weights for the overall score
// ---------------------------------------------------------------------------
const WEIGHTS = {
  contextRelevance: 0.3,
  groundedness: 0.4,
  answerRelevance: 0.3,
};

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Compute all three RAG Triad metrics for a single pipeline invocation.
 *
 * This is a lightweight, heuristic-based implementation suitable for
 * client-side execution.  For production evaluation at scale, replace
 * with calls to an evaluation LLM (e.g. GPT-4o as judge).
 *
 * @param {EvalInput} input
 * @returns {TriadScores}
 */
export function evaluateTriad(input) {
  const cr = measureContextRelevance(input);
  const gr = measureGroundedness(input);
  const ar = measureAnswerRelevance(input);

  const overall =
    WEIGHTS.contextRelevance * cr.score +
    WEIGHTS.groundedness * gr.score +
    WEIGHTS.answerRelevance * ar.score;

  return {
    contextRelevance: cr.score,
    groundedness: gr.score,
    answerRelevance: ar.score,
    overall,
    grade: scoreToGrade(overall),
    details: { contextRelevance: cr, groundedness: gr, answerRelevance: ar },
  };
}

/**
 * Record a pipeline evaluation to the metrics history.
 * Stored in localStorage so it persists across sessions for site managers.
 *
 * @param {string}      pipelineRunId  Unique ID for this pipeline run.
 * @param {TriadScores} scores
 */
export function recordEvaluation(pipelineRunId, scores) {
  const STORAGE_KEY = 'zedd_rag_eval_history';
  const existing = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]');

  existing.push({
    id: pipelineRunId,
    timestamp: new Date().toISOString(),
    ...scores,
  });

  // Keep last 100 evaluations
  const trimmed = existing.length > 100 ? existing.slice(-100) : existing;

  localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
}

/**
 * Retrieve the evaluation history.
 *
 * @returns {{ id: string, timestamp: string, overall: number, grade: string }[]}
 */
export function getEvaluationHistory() {
  const STORAGE_KEY = 'zedd_rag_eval_history';
  return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]');
}

/**
 * Compute aggregate statistics over the evaluation history.
 *
 * @returns {{ count: number, avgOverall: number, avgContextRelevance: number,
 *             avgGroundedness: number, avgAnswerRelevance: number }}
 */
export function getAggregateStats() {
  const history = getEvaluationHistory();
  if (history.length === 0) {
    return {
      count: 0,
      avgOverall: 0,
      avgContextRelevance: 0,
      avgGroundedness: 0,
      avgAnswerRelevance: 0,
    };
  }

  const sum = (key) => history.reduce((acc, h) => acc + (h[key] ?? 0), 0);
  const n = history.length;

  return {
    count: n,
    avgOverall: sum('overall') / n,
    avgContextRelevance: sum('contextRelevance') / n,
    avgGroundedness: sum('groundedness') / n,
    avgAnswerRelevance: sum('answerRelevance') / n,
  };
}

// ---------------------------------------------------------------------------
// Individual metric implementations (heuristic-based)
// ---------------------------------------------------------------------------

/**
 * Context Relevance: Do the retrieved documents relate to the query?
 *
 * Measured by keyword overlap between the query and retrieved docs.
 * @param {EvalInput} input
 * @returns {MetricDetail}
 */
function measureContextRelevance(input) {
  const queryTokens = tokenize(input.query);
  const evidence = [];
  let totalOverlap = 0;

  for (const doc of input.retrievedDocs) {
    const docTokens = new Set(tokenize(doc));
    const overlap = queryTokens.filter((t) => docTokens.has(t));
    const ratio = queryTokens.length > 0 ? overlap.length / queryTokens.length : 0;
    totalOverlap += ratio;
    if (overlap.length > 0) {
      evidence.push(
        `Matched ${overlap.length}/${queryTokens.length} query terms in doc`,
      );
    }
  }

  const score = input.retrievedDocs.length > 0
    ? Math.min(totalOverlap / input.retrievedDocs.length, 1)
    : 0;

  return {
    score,
    rationale: score > 0.6
      ? 'Retrieved documents are highly relevant to the query.'
      : score > 0.3
        ? 'Some relevant content was retrieved, but coverage is partial.'
        : 'Low relevance — retrieval may need tuning.',
    evidence,
  };
}

/**
 * Groundedness: Is the generated answer supported by the retrieved context?
 *
 * Measured by checking how many key claims in the answer appear in the
 * retrieved documents.
 * @param {EvalInput} input
 * @returns {MetricDetail}
 */
function measureGroundedness(input) {
  const answerSentences = input.generatedAnswer
    .split(/[.!?]\s+/)
    .filter((s) => s.trim().length > 10);

  const allDocText = input.retrievedDocs.join(' ').toLowerCase();
  const evidence = [];
  let groundedCount = 0;

  for (const sentence of answerSentences) {
    const tokens = tokenize(sentence);
    const matchCount = tokens.filter((t) => allDocText.includes(t)).length;
    const ratio = tokens.length > 0 ? matchCount / tokens.length : 0;
    if (ratio > 0.3) {
      groundedCount++;
      evidence.push(`Grounded: "${sentence.slice(0, 60)}…"`);
    }
  }

  const score =
    answerSentences.length > 0 ? groundedCount / answerSentences.length : 0;

  return {
    score,
    rationale: score > 0.7
      ? 'Answer is well-grounded in retrieved context.'
      : score > 0.4
        ? 'Partially grounded — some claims lack supporting evidence.'
        : 'Low groundedness — answer may contain hallucinated content.',
    evidence,
  };
}

/**
 * Answer Relevance: Does the answer address the original query?
 *
 * Measured by checking token overlap between the query and the answer.
 * @param {EvalInput} input
 * @returns {MetricDetail}
 */
function measureAnswerRelevance(input) {
  const queryTokens = tokenize(input.query);
  const answerTokens = new Set(tokenize(input.generatedAnswer));
  const evidence = [];

  const matched = queryTokens.filter((t) => answerTokens.has(t));
  const score = queryTokens.length > 0 ? matched.length / queryTokens.length : 0;

  if (matched.length > 0) {
    evidence.push(`Answer addresses ${matched.length}/${queryTokens.length} query terms`);
  }

  return {
    score: Math.min(score, 1),
    rationale: score > 0.6
      ? 'Answer directly addresses the query.'
      : score > 0.3
        ? 'Answer partially addresses the query.'
        : 'Answer may not address the original query.',
    evidence,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STOP_WORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
  'could', 'may', 'might', 'shall', 'can', 'to', 'of', 'in', 'for',
  'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
  'before', 'after', 'above', 'below', 'between', 'out', 'off', 'over',
  'under', 'again', 'further', 'then', 'once', 'and', 'but', 'or', 'nor',
  'not', 'so', 'if', 'than', 'too', 'very', 'just', 'that', 'this',
  'it', 'its', 'he', 'she', 'they', 'we', 'you', 'i', 'me', 'my',
]);

function tokenize(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, '')
    .split(/\s+/)
    .filter((t) => t.length > 2 && !STOP_WORDS.has(t));
}

function scoreToGrade(score) {
  if (score >= 0.9) return 'A';
  if (score >= 0.75) return 'B';
  if (score >= 0.6) return 'C';
  if (score >= 0.4) return 'D';
  return 'F';
}
