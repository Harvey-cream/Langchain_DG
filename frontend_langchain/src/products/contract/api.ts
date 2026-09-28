import { sendRequest, sendUploadRequest } from '../../common/http/request';
import type {
  Analysis,
  AnalysisRun,
  ApiResponse,
  Contract,
  ContractVersion,
  Customer,
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

export const uploadContract = (id: string, file: File) => {
  const body = new FormData();
  body.append('file', file);
  return sendUploadRequest<ApiResponse<AnalysisTask>>(
    `/api/contracts/${id}/versions/upload`,
    body,
  );
};

export const getAnalysis = (id: string, version: string) =>
  sendRequest<ApiResponse<Analysis | null>>(
    `/api/contracts/${id}/versions/${version}/analysis`,
    'GET',
  );

export const retryAnalysis = (id: string, version: string) =>
  sendRequest<ApiResponse<RetryTask>>(
    `/api/contracts/${id}/versions/${version}/analyze`,
    'POST',
  );

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
