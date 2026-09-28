import { sendRequest, sendReleaseRequest } from '../http/request';

export interface UserDto {
  name: string;
  password: string;
  email: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface FormErrors {
  [key: string]: string;
}

// --- 公开接口 (不需要登录) ---
// 注册
export const register = (params: UserDto) => sendReleaseRequest("/api/user/register/", 'POST', params);

// 登录
export const login = (params: LoginRequest) => sendReleaseRequest("/api/user/login/", 'POST', params);

// --- 用户 ---

// 获取用户信息
export const getUserInfo = () => sendRequest("/api/user/info/", 'GET');

// 更新用户信息
export const updateUserInfo = (params: Record<string, unknown>) =>
  sendRequest("/api/user/info/update/", 'PUT', params);
