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
// 不适合消费 text/event-stream；路径见 chatStream（/api/interview/chat/stream/）。

// --- AI 面试大师（/api/interview/，表 interview_conversations / interview_sessions）---

export const getInterviewConversations = () => sendRequest('/api/interview/chat/', 'GET');

export const getInterviewConversationMessages = (conversationId: number, sessionId?: number) =>
  sendRequest(
    `/api/interview/chat/?conversation_id=${conversationId}${
      sessionId != null ? `&session_id=${sessionId}` : ''
    }`,
    'GET'
  );

export const patchInterviewConversation = (params: {
  conversation_id: number;
  title?: string;
  pinned?: boolean;
}) => sendRequest('/api/interview/conversation/', 'PATCH', params);

export const deleteInterviewConversation = (conversationId: number) =>
  sendRequest('/api/interview/conversation/', 'DELETE', { conversation_id: conversationId });

// --- 用户 ---

// 获取用户信息
export const getUserInfo = () => sendRequest("/api/user/info/", 'GET');

// 更新用户信息
export const updateUserInfo = (params: any) => sendRequest("/api/user/info/update/", 'PUT', params);
