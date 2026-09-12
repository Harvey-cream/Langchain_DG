export type ChatMessage = {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: string;
  attachments?: unknown[];
};

export type ChatConversation = {
  id: number;
  title: string;
  updated_at: string;
  pinned?: boolean;
};
