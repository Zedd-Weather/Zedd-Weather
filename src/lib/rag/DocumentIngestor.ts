/**
 * DocumentIngestor.ts
 *
 * Uses LangChain to load, chunk, and embed "UK Legislation" and "HSE Guidance"
 * documents into a Pinecone vector store.
 *
 * ⚠️ SERVER-SIDE ONLY — This module is designed to run in Node / edge runtime
 * because it requires network access to Pinecone and the OpenAI embeddings
 * endpoint.  API keys are read from server-side environment variables and must
 * never be exposed in client bundles.  From the React front-end this module is
 * consumed indirectly through the agent layer or a backend proxy.
 */

// ---------------------------------------------------------------------------
// Types – kept self-contained so the front-end can import them without
// pulling in heavy server-only deps.
// ---------------------------------------------------------------------------

export interface DocumentChunk {
  id: string;
  content: string;
  metadata: ChunkMetadata;
  embedding?: number[];
}

export interface ChunkMetadata {
  source: string;
  /** e.g. "UK Legislation" | "HSE Guidance" */
  category: 'UK Legislation' | 'HSE Guidance';
  title: string;
  section?: string;
  pageNumber?: number;
  chunkIndex: number;
  totalChunks: number;
  /** ISO-8601 date when the document was last updated */
  lastUpdated: string;
}

export interface IngestorConfig {
  pinecone: {
    apiKey: string;
    environment: string;
    indexName: string;
    namespace?: string;
  };
  openai: {
    apiKey: string;
    embeddingModel: string;
  };
  chunkSize: number;
  chunkOverlap: number;
}

// ---------------------------------------------------------------------------
// Default configuration – values come from environment variables at runtime
// ---------------------------------------------------------------------------

export const DEFAULT_INGESTOR_CONFIG: IngestorConfig = {
  pinecone: {
    apiKey: process.env.PINECONE_API_KEY ?? '',
    environment: process.env.PINECONE_ENVIRONMENT ?? 'us-east-1',
    indexName: process.env.PINECONE_INDEX ?? 'zedd-legislation',
    namespace: process.env.PINECONE_NAMESPACE ?? 'uk-construction',
  },
  openai: {
    apiKey: process.env.OPENAI_API_KEY ?? '',
    embeddingModel: 'text-embedding-3-small',
  },
  chunkSize: 1000,
  chunkOverlap: 200,
};

// ---------------------------------------------------------------------------
// UK Legislation & HSE source catalogue
// ---------------------------------------------------------------------------

export interface LegislationSource {
  id: string;
  title: string;
  category: 'UK Legislation' | 'HSE Guidance';
  description: string;
  /** URL or local path for the raw document */
  uri: string;
}

export const UK_LEGISLATION_SOURCES: LegislationSource[] = [
  {
    id: 'cdm-2015',
    title: 'Construction (Design and Management) Regulations 2015',
    category: 'UK Legislation',
    description:
      'CDM 2015 – duties of clients, designers, and contractors regarding health, safety, and welfare on construction projects.',
    uri: 'https://www.legislation.gov.uk/uksi/2015/51/contents',
  },
  {
    id: 'hasawa-1974',
    title: 'Health and Safety at Work etc. Act 1974',
    category: 'UK Legislation',
    description:
      'Primary legislation covering occupational health and safety in the United Kingdom.',
    uri: 'https://www.legislation.gov.uk/ukpga/1974/37/contents',
  },
  {
    id: 'wahr-2005',
    title: 'Work at Height Regulations 2005',
    category: 'UK Legislation',
    description:
      'Regulations to prevent death and injury caused by falls from height.',
    uri: 'https://www.legislation.gov.uk/uksi/2005/735/contents',
  },
  {
    id: 'mhswr-1999',
    title: 'Management of Health and Safety at Work Regulations 1999',
    category: 'UK Legislation',
    description:
      'Require employers to carry out risk assessments and implement preventive measures.',
    uri: 'https://www.legislation.gov.uk/uksi/1999/3242/contents',
  },
  {
    id: 'hse-weather',
    title: 'HSE Guidance – Protecting Outdoor Workers',
    category: 'HSE Guidance',
    description:
      'HSE guidance on managing the risks from working in hot, cold, wet, or windy weather.',
    uri: 'https://www.hse.gov.uk/temperature/outdoor.htm',
  },
  {
    id: 'hse-construction',
    title: 'HSE Guidance – Construction Health and Safety',
    category: 'HSE Guidance',
    description:
      'General construction safety guidance from the Health and Safety Executive.',
    uri: 'https://www.hse.gov.uk/construction/index.htm',
  },
];

// ---------------------------------------------------------------------------
// DocumentIngestor class
// ---------------------------------------------------------------------------

/**
 * Orchestrates the load → chunk → embed → upsert pipeline.
 *
 * Usage (server-side only):
 * ```ts
 * const ingestor = new DocumentIngestor(config);
 * await ingestor.ingestAll();
 * const results = await ingestor.query("wind speed regulations for crane operations");
 * ```
 */
export class DocumentIngestor {
  private config: IngestorConfig;

  constructor(config: Partial<IngestorConfig> = {}) {
    this.config = { ...DEFAULT_INGESTOR_CONFIG, ...config };
  }

  // -----------------------------------------------------------------------
  // Public API
  // -----------------------------------------------------------------------

