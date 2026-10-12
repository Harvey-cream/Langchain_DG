export type ApiResponse<T> = {
  success: boolean;
  msg?: string;
  data?: T;
};

export type Customer = {
  id: number;
  name: string;
  email: string;
};

export type Contract = {
  id: string;
  customer_id: number;
  title: string;
};

export type ContractVersion = {
  id: string;
  contract_id: string;
  number: number;
  source_key: string;
  filename: string;
  status: string;
};

export type Analysis = {
  id: string;
  status: string;
  current_step?: string;
  attempt?: number;
  error?: string;
  document_text: string;
  latest_run_id?: string | null;
  selected_run_id?: string | null;
  is_showing_previous?: boolean;
  review_version?: 'v1' | 'v2';
  our_party?: string;
  party_role?: string;
  contract_type?: string;
  model_name?: string | null;
  prompt_version?: string;
  latest_quality_gate?: ReviewQualityReport | null;
  context_snapshot?: {
    policies?: ContractPolicy[];
    references?: ReferenceSnapshot[];
    retrieval?: { enabled: boolean };
    quality_gate?: ReviewQualityReport;
    retrieval_events?: { reference_count: number; unavailable_count?: number }[];
  };
  facts?: {
    metadata: DocumentMetadata;
    coverage: { ratio: number; warnings: string[] };
    parser_version: string;
    intelligence_version: string;
  } | null;
  canonical_clauses?: CanonicalClause[];
  clauses?: {
    id: string;
    sequence: number;
    clause_type: string;
    title: string;
    original_text: string;
    summary: string;
  }[];
  risks?: {
    id: string;
    clause_id?: string | null;
    title: string;
    risk_level: 'high' | 'medium' | 'low';
    risk_type?: string | null;
    evidence?: string;
    recommendation?: string;
    related_clause_ids?: string[];
    policy_ids?: string[];
    reference_citations?: ReferenceCitation[];
    evidence_text: string;
    reason: string;
    suggestion: string;
    review_status: string;
    reviewer_note?: string | null;
  }[];
  result?: LegacyResult | { risks: RiskFinding[] } | null;
};

export type DocumentMetadata = {
  summary: string;
  parties: string[];
  amount: string;
  duration: string;
  payment_terms: string;
};
export type CanonicalClause = {
  id: string;
  sequence: number;
  title: string;
  clause_type: string;
  original_text: string;
  source_block_ids: string[];
  pages: number[];
};
export type RiskFinding = {
  clause_id: string;
  risk_type: string;
  risk_level: 'high' | 'medium' | 'low';
  evidence: string;
  reason: string;
  recommendation: string;
  related_clause_ids: string[];
  policy_ids?: string[];
  reference_citations?: ReferenceCitation[];
};
export type LegacyResult = {
  document_type: string;
  summary: string;
  parties: string[];
  amount: string;
  duration: string;
  payment_terms: string;
  key_obligations: string[];
  risks: {
    title: string;
    risk_level: 'high' | 'medium' | 'low';
    original_text: string;
    reason: string;
    suggestion: string;
  }[];
};

export type AnalysisRun = {
  id: string;
  status: string;
  current_step: string;
  attempt: number;
  error?: string | null;
  model_name?: string | null;
  prompt_version: string;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  selected: boolean;
  review_version?: 'v1' | 'v2';
  our_party?: string;
};

export type ContractPolicy = {
  id: string;
  name: string;
  description: string;
  category: string;
  applicable_contract_types: string[];
  applicable_party_role: string;
  requirement: string;
  severity: 'high' | 'medium' | 'low';
  enabled: boolean;
  archived: boolean;
  version: number;
};
export type PolicyWrite = Omit<ContractPolicy, 'id' | 'version' | 'archived'>;

export type KnowledgeDocument = {
  id: string;
  filename: string;
  document_version: number;
  category: string;
  status: 'uploading' | 'uploaded' | 'processing' | 'ready' | 'failed' | 'deleting' | 'deleted';
  generation: number;
  attempt: number;
  chunk_count: number;
  byte_count: number;
  page_count?: number | null;
  error?: string | null;
  embedding_model: string;
};
export type ReferenceCitation = { chunk_id: string; source_excerpt: string };
export type ReferenceSnapshot = {
  chunk_id: string;
  document_id: string;
  document_version: number;
  index_generation: number;
  filename: string;
  document_type: string;
  chunk_text: string;
  locator: { pages?: number[]; start_char?: number; end_char?: number; block_sequences?: number[] };
  clause_ids?: string[];
};

export type ReviewQualityReport = {
  version: string;
  status: 'passed' | 'failed';
  verified_count?: number;
  duplicate_count?: number;
  warnings?: string[];
  limitation?: string;
  message?: string;
  finding_checks?: {
    clause_id: string;
    risk_type: string;
    evidence: string;
    reason: string;
    recommendation: string;
    assessment: 'review_hint' | 'insufficient_legal_basis';
    notes: string[];
  }[];
};
