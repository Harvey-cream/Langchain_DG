import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Modal, message } from 'antd';
import { CopyOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import { getUserInfo } from '../../services/api';
import type { ChatApiClient } from '../../services/chatApi';
import { formatAssistantDisplayText } from '../../services/chatStream';
import ChatSidebar, { ConversationItem } from './ChatSidebar';
import './Chat.css';

export interface Message {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: string;
}

export type ChatPageProps = {
  featureTitle: string;
  welcomeMessage: Message;
  /** 会话与流式接口：超级智能体与面试大师分别使用不同后端路径与数据表 */
  chatApi: ChatApiClient;
};

type ChatViewProps = {
  featureTitle: string;
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
  streamActive: boolean;
  onStopStream: () => void;
  onSelectConversation: (conversationId: number) => Promise<void> | void;
  onCreateConversation: () => void;
  onRenameConversation: (conversationId: number, title: string) => Promise<void>;
  onDeleteConversation: (conversationId: number) => Promise<void>;
  onPinConversation: (conversationId: number, pinned: boolean) => Promise<void>;
  /** 当前 SSE 正在写入的助手消息 id；流式阶段纯文本，结束后 Markdown */
  streamingAssistantId: string | null;
};

function extractPlainText(node: React.ReactNode): string {
  if (node == null || node === false) return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(extractPlainText).join('');
  if (React.isValidElement(node) && node.props && typeof node.props === 'object' && node.props !== null && 'children' in node.props) {
    return extractPlainText((node.props as { children?: React.ReactNode }).children);
  }
  return '';
}

async function copyToClipboard(text: string): Promise<void> {
  await navigator.clipboard.writeText(text);
}

const CHAT_MD_COMPONENTS: Components = {
  pre: ({ children }: { children?: React.ReactNode }) => {
    const raw = extractPlainText(children).replace(/\n$/, '');
    return (
      <div className="chat-pre-wrap">
        <button
          type="button"
          className="chat-code-copy"
          onClick={() => {
            void copyToClipboard(raw).then(
              () => message.success('代码已复制'),
              () => message.error('复制失败')
            );
          }}
        >
          复制
        </button>
        <pre className="chat-pre">{children}</pre>
      </div>
    );
  },
};

/** 流式中：纯文本增量（避免每帧全量 remark 解析）；结束后：Markdown */
const AssistantBubbleContent = React.memo(function AssistantBubbleContent({
  rawContent,
  isStreaming,
}: {
  rawContent: string;
  isStreaming: boolean;
}) {
  const aiDisplay = formatAssistantDisplayText(rawContent);
  const remarkPlugins = useMemo(() => [remarkGfm], []);

  const aiPending =
    isStreaming && !aiDisplay.trim() && rawContent.trim().length > 0;

  if (aiPending) {
    return <span className="chat-assistant-pending">正在生成回复…</span>;
  }
  if (!aiDisplay.trim()) {
    return <span className="chat-assistant-fallback">（无有效回复）</span>;
  }

  if (isStreaming) {
    return <div className="chat-stream-plain">{aiDisplay}</div>;
  }

  return (
    <div className="chat-markdown">
      <ReactMarkdown remarkPlugins={remarkPlugins} components={CHAT_MD_COMPONENTS}>
        {aiDisplay}
      </ReactMarkdown>
    </div>
  );
});

const ChatView: React.FC<ChatViewProps> = ({
  featureTitle,
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
  streamActive,
  onStopStream,
  onSelectConversation,
  onCreateConversation,
  onRenameConversation,
  onDeleteConversation,
  onPinConversation,
  streamingAssistantId,
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
            .filter(m => m.isUser || m.content.trim())
            .map(msg => {
              const aiDisplay = msg.isUser ? '' : formatAssistantDisplayText(msg.content);
              const streamThis =
                !msg.isUser && streamActive && streamingAssistantId === msg.id;
              return (
            <div key={msg.id} className={`message ${msg.isUser ? 'user-message' : 'ai-message'}`}>
              <div className="message-bubble-row">
                <div
                  className={`message-content ${msg.isUser ? '' : 'message-content-md'}`}
                >
                  {msg.isUser ? (
                    msg.content
                  ) : (
                    <AssistantBubbleContent
                      rawContent={msg.content}
                      isStreaming={streamThis}
                    />
                  )}
                </div>
                {!msg.isUser && (
                  <button
                    type="button"
                    className="message-copy-fab"
                    title="复制可见正文"
                    aria-label="复制可见正文"
                    onClick={() => {
                      const text = aiDisplay.trim();
                      if (!text) {
                        message.warning('暂无可复制的正文');
                        return;
                      }
                      void copyToClipboard(text).then(
                        () => message.success('已复制'),
                        () => message.error('复制失败')
                      );
                    }}
                  >
                    <CopyOutlined />
                  </button>
                )}
              </div>
              <div className="message-time">{msg.timestamp}</div>
            </div>
              );
            })}
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
          {streamActive ? (
            <button type="button" onClick={onStopStream} className="send-button send-button-stop">
              中止
            </button>
          ) : (
            <button type="button" onClick={onSendMessage} className="send-button">
              发送
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

const ChatPage: React.FC<ChatPageProps> = ({ featureTitle, welcomeMessage, chatApi }) => {
  const [messages, setMessages] = useState<Message[]>(() => [welcomeMessage]);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingConversationId, setLoadingConversationId] = useState<number | undefined>(undefined);
  const [conversationId, setConversationId] = useState<number | undefined>(undefined);
  const [userDisplayTag, setUserDisplayTag] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const conversationIdRef = useRef<number | undefined>(undefined);
  const logoutModalShownRef = useRef(false);
  const streamAbortRef = useRef<AbortController | null>(null);
  const userAbortRef = useRef(false);
  const streamActiveRef = useRef(false);
  const [streamActive, setStreamActive] = useState(false);
  /** 流式写入中的助手气泡 id：用于纯文本渲染 + RAF 合并后同步 content */
  const [streamingAssistantId, setStreamingAssistantId] = useState<string | null>(null);
  const streamAccumRef = useRef<{ msgId: string | null; text: string }>({ msgId: null, text: '' });
  const streamFlushRafRef = useRef<number | null>(null);
  const scrollRafRef = useRef<number | null>(null);
  const navigate = useNavigate();

  const flushStreamContent = useCallback(() => {
    streamFlushRafRef.current = null;
    const { msgId, text } = streamAccumRef.current;
    if (!msgId) return;
    setMessages(prev => prev.map(m => (m.id === msgId ? { ...m, content: text } : m)));
  }, []);

  const scheduleStreamFlush = useCallback(() => {
    if (streamFlushRafRef.current != null) return;
    streamFlushRafRef.current = requestAnimationFrame(() => {
      flushStreamContent();
    });
  }, [flushStreamContent]);

  const handleStopStream = useCallback(() => {
    userAbortRef.current = true;
    streamAbortRef.current?.abort();
  }, []);

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
    const response = await chatApi.getConversations();
    if (response?.success && response?.data?.conversations) {
      setConversations(response.data.conversations);
    }
  }, [chatApi]);

  const handleRenameConversation = useCallback(
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

  const handleDeleteConversation = useCallback(
    async (id: number) => {
      const res = await chatApi.deleteConversation(id);
      if (!res?.success) {
        message.error((res as { msg?: string })?.msg || '删除失败');
        throw new Error('delete failed');
      }
      if (conversationId === id) {
        streamAbortRef.current?.abort();
        streamActiveRef.current = false;
        setStreamActive(false);
        setStreamingAssistantId(null);
        setIsLoading(false);
        setLoadingConversationId(undefined);
        setConversationId(undefined);
        setMessages([welcomeMessage]);
      }
      await loadConversations();
    },
    [chatApi, loadConversations, conversationId, welcomeMessage]
  );

  const handlePinConversation = useCallback(
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
    if (scrollRafRef.current != null) {
      cancelAnimationFrame(scrollRafRef.current);
    }
    scrollRafRef.current = requestAnimationFrame(() => {
      scrollRafRef.current = null;
      messagesEndRef.current?.scrollIntoView({
        behavior: streamActive ? 'auto' : 'smooth',
        block: 'end',
      });
    });
    return () => {
      if (scrollRafRef.current != null) {
        cancelAnimationFrame(scrollRafRef.current);
      }
    };
  }, [messages, streamActive]);

  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  const handleSelectConversation = async (selectedConversationId: number): Promise<void> => {
    try {
      const response = await chatApi.getConversationMessages(selectedConversationId);
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
      setMessages(mapped.length ? mapped : [welcomeMessage]);
    } catch {
      return;
    }
  };

  const handleCreateConversation = () => {
    setConversationId(undefined);
    setMessages([welcomeMessage]);
  };

  const handleSendMessage = async () => {
    if (streamActiveRef.current) return;

    const messageText = inputMessage.trim();
    if (!messageText) return;

    const startConversationId = conversationIdRef.current;

    userAbortRef.current = false;
    const abortController = new AbortController();
    streamAbortRef.current = abortController;
    streamActiveRef.current = true;
    setStreamActive(true);

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

    let streamingMsgId: string | null = null;

    try {
      await chatApi.chatWithStream(
        messageText,
        conversationId,
        {
        onMeta: ({ conversation_id }) => {
          if (conversationIdRef.current === startConversationId) {
            setConversationId(conversation_id);
            setLoadingConversationId(conversation_id);
          }
        },
        onDelta: text => {
          if (conversationIdRef.current !== startConversationId) return;
          if (!streamingMsgId) {
            const id = `ai-${Date.now()}`;
            streamingMsgId = id;
            streamAccumRef.current = { msgId: id, text };
            setStreamingAssistantId(id);
            setIsLoading(false);
            setMessages(prev => [
              ...prev,
              {
                id,
                content: text,
                isUser: false,
                timestamp: new Date().toLocaleTimeString(),
              },
            ]);
            return;
          }
          streamAccumRef.current.text += text;
          scheduleStreamFlush();
        },
        onError: errText => {
          if (conversationIdRef.current !== startConversationId) return;
          const line = `\n\n[错误] ${errText}`;
          if (!streamingMsgId) {
            const id = `ai-${Date.now()}`;
            streamingMsgId = id;
            streamAccumRef.current = { msgId: id, text: line.trim() };
            setStreamingAssistantId(id);
            setIsLoading(false);
            setMessages(prev => [
              ...prev,
              {
                id,
                content: line.trim(),
                isUser: false,
                timestamp: new Date().toLocaleTimeString(),
              },
            ]);
          } else {
            streamAccumRef.current.text += line;
            setMessages(prev =>
              prev.map(m =>
                m.id === streamingMsgId ? { ...m, content: streamAccumRef.current.text } : m
              )
            );
          }
        },
        onDone: () => {
          void loadConversations();
        },
      },
        { signal: abortController.signal }
      );

      if (conversationIdRef.current !== startConversationId) {
        await loadConversations();
        return;
      }

      if (!streamingMsgId) {
        setMessages(prev => [
          ...prev,
          {
            id: `ai-${Date.now()}`,
            content: '（模型未返回内容）',
            isUser: false,
            timestamp: new Date().toLocaleTimeString(),
          },
        ]);
      }
    } catch (error) {
      const err = error as { name?: string; message?: string };
      if (err?.name === 'AbortError') {
        const userStopped = userAbortRef.current;
        if (userStopped) {
          message.info('已中止生成');
        } else {
          message.warning('长时间未收到模型输出，连接已中断');
        }
        const tail = userStopped ? '（已中止）' : '（已中断：长时间无数据）';
        if (conversationIdRef.current === startConversationId) {
          if (!streamingMsgId) {
            setMessages(prev => [
              ...prev,
              {
                id: `ai-${Date.now()}`,
                content: tail,
                isUser: false,
                timestamp: new Date().toLocaleTimeString(),
              },
            ]);
          } else {
            setMessages(prev =>
              prev.map(m =>
                m.id === streamingMsgId ? { ...m, content: `${m.content}\n\n${tail}` } : m
              )
            );
          }
        }
        return;
      }

      const errorMessage = err?.message || '调用失败，请稍后重试';
      if (errorMessage.includes('认证失败') || errorMessage.includes('未登录')) {
        handleForceLogout('登录已失效，请重新登录');
        return;
      }

      if (conversationIdRef.current !== startConversationId) {
        await loadConversations();
        return;
      }

      if (!streamingMsgId) {
        setMessages(prev => [
          ...prev,
          {
            id: `ai-${Date.now()}`,
            content: errorMessage,
            isUser: false,
            timestamp: new Date().toLocaleTimeString(),
          },
        ]);
      } else {
        setMessages(prev =>
          prev.map(m =>
            m.id === streamingMsgId ? { ...m, content: m.content || errorMessage } : m
          )
        );
      }
    } finally {
      if (streamFlushRafRef.current != null) {
        cancelAnimationFrame(streamFlushRafRef.current);
        streamFlushRafRef.current = null;
      }
      flushStreamContent();
      streamAccumRef.current = { msgId: null, text: '' };
      setStreamingAssistantId(null);
      streamActiveRef.current = false;
      setStreamActive(false);
      streamAbortRef.current = null;
      setIsLoading(false);
      setLoadingConversationId(undefined);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (streamActiveRef.current) return;
      void handleSendMessage();
    }
  };

  const showLoading = isLoading && loadingConversationId === conversationId;

  return (
    <div className="chat-page-shell">
      <ChatView
        featureTitle={featureTitle}
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
        streamActive={streamActive}
        onStopStream={handleStopStream}
        onSelectConversation={handleSelectConversation}
        onCreateConversation={handleCreateConversation}
        onRenameConversation={handleRenameConversation}
        onDeleteConversation={handleDeleteConversation}
        onPinConversation={handlePinConversation}
        streamingAssistantId={streamingAssistantId}
      />
    </div>
  );
};

export default ChatPage;