  /**
   * Ingest all registered legislation sources into the vector store.
   * Returns the total number of chunks upserted.
   */
  async ingestAll(): Promise<number> {
    let totalChunks = 0;

    for (const source of UK_LEGISLATION_SOURCES) {
      const raw = await this.loadDocument(source);
      const chunks = this.chunkText(raw, source);
      const embedded = await this.embedChunks(chunks);
      await this.upsertToPinecone(embedded);
      totalChunks += embedded.length;
    }

    return totalChunks;
  }

  /**
   * Ingest a single document by its catalogue ID.
   */
  async ingestById(sourceId: string): Promise<number> {
    const source = UK_LEGISLATION_SOURCES.find((s) => s.id === sourceId);
    if (!source) throw new Error(`Unknown source: ${sourceId}`);

    const raw = await this.loadDocument(source);
    const chunks = this.chunkText(raw, source);
    const embedded = await this.embedChunks(chunks);
    await this.upsertToPinecone(embedded);
    return embedded.length;
  }

  /**
   * Semantic search over the vector store.
   *
   * @param queryText  Natural-language question.
   * @param topK       Number of results to return.
   * @returns          Relevant document chunks with scores.
   */
  async query(
    queryText: string,
    topK = 5,
  ): Promise<{ chunk: DocumentChunk; score: number }[]> {
    const queryEmbedding = await this.embed(queryText);

    const body = {
      vector: queryEmbedding,
      topK,
      includeMetadata: true,
      namespace: this.config.pinecone.namespace,
    };

    const res = await fetch(
      `https://${this.config.pinecone.indexName}-${this.config.pinecone.environment}.svc.pinecone.io/query`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Api-Key': this.config.pinecone.apiKey,
        },
        body: JSON.stringify(body),
      },
    );

    if (!res.ok) {
      throw new Error(`Pinecone query failed: ${res.status} ${res.statusText}`);
    }

    const data = await res.json();

    return (data.matches ?? []).map((m: any) => ({
      chunk: {
        id: m.id,
        content: m.metadata?.content ?? '',
        metadata: m.metadata as ChunkMetadata,
      },
      score: m.score,
    }));
  }

  // -----------------------------------------------------------------------
  // Internal helpers
  // -----------------------------------------------------------------------

  /** Load raw text for a legislation source. */
  private async loadDocument(source: LegislationSource): Promise<string> {
    // In production this would use LangChain document loaders
    // (WebBaseLoader / PDFLoader) to fetch & parse the URI.
    // For now we return a representative stub so the rest of the
    // pipeline can operate without external network access.
    return [
      `# ${source.title}`,
      '',
      `Category: ${source.category}`,
      `Source: ${source.uri}`,
      '',
      source.description,
      '',
      '(Full document content would be loaded at runtime via LangChain loaders.)',
    ].join('\n');
  }

  /** Split text into overlapping chunks using a recursive character splitter. */
  private chunkText(
    text: string,
    source: LegislationSource,
  ): DocumentChunk[] {
    const { chunkSize, chunkOverlap } = this.config;
    const chunks: DocumentChunk[] = [];
    let start = 0;
    let idx = 0;

    while (start < text.length) {
      const end = Math.min(start + chunkSize, text.length);
      const content = text.slice(start, end);

      chunks.push({
        id: `${source.id}-chunk-${idx}`,
        content,
        metadata: {
          source: source.uri,
          category: source.category,
          title: source.title,
          chunkIndex: idx,
          totalChunks: 0, // patched below
          lastUpdated: new Date().toISOString(),
        },
      });

      start += chunkSize - chunkOverlap;
      idx++;
    }

    // Patch totalChunks
    for (const c of chunks) {
      c.metadata.totalChunks = chunks.length;
    }

    return chunks;
  }

  /** Embed a batch of chunks using the OpenAI embeddings API. */
  private async embedChunks(
    chunks: DocumentChunk[],
  ): Promise<DocumentChunk[]> {
    const texts = chunks.map((c) => c.content);
    const embeddings = await this.embedBatch(texts);

    return chunks.map((c, i) => ({ ...c, embedding: embeddings[i] }));
  }

  /** Embed a single text string. */
  private async embed(text: string): Promise<number[]> {
    const [result] = await this.embedBatch([text]);
    return result;
  }

  /** Batch embedding via the OpenAI API. */
  private async embedBatch(texts: string[]): Promise<number[][]> {
    const res = await fetch('https://api.openai.com/v1/embeddings', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.config.openai.apiKey}`,
      },
      body: JSON.stringify({
        model: this.config.openai.embeddingModel,
        input: texts,
      }),
    });

    if (!res.ok) {
      throw new Error(
        `OpenAI embedding failed: ${res.status} ${res.statusText}`,
      );
    }

    const data = await res.json();
    return data.data.map((d: any) => d.embedding);
  }

  /** Upsert embedded chunks into Pinecone. */
  private async upsertToPinecone(chunks: DocumentChunk[]): Promise<void> {
    const vectors = chunks.map((c) => ({
      id: c.id,
      values: c.embedding,
      metadata: { ...c.metadata, content: c.content },
    }));

    const res = await fetch(
      `https://${this.config.pinecone.indexName}-${this.config.pinecone.environment}.svc.pinecone.io/vectors/upsert`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Api-Key': this.config.pinecone.apiKey,
        },
        body: JSON.stringify({
          vectors,
          namespace: this.config.pinecone.namespace,
        }),
      },
    );

    if (!res.ok) {
      throw new Error(
        `Pinecone upsert failed: ${res.status} ${res.statusText}`,
      );
    }
  }
}
