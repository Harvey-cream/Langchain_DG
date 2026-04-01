import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Modal } from 'antd';
import { chatWithAgent, getConversations, getConversationMessages } from '../../services/api';
import ChatSidebar, { ConversationItem } from './ChatSidebar';
import './Chat.css';

interface Message {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: string;
}

type ChatViewProps = {
  conversations: ConversationItem[];
  activeConversationId?: number;
  messages: Message[];
  inputMessage: string;
  isLoading: boolean;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  onInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  onSendMessage: () => void;
  onBack: () => void;
  onSelectConversation: (conversationId: number) => Promise<void> | void;
  onCreateConversation: () => void;
};

const ChatView: React.FC<ChatViewProps> = ({
  conversations,
  activeConversationId,
  messages,
  inputMessage,
  isLoading,
  messagesEndRef,
  onInputChange,
  onKeyDown,
  onSendMessage,
  onBack,
  onSelectConversation,
  onCreateConversation,
}) => {
  return (
    <div className="chat-layout">
      <ChatSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={onSelectConversation}
        onCreateConversation={onCreateConversation}
      />

      <div className="chat-container">
        <div className="chat-header">
          <button className="back-button" onClick={onBack}>
            ← 返回
          </button>
          <h1>AI超级智能体</h1>
        </div>

        <div className="chat-messages">
          {messages.map(message => (
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

        <div className="chat-footer">
          <div className="footer-left">鱼皮AI超级智能体应用平台</div>
          <div className="footer-center">友情链接</div>
          <div className="footer-right">联系我们</div>
        </div>
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
  const [conversationId, setConversationId] = useState<number | undefined>(undefined);
  const messagesEndRef = useRef<HTMLDivElement>(null);
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

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      handleForceLogout('登录已失效，请重新登录');
      return;
    }

    void loadConversations();
  }, [handleForceLogout, loadConversations]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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
        mapped.push({
          id: `a-${item.id}`,
          content: item.ai_response,
          isUser: false,
          timestamp: item.created_at,
        });
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

    const userMessage: Message = {
      id: Date.now().toString(),
      content: messageText,
      isUser: true,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await chatWithAgent(messageText, conversationId);

      if (response?.success === false && (response?.msg || '').includes('认证失败')) {
        handleForceLogout('登录已失效，请重新登录');
        return;
      }

      if (response?.data?.conversation_id) {
        setConversationId(response.data.conversation_id);
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

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: errorMessage,
        isUser: false,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages(prev => [...prev, aiMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <ChatView
      conversations={conversations}
      activeConversationId={conversationId}
      messages={messages}
      inputMessage={inputMessage}
      isLoading={isLoading}
      messagesEndRef={messagesEndRef}
      onInputChange={(e) => setInputMessage(e.target.value)}
      onKeyDown={handleKeyDown}
      onSendMessage={handleSendMessage}
      onBack={() => navigate('/')}
      onSelectConversation={handleSelectConversation}
      onCreateConversation={handleCreateConversation}
    />
  );
};

export default Chat;
