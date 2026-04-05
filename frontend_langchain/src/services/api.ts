import { sendRequest, sendReleaseRequest} from './request';
import { UserDto, LoginRequest } from '../types';

// --- 公开接口 (不需要登录) ---
// 注册
export const register = (params: UserDto) => sendReleaseRequest("/api/user/register/", 'POST', params);

// 登录
export const login = (params: LoginRequest) => sendReleaseRequest("/api/user/login/", 'POST', params);

// --- 受保护接口 (需要登录) ---
//
// 发送一条「流式」对话消息不在本文件里封装：见 services/chatStream.ts。
// 原因：流式必须用 fetch + response.body.getReader() 读 SSE，而 sendRequest 基于 axios，
// 不适合消费 text/event-stream；路径为 POST /api/agent/chat/stream/。
//

// 获取会话列表
export const getConversations = () => sendRequest("/api/agent/chat/", 'GET');

// 获取某个会话详情（历史消息）
export const getConversationMessages = (conversationId: number) =>
  sendRequest(`/api/agent/chat/?conversation_id=${conversationId}`, 'GET');

/** 更新会话：重命名 title 和/或 置顶 pinned */
export const patchConversation = (params: {
  conversation_id: number;
  title?: string;
  pinned?: boolean;
}) => sendRequest('/api/agent/conversation/', 'PATCH', params);

/** 删除会话（级联删除该会话下消息） */
export const deleteConversation = (conversationId: number) =>
  sendRequest('/api/agent/conversation/', 'DELETE', { conversation_id: conversationId });

// 获取用户信息
export const getUserInfo = () => sendRequest("/api/user/info/", 'GET');

// 更新用户信息
export const updateUserInfo = (params: any) => sendRequest("/api/user/info/update/", 'PUT', params);
