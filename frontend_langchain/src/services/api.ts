import { sendRequest, sendReleaseRequest} from './request';
import { UserDto, LoginRequest } from '../types';

// --- 公开接口 (不需要登录) ---
// 注册
export const register = (params: UserDto) => sendReleaseRequest("/api/user/register/", 'POST', params);

// 登录
export const login = (params: LoginRequest) => sendReleaseRequest("/api/user/login/", 'POST', params);

// --- 受保护接口 (需要登录) ---
// AI 对话
export const chatWithAgent = (message: string, conversationId?: number) =>
  sendRequest("/api/agent/chat/", 'POST', { message, conversation_id: conversationId }, 60000);

// 获取会话列表
export const getConversations = () => sendRequest("/api/agent/chat/", 'GET');

// 获取某个会话详情（历史消息）
export const getConversationMessages = (conversationId: number) =>
  sendRequest(`/api/agent/chat/?conversation_id=${conversationId}`, 'GET');

// 示例：获取用户信息
export const getUserInfo = () => sendRequest("/api/user/info/", 'GET');

// 示例：更新用户信息
export const updateUserInfo = (params: any) => sendRequest("/api/user/info/update/", 'PUT', params);
