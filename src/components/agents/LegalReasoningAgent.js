/**
 * LegalReasoningAgent.js
 *
 * Uses OpenAI GPT-4o (via fetch) to apply retrieved UK-legislation chunks to
 * current weather hazards.  In production this would call the DocumentIngestor's
 * query method to retrieve relevant legal text from Pinecone; for the front-end
 * build we embed a curated set of legal references so the module compiles
 * without server-side dependencies.
 *
 * Supports Server-Sent Events (SSE) streaming for progressive UI rendering.
 */

/**
 * @typedef {Object} LegalReference
 * @property {string} id
 * @property {string} title
 * @property {string} section
 * @property {string} relevantText
 * @property {number} relevanceScore  0 – 1
 */

/**
 * @typedef {Object} LegalReasoning
 * @property {LegalReference[]} references
 * @property {string}           reasoning       Full LLM-generated reasoning text.
 * @property {string[]}         mitigations     Recommended mitigation controls.
 * @property {string[]}         complianceGaps  Identified compliance gaps.
 * @property {'compliant'|'partial'|'non-compliant'} complianceStatus
 */

// ---------------------------------------------------------------------------
// Embedded legal reference catalogue (used when Pinecone is unavailable)
// ---------------------------------------------------------------------------

const LEGAL_CATALOGUE = [
  {
    id: 'cdm-2015-reg-13',
    title: 'CDM 2015 – Regulation 13',
    section: 'Duties of contractors',
    text: 'Contractors must plan, manage and monitor construction work to ensure it is carried out without risks to health and safety, including risks from adverse weather conditions.',
  },
  {
    id: 'hasawa-1974-s2',
    title: 'Health and Safety at Work Act 1974 – Section 2',
    section: 'General duties of employers',
    text: 'It shall be the duty of every employer to ensure, so far as is reasonably practicable, the health, safety and welfare at work of all his employees.',
  },
  {
    id: 'wahr-2005-reg-4',
    title: 'Work at Height Regulations 2005 – Regulation 4',
    section: 'Organisation and planning',
    text: 'Every employer shall ensure that work at height is properly planned, appropriately supervised, carried out in a manner that is safe, taking account of weather conditions that could endanger health or safety.',
  },
  {
    id: 'mhswr-1999-reg-3',
    title: 'MHSWR 1999 – Regulation 3',
    section: 'Risk assessment',
    text: 'Every employer shall make a suitable and sufficient assessment of the risks to the health and safety of his employees, including those arising from weather exposure.',
  },
  {
    id: 'hse-temp-guidance',
    title: 'HSE – Temperature Guidance',
    section: 'Protecting outdoor workers',
    text: 'There is no legal maximum or minimum working temperature for outdoor work. However, employers must conduct risk assessments for thermal comfort and provide appropriate controls such as rest breaks, shelter, and PPE.',
  },
  {
    id: 'hse-wind-guidance',
    title: 'HSE – Wind Safety',
    section: 'Construction wind limits',
    text: 'Crane operations must cease when wind speeds exceed manufacturer limits (typically 9–13 m/s). Work at height should be reassessed when sustained winds exceed 8 m/s or gusts exceed 12 m/s.',
  },
];

// ---------------------------------------------------------------------------
// Hazard → legal reference matching (lightweight reranker)
// ---------------------------------------------------------------------------

/**
 * Select the most relevant legal references for the given constraints.
 *
 * Acts as a simple "reranker" to keep the LLM context window manageable.
 *
 * @param {import('./TaskContextAgent').TaskConstraints} constraints
 * @returns {import('./LegalReasoningAgent').LegalReference[]}
 */
function retrieveRelevantLegal(constraints) {
  const keywords = [
    ...constraints.haltReasons,
    ...constraints.cautionReasons,
  ].join(' ').toLowerCase();

  return LEGAL_CATALOGUE.map((ref) => {
    // Simple keyword relevance scoring
    let score = 0;
    const combined = `${ref.title} ${ref.section} ${ref.text}`.toLowerCase();
    if (keywords.includes('wind') && combined.includes('wind')) score += 0.4;
    if (keywords.includes('temperature') && combined.includes('temperature')) score += 0.3;
    if (keywords.includes('temperature') && combined.includes('thermal')) score += 0.3;
    if (keywords.includes('height') && combined.includes('height')) score += 0.4;
    if (keywords.includes('rain') && combined.includes('weather')) score += 0.2;
    if (keywords.includes('uv') && combined.includes('outdoor')) score += 0.3;
    if (keywords.includes('visibility') && combined.includes('safety')) score += 0.2;
    // Boost general duties – always relevant
    if (combined.includes('general duties') || combined.includes('risk assessment')) score += 0.15;

    return {
      id: ref.id,
      title: ref.title,
      section: ref.section,
      relevantText: ref.text,
      relevanceScore: Math.min(score, 1),
    };
  })
    .filter((r) => r.relevanceScore > 0)
    .sort((a, b) => b.relevanceScore - a.relevanceScore)
    .slice(0, 4); // Keep top-4 to fit context window
}

// ---------------------------------------------------------------------------
// LLM reasoning (OpenAI GPT-4o via fetch)
// ---------------------------------------------------------------------------

