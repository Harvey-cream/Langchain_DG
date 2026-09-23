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
