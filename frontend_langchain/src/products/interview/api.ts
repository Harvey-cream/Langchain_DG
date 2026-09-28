import { sendRequest } from '../../common/http/request';
import {
  chatWithInterviewStream,
  type ChatAttachment,
  type ChatStreamCallbacks,
} from './stream';

const getInterviewConversations = () =>
  sendRequest('/api/interview/chat/', 'GET');

const getInterviewConversationMessages = (
  conversationId: number,
  sessionId?: number,
) =>
  sendRequest(
    `/api/interview/chat/?conversation_id=${conversationId}${
      sessionId != null ? `&session_id=${sessionId}` : ''
    }`,
    'GET',
  );

const patchInterviewConversation = (params: {
  conversation_id: number;
  title?: string;
  pinned?: boolean;
}) => sendRequest('/api/interview/conversation/', 'PATCH', params);

const deleteInterviewConversation = (conversationId: number) =>
  sendRequest('/api/interview/conversation/', 'DELETE', {
    conversation_id: conversationId,
  });

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
    },
  ) => Promise<void>;
};

export const interviewChatApi: ChatApiClient = {
  getConversations: getInterviewConversations,
  getConversationMessages: getInterviewConversationMessages,
  patchConversation: patchInterviewConversation,
  deleteConversation: deleteInterviewConversation,
  chatWithStream: chatWithInterviewStream,
};
