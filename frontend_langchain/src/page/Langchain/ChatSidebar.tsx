import React from 'react';

type ConversationItem = {
  id: number;
  title: string;
  updated_at: string;
};

type ChatSidebarProps = {
  conversations: ConversationItem[];
  activeConversationId?: number;
  onSelectConversation: (conversationId: number) => Promise<void> | void;
  onCreateConversation: () => void;
};

const ChatSidebar: React.FC<ChatSidebarProps> = ({
  conversations,
  activeConversationId,
  onSelectConversation,
  onCreateConversation,
}) => {
  return (
    <aside className="chat-sidebar">
      <div className="chat-sidebar-header">
        <h2>对话列表</h2>
        <button className="new-chat-button" onClick={onCreateConversation}>+ 新对话</button>
      </div>

      <div className="chat-sidebar-list">
        {conversations.map((item) => (
          <button
            key={item.id}
            className={`chat-sidebar-item ${activeConversationId === item.id ? 'active' : ''}`}
            onClick={() => {
              void onSelectConversation(item.id);
            }}
          >
            <div className="chat-sidebar-title">{item.title}</div>
            <div className="chat-sidebar-time">{item.updated_at}</div>
          </button>
        ))}
      </div>
    </aside>
  );
};

export type { ConversationItem };
export default ChatSidebar;
