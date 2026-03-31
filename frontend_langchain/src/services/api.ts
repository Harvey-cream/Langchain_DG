import { sendRequest, sendReleaseRequest, sendUploadRequest } from './request';
import { UserDto, LoginRequest } from '../types';

// --- 公开接口 (不需要登录) ---

// 注册
export const register = (params: UserDto) => sendReleaseRequest("/api/user/register/", 'POST', params);

// 登录（注：后端暂未实现登录接口，这里是预留接口）
export const login = (params: LoginRequest) => sendReleaseRequest("/api/user/login/", 'POST', params);

// --- 受保护接口 (需要登录) ---

// 示例：获取用户信息
export const getUserInfo = () => sendRequest("/api/user/info/", 'GET');

// 示例：更新用户信息
export const updateUserInfo = (params: any) => sendRequest("/api/user/info/update/", 'PUT', params);