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
    evidence_text: string;
    reason: string;
    suggestion: string;
    review_status: string;
    reviewer_note?: string | null;
  }[];
  result?: {
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
};
