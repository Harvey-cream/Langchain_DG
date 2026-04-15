/**
 * 对话页与后端交互的抽象：超级智能体走 /api/agent/，面试大师走 /api/interview/（独立表）。
 */
import {
  getConversations,
  getConversationMessages,
  patchConversation,
  deleteConversation,
  getInterviewConversations,
  getInterviewConversationMessages,
  patchInterviewConversation,
  deleteInterviewConversation,
} from './api';
import {
  chatWithAgentStream,
  chatWithInterviewStream,
  type ChatStreamCallbacks,
} from './chatStream';

export type ChatApiClient = {
  getConversations: () => ReturnType<typeof getConversations>;
  getConversationMessages: (
    conversationId: number,
    sessionId?: number
  ) => ReturnType<typeof getConversationMessages>;
  patchConversation: typeof patchConversation;
  deleteConversation: typeof deleteConversation;
  chatWithStream: (
    message: string,
    conversationId: number | undefined,
    callbacks: ChatStreamCallbacks,
    options?: { idleMs?: number; signal?: AbortSignal }
  ) => Promise<void>;
};

/** 默认：超级智能体 + user_conversations / user_sessions */
export const agentChatApi: ChatApiClient = {
  getConversations,
  getConversationMessages,
  patchConversation,
  deleteConversation,
  chatWithStream: chatWithAgentStream,
};

/** AI 面试大师：interview_conversations / interview_sessions */
export const interviewChatApi: ChatApiClient = {
  getConversations: getInterviewConversations,
  getConversationMessages: getInterviewConversationMessages,
  patchConversation: patchInterviewConversation,
  deleteConversation: deleteInterviewConversation,
  chatWithStream: chatWithInterviewStream,
};
