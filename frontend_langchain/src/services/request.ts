import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';

// 创建Axios实例
const apiClient: AxiosInstance = axios.create({
  baseURL: '',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 创建不需要认证的Axios实例
const releaseClient: AxiosInstance = axios.create({
  baseURL: '',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器（带认证）
apiClient.interceptors.request.use(
  (config) => {
    // 添加认证token
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
const setupResponseInterceptor = (client: AxiosInstance) => {
  client.interceptors.response.use(
    (response: AxiosResponse) => {
      return response;
    },
    (error) => {
      // 统一错误处理
      if (error.response) {
        // 服务器返回错误状态码
        console.error('API Error:', error.response.data);
      } else if (error.request) {
        // 请求已发出但没有收到响应
        console.error('Network Error:', error.request);
      } else {
        // 请求配置出错
        console.error('Request Error:', error.message);
      }
      return Promise.reject(error);
    }
  );
};

// 设置响应拦截器
setupResponseInterceptor(apiClient);
setupResponseInterceptor(releaseClient);

// 通用请求方法
export const sendRequest = async (url: string, method: string, data?: any, timeout?: number): Promise<any> => {
  const config: AxiosRequestConfig = {
    url,
    method,
    data,
    ...(timeout ? { timeout } : {}),
  };
  const response = await apiClient(config);
  return response.data;
};

// 不需要认证的请求方法
export const sendReleaseRequest = async (url: string, method: string, data?: any, timeout?: number): Promise<any> => {
  const config: AxiosRequestConfig = {
    url,
    method,
    data,
    ...(timeout ? { timeout } : {}),
  };
  const response = await releaseClient(config);
  return response.data;
};

// 文件上传请求方法
export const sendUploadRequest = async (url: string, data: FormData): Promise<any> => {
  const config: AxiosRequestConfig = {
    url,
    method: 'POST',
    data,
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  };
  const response = await apiClient(config);
  return response.data;
};