/**
 * Apply legal reasoning to weather hazards.
 *
 * If the OpenAI API key is not set the function falls back to a deterministic
 * rule-based reasoning so the app still works without external AI.
 *
 * @param {Object} weather         Current weather data.
 * @param {import('./TaskContextAgent').TaskConstraints} constraints
 * @returns {Promise<LegalReasoning>}
 */
export async function applyLegalReasoning(weather, constraints) {
  const references = retrieveRelevantLegal(constraints);

  // NOTE: In a production deployment, API calls to OpenAI should be proxied
  // through a backend endpoint to protect the API key. The key is read from
  // the Vite build-time environment here for development convenience only.
  const openaiKey = typeof import.meta !== 'undefined'
    ? import.meta.env?.VITE_OPENAI_API_KEY
    : undefined;

  if (!openaiKey) {
    // Deterministic fallback
    return buildFallbackReasoning(weather, constraints, references);
  }

  // Build prompt
  const systemPrompt = `You are a UK construction health & safety legal expert.
Given the current weather data and identified task constraints, reason about
which UK legislation and HSE guidance applies.  Cite specific regulations.
Produce:
1. A concise reasoning paragraph.
2. A list of recommended mitigation controls.
3. Any compliance gaps.
4. An overall compliance status: "compliant", "partial", or "non-compliant".

Respond in JSON matching this schema:
{ "reasoning": string, "mitigations": string[], "complianceGaps": string[], "complianceStatus": "compliant"|"partial"|"non-compliant" }`;

  const userPrompt = `Weather: ${JSON.stringify(weather)}
Constraints: ${JSON.stringify(constraints)}
Legal references:
${references.map((r) => `- [${r.id}] ${r.title}: ${r.relevantText}`).join('\n')}`;

  try {
    const res = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${openaiKey}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o',
        response_format: { type: 'json_object' },
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt },
        ],
        temperature: 0.2,
        max_tokens: 1024,
      }),
    });

    if (!res.ok) {
      console.error('OpenAI API error', res.status);
      return buildFallbackReasoning(weather, constraints, references);
    }

    const data = await res.json();
    const parsed = JSON.parse(data.choices[0].message.content);

    return {
      references,
      reasoning: parsed.reasoning ?? '',
      mitigations: parsed.mitigations ?? [],
      complianceGaps: parsed.complianceGaps ?? [],
      complianceStatus: parsed.complianceStatus ?? 'partial',
    };
  } catch (err) {
    console.error('LegalReasoningAgent error', err);
    return buildFallbackReasoning(weather, constraints, references);
  }
}

// ---------------------------------------------------------------------------
// Stream-capable variant (SSE) — for future integration
// ---------------------------------------------------------------------------

/**
 * Stream legal reasoning via Server-Sent Events.
 *
 * @param {Object} weather
 * @param {import('./TaskContextAgent').TaskConstraints} constraints
 * @param {(token: string) => void} onToken  Called for each streamed token.
 * @returns {Promise<LegalReasoning>}
 */
export async function streamLegalReasoning(weather, constraints, onToken) {
  // Fallback to non-streaming for now – SSE requires a server endpoint
  const result = await applyLegalReasoning(weather, constraints);
  // Simulate streaming the reasoning text
  for (const char of result.reasoning) {
    onToken(char);
    await new Promise((r) => setTimeout(r, 5));
  }
  return result;
}

// ---------------------------------------------------------------------------
// Deterministic fallback
// ---------------------------------------------------------------------------

function buildFallbackReasoning(weather, constraints, references) {
  const mitigations = [];
  const complianceGaps = [];

  if (constraints.haltReasons.length > 0) {
    mitigations.push('Halt all affected work activities immediately');
    mitigations.push('Brief workers on weather-related stand-down procedure');
    complianceGaps.push(
      'Work proceeding under halt conditions would violate CDM 2015 Reg 13',
    );
  }

  if (constraints.cautionReasons.some((r) => r.includes('Wind'))) {
    mitigations.push('Reduce crane load limits by 25%');
    mitigations.push('Secure loose materials and scaffold sheeting');
  }

  if (constraints.cautionReasons.some((r) => r.includes('UV'))) {
    mitigations.push('Provide shaded rest areas');
    mitigations.push('Enforce 15-minute hydration breaks every hour');
  }

  if (constraints.cautionReasons.some((r) => r.includes('Temperature'))) {
    mitigations.push('Adjust work/rest schedules per HSE thermal comfort guidance');
  }

  mitigations.push('Complete updated risk assessment before resuming work');
  mitigations.push('Record weather conditions in site diary per CDM 2015');

  const status =
    constraints.haltReasons.length > 0
      ? 'non-compliant'
      : constraints.cautionReasons.length > 0
        ? 'partial'
        : 'compliant';

  const reasoning = constraints.haltReasons.length > 0
    ? `Current weather conditions trigger ${constraints.haltReasons.length} halt condition(s). Under CDM 2015 Regulation 13 and HASAWA 1974 Section 2, the contractor must cease the affected activity until conditions improve.`
    : constraints.cautionReasons.length > 0
      ? `Weather conditions are within operational limits but ${constraints.cautionReasons.length} caution flag(s) have been raised. Additional controls are required under MHSWR 1999 Regulation 3 (risk assessment duty).`
      : 'All weather parameters are within safe limits. Standard operating procedures apply. Ensure ongoing monitoring per CDM 2015 requirements.';

  return {
    references,
    reasoning,
    mitigations,
    complianceGaps,
    complianceStatus: status,
  };
}
