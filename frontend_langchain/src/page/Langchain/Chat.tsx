import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Modal, message } from 'antd';
import {
  chatWithAgent,
  getConversations,
  getConversationMessages,
  getUserInfo,
  patchConversation,
  deleteConversation,
} from '../../services/api';
import ChatSidebar, { ConversationItem } from './ChatSidebar';
import './Chat.css';

interface Message {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: string;
}

type ChatViewProps = {
  featureTitle?: string;
  userDisplayTag: string | null;
  conversations: ConversationItem[];
  activeConversationId?: number;
  messages: Message[];
  inputMessage: string;
  isLoading: boolean;
  messagesEndRef: React.RefObject<HTMLDivElement>;
  onInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  onSendMessage: () => void;
  onSelectConversation: (conversationId: number) => Promise<void> | void;
  onCreateConversation: () => void;
  onRenameConversation: (conversationId: number, title: string) => Promise<void>;
  onDeleteConversation: (conversationId: number) => Promise<void>;
  onPinConversation: (conversationId: number, pinned: boolean) => Promise<void>;
};

const DEFAULT_FEATURE_TITLE = 'AI超级智能体';

const ChatView: React.FC<ChatViewProps> = ({
  featureTitle = DEFAULT_FEATURE_TITLE,
  userDisplayTag,
  conversations,
  activeConversationId,
  messages,
  inputMessage,
  isLoading,
  messagesEndRef,
  onInputChange,
  onKeyDown,
  onSendMessage,
  onSelectConversation,
  onCreateConversation,
  onRenameConversation,
  onDeleteConversation,
  onPinConversation,
}) => {
  return (
    <div className="chat-layout">
      <ChatSidebar
        featureTitle={featureTitle}
        userDisplayTag={userDisplayTag}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={onSelectConversation}
        onCreateConversation={onCreateConversation}
        onRenameConversation={onRenameConversation}
        onDeleteConversation={onDeleteConversation}
        onPinConversation={onPinConversation}
      />

      <div className="chat-container">
        <div className="chat-mobile-topbar">
          <span className="chat-mobile-title">{featureTitle}</span>
        </div>

        <div className="chat-messages">
          {messages
            /* 后端在生成中可能已落库 question、但 ai_response 仍为空，避免渲染空白 AI 气泡 */
            .filter(m => m.isUser || m.content.trim())
            .map(message => (
            <div key={message.id} className={`message ${message.isUser ? 'user-message' : 'ai-message'}`}>
              <div className="message-content">{message.content}</div>
              <div className="message-time">{message.timestamp}</div>
            </div>
          ))}
          {isLoading && (
            <div className="message ai-message">
              <div className="message-content">
                <div className="loading-indicator">
                  <span className="loading-dot"></span>
                  <span className="loading-dot"></span>
                  <span className="loading-dot"></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-area">
          <input
            type="text"
            value={inputMessage}
            onChange={onInputChange}
            onKeyDown={onKeyDown}
            placeholder="请输入消息..."
            className="chat-input"
          />
          <button onClick={onSendMessage} className="send-button">
            发送
          </button>
        </div>
{/* 
        <div className="chat-footer">
          <div className="footer-left">鱼皮AI超级智能体应用平台</div>
          <div className="footer-center">友情链接</div>
          <div className="footer-right">联系我们</div>
        </div> */}
      </div>
    </div>
  );
};

const WELCOME_MESSAGE: Message = {
  id: 'welcome',
  content: '你好，我是AI超级智能体。我可以解答各类问题，提供专业建议，请问有什么可以帮助你的吗？',
  isUser: false,
  timestamp: new Date().toLocaleTimeString(),
};

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingConversationId, setLoadingConversationId] = useState<number | undefined>(undefined);
  const [conversationId, setConversationId] = useState<number | undefined>(undefined);
  const [userDisplayTag, setUserDisplayTag] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const conversationIdRef = useRef<number | undefined>(undefined);
  const logoutModalShownRef = useRef(false);
  const navigate = useNavigate();

  const handleForceLogout = useCallback((msg: string) => {
    if (logoutModalShownRef.current) return;
    logoutModalShownRef.current = true;

    Modal.warning({
      title: '登录状态失效',
      content: msg,
      okText: '退出登录',
      centered: true,
      onOk: () => {
        localStorage.removeItem('token');
        navigate('/login', { replace: true });
      },
    });
  }, [navigate]);

  const loadConversations = useCallback(async () => {
    const response = await getConversations();
    if (response?.success && response?.data?.conversations) {
      setConversations(response.data.conversations);
    }
  }, []);

  const handleRenameConversation = useCallback(
    async (id: number, title: string) => {
      const res = await patchConversation({ conversation_id: id, title });
      if (!res?.success) {
        message.error((res as { msg?: string })?.msg || '重命名失败');
        throw new Error('rename failed');
      }
      await loadConversations();
    },
    [loadConversations]
  );

  const handleDeleteConversation = useCallback(
    async (id: number) => {
      const res = await deleteConversation(id);
      if (!res?.success) {
        message.error((res as { msg?: string })?.msg || '删除失败');
        throw new Error('delete failed');
      }
      if (conversationId === id) {
        setIsLoading(false);
        setLoadingConversationId(undefined);
        setConversationId(undefined);
        setMessages([WELCOME_MESSAGE]);
      }
      await loadConversations();
    },
    [loadConversations, conversationId]
  );

  const handlePinConversation = useCallback(
    async (id: number, pinned: boolean) => {
      const res = await patchConversation({ conversation_id: id, pinned });
      if (!res?.success) {
        message.error((res as { msg?: string })?.msg || '操作失败');
        throw new Error('pin failed');
      }
      message.success(pinned ? '已置顶' : '已取消置顶');
      await loadConversations();
    },
    [loadConversations]
  );

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      handleForceLogout('登录已失效，请重新登录');
      return;
    }

    void loadConversations();
    void (async () => {
      try {
        const res = await getUserInfo();
        if (res?.success && res?.data?.display_tag) {
          setUserDisplayTag(String(res.data.display_tag));
        }
      } catch {
        /* ignore */
      }
    })();
  }, [handleForceLogout, loadConversations]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  const handleSelectConversation = async (selectedConversationId: number): Promise<void> => {
    try {
      const response = await getConversationMessages(selectedConversationId);
      if (!response?.success) return;

      const history = response?.data?.messages || [];
      const mapped: Message[] = [];

      history.forEach((item: { id: number; question: string; ai_response: string; created_at: string }) => {
        mapped.push({
          id: `u-${item.id}`,
          content: item.question,
          isUser: true,
          timestamp: item.created_at,
        });
        const reply = String(item.ai_response ?? '').trim();
        if (reply) {
          mapped.push({
            id: `a-${item.id}`,
            content: reply,
            isUser: false,
            timestamp: item.created_at,
          });
        }
      });

      setConversationId(selectedConversationId);
      setMessages(mapped.length ? mapped : [WELCOME_MESSAGE]);
    } catch {
      return;
    }
  };

  const handleCreateConversation = () => {
    setConversationId(undefined);
    setMessages([WELCOME_MESSAGE]);
  };

  const handleSendMessage = async () => {
    const messageText = inputMessage.trim();
    if (!messageText) return;

    const startConversationId = conversationIdRef.current;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: messageText,
      isUser: true,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setLoadingConversationId(startConversationId);

    try {
      const response = await chatWithAgent(messageText, conversationId);

      if (response?.success === false && (response?.msg || '').includes('认证失败')) {
        handleForceLogout('登录已失效，请重新登录');
        return;
      }

      if (response?.data?.conversation_id) {
        // 新建会话时 loading 归属需要切换到后端返回的 conversation_id
        if (conversationIdRef.current === startConversationId) {
          setConversationId(response.data.conversation_id);
          setLoadingConversationId(response.data.conversation_id);
        }
      }

      // 如果用户在请求期间切换了会话，则不再把这次 AI 回复追加到其它会话里
      if (conversationIdRef.current !== startConversationId) {
        await loadConversations();
        return;
      }

      const aiReply = response?.data?.reply || response?.msg || '模型暂无回复';
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: aiReply,
        isUser: false,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages(prev => [...prev, aiMessage]);
      await loadConversations();
    } catch (error) {
      const err = error as {
        response?: { data?: { msg?: string; message?: string }; status?: number };
        message?: string;
      };
      const errorMessage =
        err?.response?.data?.msg ||
        err?.response?.data?.message ||
        err?.message ||
        '调用失败，请稍后重试';

      if (err?.response?.status === 401 || errorMessage.includes('认证失败')) {
        handleForceLogout('登录已失效，请重新登录');
        return;
      }

      // 请求期间若已切换会话，不追加错误信息到其它会话
      if (conversationIdRef.current !== startConversationId) {
        await loadConversations();
        return;
      }

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: errorMessage,
        isUser: false,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages(prev => [...prev, aiMessage]);
    } finally {
      setIsLoading(false);
      setLoadingConversationId(undefined);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // 只在“发起请求的那个会话”上展示 loading 动画
  const showLoading = isLoading && loadingConversationId === conversationId;

  return (
    <div className="chat-page-shell">
      <ChatView
        featureTitle={DEFAULT_FEATURE_TITLE}
        userDisplayTag={userDisplayTag}
        conversations={conversations}
        activeConversationId={conversationId}
        messages={messages}
        inputMessage={inputMessage}
        isLoading={showLoading}
        messagesEndRef={messagesEndRef}
        onInputChange={(e) => setInputMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        onSendMessage={handleSendMessage}
        onSelectConversation={handleSelectConversation}
        onCreateConversation={handleCreateConversation}
        onRenameConversation={handleRenameConversation}
        onDeleteConversation={handleDeleteConversation}
        onPinConversation={handlePinConversation}
      />
    </div>
  );
};

export default Chat;
