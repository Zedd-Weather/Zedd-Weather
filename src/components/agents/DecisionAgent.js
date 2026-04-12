/**
 * DecisionAgent.js
 *
 * Consumes the output of TaskContextAgent and LegalReasoningAgent to produce
 * a final Green / Amber / Red status decision with a human-readable explanation.
 */

/**
 * @typedef {Object} Decision
 * @property {'Green'|'Amber'|'Red'} status
 * @property {string}                explanation
 * @property {string[]}              actions       Immediate actions required.
 * @property {string}                reviewTime    ISO-8601 recommended next review time.
 * @property {number}                confidence    0 – 1 confidence in the decision.
 */

/**
 * Produce a Green / Amber / Red decision.
 *
 * @param {import('./TaskContextAgent').TaskConstraints}     constraints
 * @param {import('./LegalReasoningAgent').LegalReasoning}   legalReasoning
 * @returns {Decision}
 */
export function makeDecision(constraints, legalReasoning) {
  const { haltReasons, cautionReasons, riskBand } = constraints;
  const { complianceStatus, mitigations, complianceGaps } = legalReasoning;

  // -----------------------------------------------------------------------
  // Status matrix
  // -----------------------------------------------------------------------
  let status = 'Green';
  let confidence = 0.95;

  if (
    riskBand === 'critical' ||
    complianceStatus === 'non-compliant' ||
    haltReasons.length > 0
  ) {
    status = 'Red';
    confidence = 0.9;
  } else if (
    riskBand === 'high' ||
    complianceStatus === 'partial' ||
    cautionReasons.length >= 2
  ) {
    status = 'Amber';
    confidence = 0.85;
  } else if (cautionReasons.length === 1) {
    status = 'Amber';
    confidence = 0.88;
  }

  // -----------------------------------------------------------------------
  // Explanation
  // -----------------------------------------------------------------------
  const parts = [];

  if (status === 'Red') {
    parts.push(
      `🔴 **RED — Work Must Not Proceed**`,
      '',
      `${haltReasons.length} halt condition(s) detected:`,
      ...haltReasons.map((r) => `  • ${r}`),
    );
    if (complianceGaps.length > 0) {
      parts.push('', 'Compliance gaps:');
      parts.push(...complianceGaps.map((g) => `  ⚠ ${g}`));
    }
  } else if (status === 'Amber') {
    parts.push(
      `🟡 **AMBER — Proceed With Additional Controls**`,
      '',
      `${cautionReasons.length} caution flag(s):`,
      ...cautionReasons.map((r) => `  • ${r}`),
    );
  } else {
    parts.push(
      `🟢 **GREEN — Safe to Proceed**`,
      '',
      'All weather parameters are within safe operating limits.',
    );
  }

  // Mitigation controls
  if (mitigations.length > 0) {
    parts.push('', '**Required Mitigation Controls:**');
    parts.push(...mitigations.map((m, i) => `  ${i + 1}. ${m}`));
  }

  // PPE
  if (constraints.ppeRequired?.length > 0) {
    parts.push('', '**PPE Requirements:**');
    parts.push(...constraints.ppeRequired.map((p) => `  • ${p}`));
  }

  // Legal reasoning summary
  if (legalReasoning.reasoning) {
    parts.push('', '**Legal Basis:**', legalReasoning.reasoning);
  }

  const explanation = parts.join('\n');

  // -----------------------------------------------------------------------
  // Actions
  // -----------------------------------------------------------------------
  const actions = [];
  if (status === 'Red') {
    actions.push('HALT all affected activities immediately');
    actions.push('Notify site manager and H&S officer');
    actions.push('Schedule reassessment in 1 hour');
  } else if (status === 'Amber') {
    actions.push('Implement additional controls before starting work');
    actions.push('Brief all workers on current conditions');
    actions.push('Schedule reassessment in 2 hours');
  } else {
    actions.push('Proceed with standard operating procedures');
    actions.push('Maintain routine weather monitoring');
  }

  // Next review
  const hoursUntilReview = status === 'Red' ? 1 : status === 'Amber' ? 2 : 4;
  const reviewTime = new Date(
    Date.now() + hoursUntilReview * 3600_000,
  ).toISOString();

  return {
    status,
    explanation,
    actions,
    reviewTime,
    confidence,
  };
}
