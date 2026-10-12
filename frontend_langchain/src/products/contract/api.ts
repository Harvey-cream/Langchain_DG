import { sendRequest, sendUploadRequest, sendDownloadRequest } from '../../common/http/request';
import type {
  Analysis,
  AnalysisRun,
  ApiResponse,
  Contract,
  ContractVersion,
  Customer,
  ContractPolicy,
  PolicyWrite,
  KnowledgeDocument,
} from './types';

type AnalysisTask = { version_id: string; run_id: string };
type RetryTask = { run_id: string };

export const listCustomers = () =>
  sendRequest<ApiResponse<{ customers: Customer[] }>>('/api/customers', 'GET');

export const createCustomer = (params: { name: string; email: string }) =>
  sendRequest<ApiResponse<Customer>>('/api/customers', 'POST', params);

export const listContracts = () =>
  sendRequest<ApiResponse<{ contracts: Contract[] }>>('/api/contracts', 'GET');

export const createContract = (params: { customer_id: number; title: string }) =>
  sendRequest<ApiResponse<Contract>>('/api/contracts', 'POST', params);

export const getContract = (id: string) =>
  sendRequest<ApiResponse<Contract>>(`/api/contracts/${id}`, 'GET');

export const listContractVersions = (contractId: string) =>
  sendRequest<ApiResponse<{ versions: ContractVersion[] }>>(
    `/api/contracts/${contractId}/versions`,
    'GET',
  );

export const createContractVersion = (
  contractId: string,
  params: { source_key: string; filename: string },
) =>
  sendRequest<ApiResponse<ContractVersion>>(
    `/api/contracts/${contractId}/versions`,
    'POST',
    params,
  );

export const uploadContract = (
  id: string,
  file: File,
  ourParty = '',
  partyRole = '',
  contractType = '',
) => {
  const body = new FormData();
  body.append('file', file);
  body.append('our_party', ourParty.trim());
  body.append('party_role', partyRole.trim());
  body.append('contract_type', contractType.trim());
  return sendUploadRequest<ApiResponse<AnalysisTask>>(`/api/contracts/${id}/versions/upload`, body);
};

export const getAnalysis = (id: string, version: string) =>
  sendRequest<ApiResponse<Analysis | null>>(
    `/api/contracts/${id}/versions/${version}/analysis`,
    'GET',
  );

export const retryAnalysis = (
  id: string,
  version: string,
  ourParty = '',
  partyRole = '',
  contractType = '',
) =>
  sendRequest<ApiResponse<RetryTask>>(`/api/contracts/${id}/versions/${version}/analyze`, 'POST', {
    our_party: ourParty.trim(),
    ...(partyRole ? { party_role: partyRole.trim() } : {}),
    ...(contractType ? { contract_type: contractType.trim() } : {}),
  });

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

export const errorText = (error: unknown): string => {
  const cause = error as { response?: { data?: { msg?: string } } };
  if (cause.response?.data?.msg) return cause.response.data.msg;
  if (error instanceof Error && error.message) return error.message;
  return '请求失败，请检查网络或稍后重试';
};

export const listPolicies = () =>
  sendRequest<ApiResponse<{ policies: ContractPolicy[] }>>('/api/contract-policies', 'GET');
export const createPolicy = (body: PolicyWrite) =>
  sendRequest<ApiResponse<ContractPolicy>>('/api/contract-policies', 'POST', body);
export const updatePolicy = (
  id: string,
  body: Partial<PolicyWrite> & { expected_version: number },
) => sendRequest<ApiResponse<ContractPolicy>>(`/api/contract-policies/${id}`, 'PATCH', body);
export const archivePolicy = (id: string, version: number) =>
  sendRequest<ApiResponse<ContractPolicy>>(
    `/api/contract-policies/${id}?expected_version=${version}`,
    'DELETE',
  );

export const listKnowledgeDocuments = () =>
  sendRequest<ApiResponse<{ documents: KnowledgeDocument[] }>>(
    '/api/contract-knowledge/documents',
    'GET',
  );
export const uploadKnowledgeDocument = (file: File, category: string) => {
  const body = new FormData();
  body.append('file', file);
  body.append('category', category);
  return sendUploadRequest<ApiResponse<{ document: KnowledgeDocument; duplicate: boolean }>>(
    '/api/contract-knowledge/documents/upload',
    body,
  );
};
export const reindexKnowledgeDocument = (id: string) =>
  sendRequest<ApiResponse<KnowledgeDocument>>(
    `/api/contract-knowledge/documents/${id}/reindex`,
    'POST',
  );
export const deleteKnowledgeDocument = (id: string) =>
  sendRequest<ApiResponse<KnowledgeDocument>>(`/api/contract-knowledge/documents/${id}`, 'DELETE');
export const classifyKnowledgeDocument = (id: string, category: string, generation: number) =>
  sendRequest<ApiResponse<KnowledgeDocument>>(`/api/contract-knowledge/documents/${id}`, 'PATCH', {
    category,
    expected_generation: generation,
  });
export const downloadKnowledgeDocument = async (document: KnowledgeDocument) => {
  const blob = await sendDownloadRequest(
    `/api/contract-knowledge/documents/${document.id}/download`,
  );
  const url = URL.createObjectURL(blob);
  const anchor = window.document.createElement('a');
  anchor.href = url;
  anchor.download = document.filename;
  anchor.click();
  URL.revokeObjectURL(url);
};
