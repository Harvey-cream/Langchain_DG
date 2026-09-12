import { useState, useCallback } from 'react';
import { message } from 'antd';
import type { ChatApiClient } from '../../../services/chatApi';

export type ConversationItem = {
  id: number;
  title: string;
  updated_at: string;
  pinned?: boolean;
};

export function useConversation(chatApi: ChatApiClient) {
  const [conversations, setConversations] = useState<ConversationItem[]>([]);

  const loadConversations = useCallback(async (): Promise<ConversationItem[]> => {
    const response = await chatApi.getConversations();
    const items = response?.success && response?.data?.conversations
      ? response.data.conversations
      : [];
    setConversations(items);
    return items;
  }, [chatApi]);

  const renameConversation = useCallback(
    async (id: number, title: string) => {
      const res = await chatApi.patchConversation({ conversation_id: id, title });
      if (!res?.success) {
        message.error((res as { msg?: string })?.msg || '重命名失败');
        throw new Error('rename failed');
      }
      await loadConversations();
    },
    [chatApi, loadConversations]
  );

  const deleteConversation = useCallback(
    async (id: number) => {
      const res = await chatApi.deleteConversation(id);
      if (!res?.success) {
        message.error((res as { msg?: string })?.msg || '删除失败');
        throw new Error('delete failed');
      }
      await loadConversations();
    },
    [chatApi, loadConversations]
  );

  const pinConversation = useCallback(
    async (id: number, pinned: boolean) => {
      const res = await chatApi.patchConversation({ conversation_id: id, pinned });
      if (!res?.success) {
        message.error((res as { msg?: string })?.msg || '操作失败');
        throw new Error('pin failed');
      }
      message.success(pinned ? '已置顶' : '已取消置顶');
      await loadConversations();
    },
    [chatApi, loadConversations]
  );

  return {
    conversations,
    setConversations,
    loadConversations,
    renameConversation,
    deleteConversation,
    pinConversation,
  };
}
