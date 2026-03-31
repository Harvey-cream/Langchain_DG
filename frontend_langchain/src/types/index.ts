// 用户相关类型定义
export interface UserDto {
  name: string;
  password: string;
  email: string;
}

// 登录请求参数
export interface LoginRequest {
  email: string;
  password: string;
}

// 登录响应
export interface LoginResponse {
  token?: string;
  message: string;
  success: boolean;
}

// 注册响应
export interface RegisterResponse {
  message: string;
  success: boolean;
}

// API响应通用结构
export interface ApiResponse<T> {
  data?: T;
  message: string;
  success: boolean;
}

// 表单验证错误
export interface FormErrors {
  [key: string]: string;
}