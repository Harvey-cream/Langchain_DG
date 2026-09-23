import { sendRequest, sendUploadRequest } from '../../../services/request';
import type { ApiResponse, Contract } from '../types';

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

type AnalysisTask = { version_id: string; run_id: string };
type RetryTask = { run_id: string };
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

export const uploadContract = (id: string, file: File) => {
  const body = new FormData();
  body.append('file', file);
  return sendUploadRequest<ApiResponse<AnalysisTask>>(`/api/contracts/${id}/versions/upload`, body);
};
export const getAnalysis = (id: string, version: string) =>
  sendRequest<ApiResponse<Analysis | null>>(
    `/api/contracts/${id}/versions/${version}/analysis`,
    'GET',
  );
export const retryAnalysis = (id: string, version: string) =>
  sendRequest<ApiResponse<RetryTask>>(`/api/contracts/${id}/versions/${version}/analyze`, 'POST');
export const listAnalysisRuns = (id: string, version: string) =>
  sendRequest<ApiResponse<{ selected_run_id?: string | null; runs: AnalysisRun[] }>>(
    `/api/contracts/${id}/versions/${version}/analysis-runs`,
    'GET',
  );
export const selectAnalysisRun = (id: string, version: string, runId: string) =>
  sendRequest<ApiResponse<Analysis>>(
    `/api/contracts/${id}/versions/${version}/analysis-runs/${runId}/select`,
    'POST',
  );
export const getContract = (id: string) =>
  sendRequest<ApiResponse<Contract>>(`/api/contracts/${id}`, 'GET');
export const errorText = (error: unknown): string => {
  const e = error as { response?: { data?: { msg?: string } } };
  if (e.response?.data?.msg) return e.response.data.msg;
  if (error instanceof Error && error.message) return error.message;
  return '请求失败，请检查网络或稍后重试';
};
