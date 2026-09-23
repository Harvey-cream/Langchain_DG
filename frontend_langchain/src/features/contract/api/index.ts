import { sendRequest } from '../../../services/request';
import type { ApiResponse, Contract, ContractVersion, Customer } from '../types';

export const listCustomers = () =>
  sendRequest<ApiResponse<{ customers: Customer[] }>>('/api/customers', 'GET');

export const createCustomer = (params: { name: string; email: string }) =>
  sendRequest<ApiResponse<Customer>>('/api/customers', 'POST', params);

export const listContracts = () =>
  sendRequest<ApiResponse<{ contracts: Contract[] }>>('/api/contracts', 'GET');

export const createContract = (params: { customer_id: number; title: string }) =>
  sendRequest<ApiResponse<Contract>>('/api/contracts', 'POST', params);

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
