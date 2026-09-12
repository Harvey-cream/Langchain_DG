import { sendRequest } from '../../../services/request';
import type { Contract, ContractVersion, Customer } from '../types';

type ApiResponse<T> = { success: boolean; msg?: string; data?: T };

export const listCustomers = () =>
  sendRequest('/api/customers', 'GET') as Promise<ApiResponse<{ customers: Customer[] }>>;

export const createCustomer = (params: { name: string; email: string }) =>
  sendRequest('/api/customers', 'POST', params) as Promise<ApiResponse<Customer>>;

export const listContracts = () =>
  sendRequest('/api/contracts', 'GET') as Promise<ApiResponse<{ contracts: Contract[] }>>;

export const createContract = (params: { customer_id: number; title: string }) =>
  sendRequest('/api/contracts', 'POST', params) as Promise<ApiResponse<Contract>>;

export const listContractVersions = (contractId: string) =>
  sendRequest(`/api/contracts/${contractId}/versions`, 'GET') as Promise<
    ApiResponse<{ versions: ContractVersion[] }>
  >;

export const createContractVersion = (
  contractId: string,
  params: { source_key: string; filename: string },
) =>
  sendRequest(`/api/contracts/${contractId}/versions`, 'POST', params) as Promise<
    ApiResponse<ContractVersion>
  >;
