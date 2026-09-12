/**
 * 对话页与后端交互的抽象：AI 面试大师走 /api/interview/（独立表）。
 */
import {
  getInterviewConversations,
  getInterviewConversationMessages,
  patchInterviewConversation,
  deleteInterviewConversation,
} from './api';
import {
  chatWithInterviewStream,
  type ChatStreamCallbacks,
  type ChatAttachment,
} from './chatStream';

export type ChatApiClient = {
  getConversations: typeof getInterviewConversations;
  getConversationMessages: typeof getInterviewConversationMessages;
  patchConversation: typeof patchInterviewConversation;
  deleteConversation: typeof deleteInterviewConversation;
  chatWithStream: (
    message: string,
    conversationId: number | undefined,
    callbacks: ChatStreamCallbacks,
    options?: {
      idleMs?: number;
      signal?: AbortSignal;
      resumePdfExport?: boolean;
      enableWebSearch?: boolean;
      attachments?: ChatAttachment[];
    }
  ) => Promise<void>;
};

/** AI 面试大师：interview_conversations / interview_sessions */
export const interviewChatApi: ChatApiClient = {
  getConversations: getInterviewConversations,
  getConversationMessages: getInterviewConversationMessages,
  patchConversation: patchInterviewConversation,
  deleteConversation: deleteInterviewConversation,
  chatWithStream: chatWithInterviewStream,
};
