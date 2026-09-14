import { sendRequest, sendUploadRequest } from '../../../services/request';
export type Analysis = {
  status: string;
  error?: string;
  document_text: string;
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
export const uploadContract = (id: string, file: File) => {
  const body = new FormData();
  body.append('file', file);
  return sendUploadRequest(`/api/contracts/${id}/versions/upload`, body);
};
export const getAnalysis = (id: string, version: string) =>
  sendRequest(`/api/contracts/${id}/versions/${version}/analysis`, 'GET');
export const retryAnalysis = (id: string, version: string) =>
  sendRequest(`/api/contracts/${id}/versions/${version}/analyze`, 'POST');
export const getContract = (id: string) => sendRequest(`/api/contracts/${id}`, 'GET');
export const errorText = (error: unknown): string => {
  const e = error as { response?: { data?: { msg?: string } } };
  return e.response?.data?.msg || '请求失败，请检查网络或稍后重试';
};
