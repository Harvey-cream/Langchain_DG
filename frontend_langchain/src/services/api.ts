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
// 不适合消费 text/event-stream；路径见 chatStream（/api/agent/chat/stream/、/api/interview/chat/stream/）。
//

// --- 企业知识库AI助手（/api/agent/，表 user_conversations / user_sessions）---

// 获取会话列表
export const getConversations = () => sendRequest("/api/agent/chat/", 'GET');

// 获取某个会话详情（历史消息）；sessionId 仅取一条，用于流式结束对账、避免拉全量
export const getConversationMessages = (conversationId: number, sessionId?: number) =>
  sendRequest(
    `/api/agent/chat/?conversation_id=${conversationId}${
      sessionId != null ? `&session_id=${sessionId}` : ''
    }`,
    'GET'
  );

/** 更新会话：重命名 title 和/或 置顶 pinned */
export const patchConversation = (params: {
  conversation_id: number;
  title?: string;
  pinned?: boolean;
}) => sendRequest('/api/agent/conversation/', 'PATCH', params);

/** 删除会话（级联删除该会话下消息） */
export const deleteConversation = (conversationId: number) =>
  sendRequest('/api/agent/conversation/', 'DELETE', { conversation_id: conversationId });

// --- 知识库助手文档（OSS 直传）---

export type AgentDocumentItem = {
  id: number;
  filename: string;
  format: string;
  status: string;
  chunk_count: number;
  size_bytes: number;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
};

export const listAgentDocuments = () => sendRequest('/api/agent/documents', 'GET');

export const initAgentDocumentUpload = (params: {
  filename: string;
  content_type: string;
  size_bytes: number;
}) => sendRequest('/api/agent/documents/upload-init', 'POST', params);

export const confirmAgentDocumentUpload = (documentId: number) =>
  sendRequest(`/api/agent/documents/${documentId}/confirm`, 'POST');

export const deleteAgentDocument = (documentId: number) =>
  sendRequest(`/api/agent/documents/${documentId}`, 'DELETE');

/** 选文件 → 预签名直传 OSS → confirm 触发入库 */
export async function uploadAgentDocumentFile(file: File): Promise<AgentDocumentItem> {
  const initRes = await initAgentDocumentUpload({
    filename: file.name,
    content_type: file.type || 'application/octet-stream',
    size_bytes: file.size,
  });
  if (!initRes?.success || !initRes.data?.upload_url) {
    throw new Error(initRes?.msg || '获取上传凭证失败');
  }
  const { document_id, upload_url, content_type } = initRes.data as {
    document_id: number;
    upload_url: string;
    content_type: string;
  };
  try {
    const putRes = await fetch(upload_url, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': content_type || file.type || 'application/octet-stream' },
    });
    if (!putRes.ok) {
      throw new Error(`OSS 上传失败 (${putRes.status})`);
    }
    const confirmRes = await confirmAgentDocumentUpload(document_id);
    if (!confirmRes?.success) {
      throw new Error(confirmRes?.msg || '确认入库失败');
    }
    return confirmRes.data as AgentDocumentItem;
  } catch (err) {
    // upload-init 已建库：失败时删掉，避免留下「等待中」脏记录
    try {
      await deleteAgentDocument(document_id);
    } catch {
      /* ignore cleanup error */
    }
    throw err;
  }
}

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
