import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { message } from 'antd';
import ReactMarkdown from 'react-markdown';
import { createRoot, type Root } from 'react-dom/client';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import type { Components } from 'react-markdown';
import { getUserInfo } from '../../services/api';
import { expireAuthSession, handleUnauthorizedStatus } from '../../services/authSession';
import type { ChatApiClient } from '../../services/chatApi';
import {
  estimateChatStreamPayloadBytes,
  formatAssistantDisplayText,
  MAX_CHAT_STREAM_PAYLOAD_BYTES,
  PAYLOAD_TOO_LARGE_MESSAGE,
  type ChatAttachment,
  type WebSource,
} from '../../services/chatStream';
import ChatSidebar from './ChatSidebar';
import { ChatInput } from '../../features/chat/components/ChatInput';
import { MessageList } from '../../features/chat/components/MessageList';
import { useChatAttachments } from '../../features/chat/hooks/useChatAttachments';
import { useConversation, type ConversationItem } from '../../features/chat/hooks/useConversation';
import './Chat.css';

export interface Message {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: string;
  attachments?: ChatAttachment[];
  /** 本轮强制联网搜索回来的来源（仅助手消息） */
  webSources?: WebSource[];
}

export type ChatPageProps = {
  featureTitle: string;
  welcomeMessage: Message;
  /** 会话与流式接口：产品线通过 ChatApiClient 使用不同后端路径与数据表 */
  chatApi: ChatApiClient;
};

type ChatViewProps = {
  featureTitle: string;
  userDisplayTag: string | null;
  conversations: ConversationItem[];
  activeConversationId?: number;
  messages: Message[];
  inputMessage: string;
  attachments: ChatAttachment[];
  isLoading: boolean;
  messagesEndRef: React.RefObject<HTMLDivElement>;
  messagesContainerRef: React.RefObject<HTMLDivElement>;
  onInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  onSendMessage: () => void;
  onAttachFiles: (files: FileList | null) => void;
  onRemoveAttachment: (id: string) => void;
  enableWebSearch: boolean;
  onToggleWebSearch: () => void;
  streamActive: boolean;
  onStopStream: () => void;
  onSelectConversation: (conversationId: number) => Promise<void> | void;
  onCreateConversation: () => void;
  onRenameConversation: (conversationId: number, title: string) => Promise<void>;
  onDeleteConversation: (conversationId: number) => Promise<void>;
  onPinConversation: (conversationId: number, pinned: boolean) => Promise<void>;
  /** 当前 SSE 正在写入的助手消息 id；流式阶段纯文本，结束后 Markdown */
  streamingAssistantId: string | null;
  /** 流式正文直写 DOM，避免每 token setMessages 触发整表 reconcile */
  streamingContentRef: React.MutableRefObject<HTMLDivElement | null>;
  /** 流式中复制「当前可见清洗正文」 */
  getStreamingFormatted?: () => string;
  /** LangGraph PDF 确认条（按钮 true/false 走 resume_pdf_export） */
  pdfExportPrompt: { kind: string; message: string } | null;
  /** 与哪一条助手消息合并到同一气泡（interrupt 时的 streaming 气泡 id） */
  pdfExportHostMessageId: string | null;
  onPdfExportConfirm: () => void;
  onPdfExportCancel: () => void;
  inputLocked: boolean;
  loadingStatusText?: string | null;
  webSources?: WebSource[];
};

/** 网络层 delta 合并：防重复片段、累计全文、后缀重叠去重 */
function mergeStreamingDelta(previous: string, incoming: string): string {
  const prev = previous || '';
  const next = incoming || '';
  if (!prev) return next;
  if (!next) return prev;
  if (next === prev || prev.endsWith(next)) return prev;
  if (next.startsWith(prev)) return next;
  const maxOverlap = Math.min(prev.length, next.length, 256);
  for (let i = maxOverlap; i >= 1; i -= 1) {
    if (prev.slice(-i) === next.slice(0, i)) {
      return prev + next.slice(i);
    }
  }
  return prev + next;
}

function sanitizeWebSources(sources: WebSource[]): WebSource[] {
  const seen = new Set<string>();
  const out: WebSource[] = [];
  for (const s of sources) {
    const url = (s.url || '').trim();
    if (!url || seen.has(url)) continue;
    if (/\.(png|jpe?g|gif|webp|svg|ico|css|js|woff2?)(\?|#|$)/i.test(url)) continue;
    if (
      /(alicdn\.com|cdn\.|static\.|\.img\.|img\.|\.cloudfront\.|googleapis\.com\/.*\/image)/i.test(
        url,
      )
    )
      continue;
    seen.add(url);
    out.push({ title: (s.title || '').trim() || url, url });
  }
  return out;
}

function extractPlainText(node: React.ReactNode): string {
  if (node == null || node === false) return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(extractPlainText).join('');
  if (
    React.isValidElement(node) &&
    node.props &&
    typeof node.props === 'object' &&
    node.props !== null &&
    'children' in node.props
  ) {
    return extractPlainText((node.props as { children?: React.ReactNode }).children);
  }
  return '';
}

/** HTTP / 非安全上下文中 Clipboard API 不可用，需 execCommand 降级（与线上 IP+「不安全」一致） */
function copyToClipboardFallback(text: string): void {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.setAttribute('readonly', '');
  ta.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0;pointer-events:none;';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  ta.setSelectionRange(0, text.length);
  let ok = false;
  try {
    ok = document.execCommand('copy');
  } finally {
    document.body.removeChild(ta);
  }
  if (!ok) {
    throw new Error('execCommand copy failed');
  }
}

async function copyToClipboard(text: string): Promise<void> {
  if (
    typeof navigator !== 'undefined' &&
    window.isSecureContext &&
    navigator.clipboard?.writeText
  ) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      /* 权限等失败时降级 */
    }
  }
  copyToClipboardFallback(text);
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
              () => message.error('复制失败'),
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
const CHAT_REMARK_PLUGINS = [remarkGfm, remarkBreaks];

/** 流式中：纯文本增量（避免每帧全量 remark 解析）；结束后：Markdown */
const ChatView: React.FC<ChatViewProps> = ({
  featureTitle,
  userDisplayTag,
  conversations,
  activeConversationId,
  messages,
  inputMessage,
  attachments,
  isLoading,
  messagesEndRef,
  messagesContainerRef,
  onInputChange,
  onKeyDown,
  onSendMessage,
  onAttachFiles,
  onRemoveAttachment,
  enableWebSearch,
  onToggleWebSearch,
  streamActive,
  onStopStream,
  onSelectConversation,
  onCreateConversation,
  onRenameConversation,
  onDeleteConversation,
  onPinConversation,
  streamingAssistantId,
  streamingContentRef,
  getStreamingFormatted,
  pdfExportPrompt,
  pdfExportHostMessageId,
  onPdfExportConfirm,
  onPdfExportCancel,
  inputLocked,
  loadingStatusText,
  webSources,
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

        <MessageList
          messages={messages}
          isLoading={isLoading}
          messagesEndRef={messagesEndRef}
          messagesContainerRef={messagesContainerRef}
          streamActive={streamActive}
          streamingAssistantId={streamingAssistantId}
          streamingContentRef={streamingContentRef}
          getStreamingFormatted={getStreamingFormatted}
          pdfExportPrompt={pdfExportPrompt}
          pdfExportHostMessageId={pdfExportHostMessageId}
          onPdfExportConfirm={onPdfExportConfirm}
          onPdfExportCancel={onPdfExportCancel}
          loadingStatusText={loadingStatusText}
          webSources={webSources}
        />

        <ChatInput
          inputMessage={inputMessage}
          attachments={attachments}
          inputLocked={inputLocked}
          enableWebSearch={enableWebSearch}
          streamActive={streamActive}
          onInputChange={onInputChange}
          onKeyDown={onKeyDown}
          onSendMessage={onSendMessage}
          onAttachFiles={onAttachFiles}
          onRemoveAttachment={onRemoveAttachment}
          onToggleWebSearch={onToggleWebSearch}
          onStopStream={onStopStream}
        />
      </div>
    </div>
  );
};

const ChatPage: React.FC<ChatPageProps> = ({ featureTitle, welcomeMessage, chatApi }) => {
  const [messages, setMessages] = useState<Message[]>(() => [welcomeMessage]);
  const [inputMessage, setInputMessage] = useState('');
  const { pathname } = useLocation();
  const activeConversationStorageKey = `chat.activeConversationId:${pathname}`;
  const pendingAttachmentStorageKey = `chat.pendingAttachments:${pathname}`;
  const {
    attachments: pendingAttachments,
    addFiles: handleAttachFiles,
    removeAttachment: handleRemoveAttachment,
    clearAttachments,
  } = useChatAttachments(pendingAttachmentStorageKey);
  const {
    conversations,
    loadConversations,
    renameConversation,
    deleteConversation,
    pinConversation,
  } = useConversation(chatApi);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingConversationId, setLoadingConversationId] = useState<number | undefined>(undefined);
  const [conversationId, setConversationId] = useState<number | undefined>(undefined);
  const [enableWebSearch, setEnableWebSearch] = useState(false);
  const [loadingStatusText, setLoadingStatusText] = useState<string | null>(null);
  const [webSources, setWebSources] = useState<WebSource[]>([]);
  const pendingWebSourcesRef = useRef<WebSource[]>([]);
  const [pdfExportPrompt, setPdfExportPrompt] = useState<{ kind: string; message: string } | null>(
    null,
  );
  const [pdfExportHostMessageId, setPdfExportHostMessageId] = useState<string | null>(null);
  const [userDisplayTag, setUserDisplayTag] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const conversationIdRef = useRef<number | undefined>(undefined);
  const streamAbortRef = useRef<AbortController | null>(null);
  const userAbortRef = useRef(false);
  const streamActiveRef = useRef(false);
  const [streamActive, setStreamActive] = useState(false);
  /** 流式写入中的助手气泡 id：用于纯文本渲染 + RAF 合并后同步 content */
  const [streamingAssistantId, setStreamingAssistantId] = useState<string | null>(null);
  const streamAccumRef = useRef<{ msgId: string | null; text: string }>({ msgId: null, text: '' });
  const streamFlushRafRef = useRef<number | null>(null);
  const typewriterRafRef = useRef<number | null>(null);
  const typewriterRevealLenRef = useRef(0);
  /** SSE 已 stream_done（正文流结束），等打字机追上全文后再关流式态、对账 */
  const pendingStreamEndRef = useRef(false);
  const scrollRafRef = useRef<number | null>(null);
  const shouldStickToBottomRef = useRef(true);
  const streamSessionIdRef = useRef<number | null>(null);
  /** 流式助手气泡：直写 DOM，避免每个 delta 触发 messages 全量更新 */
  const streamingContentRef = useRef<HTMLDivElement | null>(null);
  const streamingRenderRootRef = useRef<Root | null>(null);
  const streamingRenderHostRef = useRef<HTMLDivElement | null>(null);

  const disposeStreamingDomRenderer = useCallback(() => {
    if (streamingRenderRootRef.current) {
      streamingRenderRootRef.current.unmount();
      streamingRenderRootRef.current = null;
    }
    streamingRenderHostRef.current = null;
  }, []);

  const persistActiveConversationId = useCallback(
    (id: number | undefined) => {
      if (id == null) {
        localStorage.removeItem(activeConversationStorageKey);
        return;
      }
      localStorage.setItem(activeConversationStorageKey, String(id));
    },
    [activeConversationStorageKey],
  );

  const cancelTypewriter = useCallback(() => {
    if (typewriterRafRef.current != null) {
      cancelAnimationFrame(typewriterRafRef.current);
      typewriterRafRef.current = null;
    }
  }, []);

  const handleStopStream = useCallback(() => {
    userAbortRef.current = true;
    streamAbortRef.current?.abort();
  }, []);

  const handleForceLogout = useCallback((_message: string) => {
    expireAuthSession();
  }, []);

  const handleDeleteConversation = useCallback(
    async (id: number) => {
      await deleteConversation(id);
      if (conversationId === id) {
        streamAbortRef.current?.abort();
        cancelTypewriter();
        pendingStreamEndRef.current = false;
        streamActiveRef.current = false;
        setStreamActive(false);
        setStreamingAssistantId(null);
        setIsLoading(false);
        setLoadingConversationId(undefined);
        setConversationId(undefined);
        persistActiveConversationId(undefined);
        setMessages([welcomeMessage]);
      }
    },
    [
      deleteConversation,
      conversationId,
      welcomeMessage,
      cancelTypewriter,
      persistActiveConversationId,
    ],
  );

  const handleRenameConversation = useCallback(
    async (id: number, title: string) => {
      await renameConversation(id, title);
    },
    [renameConversation],
  );

  const handlePinConversation = useCallback(
    async (id: number, pinned: boolean) => {
      await pinConversation(id, pinned);
    },
    [pinConversation],
  );

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      handleForceLogout('登录已失效，请重新登录');
      return;
    }

    void (async () => {
      try {
        const items = await loadConversations();
        const raw = localStorage.getItem(activeConversationStorageKey);
        const restoredId = raw ? Number(raw) : NaN;
        const canRestore = Number.isInteger(restoredId) && items.some((c) => c.id === restoredId);
        if (canRestore) {
          await handleSelectConversation(restoredId);
        } else {
          persistActiveConversationId(undefined);
        }
      } catch {
        message.error('加载会话列表失败，请确认后端已启动后刷新页面');
      }

      try {
        const res = await getUserInfo();
        if (res?.success && res?.data?.display_tag) {
          setUserDisplayTag(String(res.data.display_tag));
        }
      } catch {
        /* ignore */
      }
    })();
  }, [
    handleForceLogout,
    loadConversations,
    activeConversationStorageKey,
    persistActiveConversationId,
  ]);

  const updateStickToBottom = useCallback(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    shouldStickToBottomRef.current = distanceToBottom <= 80;
  }, []);

  const scrollToBottomIfStuck = useCallback(() => {
    if (!shouldStickToBottomRef.current) return;
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'auto', block: 'end' });
    });
  }, []);

  const writeStreamingDom = useCallback(
    (full: string, streaming: boolean) => {
      const host = streamingContentRef.current;
      if (!host) return false;
      if (streamingRenderHostRef.current !== host) {
        disposeStreamingDomRenderer();
        streamingRenderHostRef.current = host;
        streamingRenderRootRef.current = createRoot(host);
      }
      const root = streamingRenderRootRef.current;
      if (!root) return false;
      const display = formatAssistantDisplayText(full, { streaming });
      root.render(
        display.trim() ? (
          <ReactMarkdown remarkPlugins={CHAT_REMARK_PLUGINS} components={CHAT_MD_COMPONENTS}>
            {display}
          </ReactMarkdown>
        ) : (
          <span className="chat-assistant-pending">正在生成回复…</span>
        ),
      );
      scrollToBottomIfStuck();
      return true;
    },
    [disposeStreamingDomRenderer, scrollToBottomIfStuck],
  );

  const getStreamingFormatted = useCallback(
    () => formatAssistantDisplayText(streamAccumRef.current.text, { streaming: true }),
    [],
  );

  useEffect(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const onScroll = () => updateStickToBottom();
    el.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => el.removeEventListener('scroll', onScroll);
  }, [updateStickToBottom]);

  useEffect(() => {
    if (!streamActive && !shouldStickToBottomRef.current) {
      return;
    }
    if (scrollRafRef.current != null) {
      cancelAnimationFrame(scrollRafRef.current);
    }
    scrollRafRef.current = requestAnimationFrame(() => {
      scrollRafRef.current = null;
      messagesEndRef.current?.scrollIntoView({
        behavior: 'auto',
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

  useEffect(() => {
    if (!streamActive) {
      disposeStreamingDomRenderer();
    }
  }, [disposeStreamingDomRenderer, streamActive]);

  useEffect(() => () => disposeStreamingDomRenderer(), [disposeStreamingDomRenderer]);

  useEffect(() => () => cancelTypewriter(), [cancelTypewriter]);

  const handleSelectConversation = async (selectedConversationId: number): Promise<void> => {
    try {
      const response = await chatApi.getConversationMessages(selectedConversationId);
      if (!response?.success) return;

      const history = response?.data?.messages || [];
      const mapped: Message[] = [];

      history.forEach(
        (item: {
          id: number;
          question: string;
          ai_response: string;
          created_at: string;
          web_sources?: WebSource[];
          status?: string;
        }) => {
          mapped.push({
            id: `u-${item.id}`,
            content: item.question,
            isUser: true,
            timestamp: item.created_at,
          });
          const reply = String(item.ai_response ?? '').trim();
          const sources = Array.isArray(item.web_sources)
            ? item.web_sources.filter((s) => s?.url)
            : undefined;
          // generating 且尚无正文：开流占位，刷新时跳过助手气泡
          if (item.status === 'generating' && !reply) {
            return;
          }
          if (reply || (sources && sources.length > 0)) {
            mapped.push({
              id: `a-${item.id}`,
              content: reply,
              isUser: false,
              timestamp: item.created_at,
              webSources: sources?.length ? sources : undefined,
            });
          }
        },
      );
      setConversationId(selectedConversationId);
      persistActiveConversationId(selectedConversationId);
      setPdfExportPrompt(null);
      setPdfExportHostMessageId(null);
      setWebSources([]);
      pendingWebSourcesRef.current = [];
      setMessages(mapped.length ? mapped : [welcomeMessage]);
    } catch {
      return;
    }
  };

  const handleCreateConversation = () => {
    setConversationId(undefined);
    persistActiveConversationId(undefined);
    setPdfExportPrompt(null);
    setPdfExportHostMessageId(null);
    setWebSources([]);
    pendingWebSourcesRef.current = [];
    setMessages([welcomeMessage]);
  };

  const reconcileStreamingMessageFromServer = useCallback(
    async (
      targetConversationId: number,
      localStreamingMsgId: string | null,
      sessionId: number | null,
    ) => {
      if (!localStreamingMsgId) return;
      try {
        const response = await chatApi.getConversationMessages(
          targetConversationId,
          sessionId ?? undefined,
        );
        if (!response?.success) return;
        const history = response?.data?.messages || [];
        const matched =
          sessionId != null
            ? (history.find((item: { id: number }) => item.id === sessionId) ?? history[0])
            : history[history.length - 1];
        const finalReply = String(matched?.ai_response ?? '').trim();
        if (!finalReply) return;
        setMessages((prev) =>
          prev.map((m) => (m.id === localStreamingMsgId ? { ...m, content: finalReply } : m)),
        );
      } catch {
        // ignore: 对账失败不影响主链路
      }
    },
    [chatApi],
  );

  const runStreamTeardown = useCallback(
    (msgId: string | null, fullText: string) => {
      cancelTypewriter();
      pendingStreamEndRef.current = false;
      if (msgId && fullText) {
        setMessages((prev) => prev.map((m) => (m.id === msgId ? { ...m, content: fullText } : m)));
      }
      streamAccumRef.current = { msgId: null, text: '' };
      typewriterRevealLenRef.current = 0;
      setStreamingAssistantId(null);
      streamActiveRef.current = false;
      setStreamActive(false);
      streamAbortRef.current = null;
      setIsLoading(false);
      setLoadingConversationId(undefined);
      const cid = conversationIdRef.current;
      const sid = streamSessionIdRef.current;
      streamSessionIdRef.current = null;
      if (cid != null && msgId) {
        void reconcileStreamingMessageFromServer(cid, msgId, sid);
      }
    },
    [cancelTypewriter, reconcileStreamingMessageFromServer],
  );

  const scheduleTypewriterTick = useCallback(() => {
    if (typewriterRafRef.current != null) return;
    const TYPEWRITER_MAX_STEP = 8;
    const tick = () => {
      typewriterRafRef.current = null;
      const { msgId, text: full } = streamAccumRef.current;
      if (!msgId) return;

      let revealed = typewriterRevealLenRef.current;
      const target = full.length;
      const backlog = target - revealed;
      if (backlog > 0) {
        const step = backlog > 200 ? TYPEWRITER_MAX_STEP : backlog > 80 ? 4 : backlog > 25 ? 2 : 1;
        revealed = Math.min(revealed + step, target);
        typewriterRevealLenRef.current = revealed;
        const slice = full.slice(0, revealed);
        if (!writeStreamingDom(slice, true)) {
          requestAnimationFrame(() => writeStreamingDom(slice, true));
        }
      }

      if (revealed < target) {
        typewriterRafRef.current = requestAnimationFrame(tick);
      } else if (pendingStreamEndRef.current) {
        runStreamTeardown(msgId, full);
      }
    };
    typewriterRafRef.current = requestAnimationFrame(tick);
  }, [runStreamTeardown, writeStreamingDom]);

  const flushStreamContent = useCallback(() => {
    streamFlushRafRef.current = null;
    const { msgId, text: full } = streamAccumRef.current;
    if (!msgId) return;
    // 流式进行中：直接展示累计全文，避免打字机每帧 1～8 字造成「模型已出字、界面跟不上」
    if (!pendingStreamEndRef.current) {
      typewriterRevealLenRef.current = full.length;
      if (!writeStreamingDom(full, true)) {
        requestAnimationFrame(() => writeStreamingDom(full, true));
      }
      return;
    }
    scheduleTypewriterTick();
  }, [scheduleTypewriterTick, writeStreamingDom]);

  const scheduleStreamFlush = useCallback(() => {
    if (streamFlushRafRef.current != null) return;
    streamFlushRafRef.current = requestAnimationFrame(() => {
      flushStreamContent();
    });
  }, [flushStreamContent]);

  const buildStreamCallbacks = (
    startConversationId: number | undefined,
    streamConversationIdRef: { current: number | undefined },
    streamingMsgIdRef: { current: string | null },
    sawInterruptRef: { current: boolean },
  ) => {
    const isCurrentStreamConversation = () =>
      conversationIdRef.current === startConversationId ||
      (streamConversationIdRef.current != null &&
        conversationIdRef.current === streamConversationIdRef.current);

    return {
      onMeta: ({
        conversation_id,
        session_id,
      }: {
        conversation_id: number;
        session_id: number;
      }) => {
        streamConversationIdRef.current = conversation_id;
        streamSessionIdRef.current = session_id;
        if (conversationIdRef.current === startConversationId) {
          setConversationId(conversation_id);
          persistActiveConversationId(conversation_id);
          setLoadingConversationId(conversation_id);
        }
      },
      onDelta: (text: string) => {
        if (!isCurrentStreamConversation()) return;
        setLoadingStatusText(null);
        if (!streamingMsgIdRef.current) {
          const id = `ai-${Date.now()}`;
          streamingMsgIdRef.current = id;
          streamAccumRef.current = { msgId: id, text };
          typewriterRevealLenRef.current = 0;
          setStreamingAssistantId(id);
          setIsLoading(false);
          setMessages((prev) => [
            ...prev,
            {
              id,
              content: '',
              isUser: false,
              timestamp: new Date().toLocaleTimeString(),
              webSources: pendingWebSourcesRef.current.length
                ? [...pendingWebSourcesRef.current]
                : undefined,
            },
          ]);
          scheduleStreamFlush();
          return;
        }
        streamAccumRef.current.text = mergeStreamingDelta(streamAccumRef.current.text, text);
        scheduleStreamFlush();
      },
      onError: (errText: string) => {
        if (!isCurrentStreamConversation()) return;
        const line = `\n\n[错误] ${errText}`;
        if (!streamingMsgIdRef.current) {
          const id = `ai-${Date.now()}`;
          streamingMsgIdRef.current = id;
          streamAccumRef.current = { msgId: id, text: line.trim() };
          setStreamingAssistantId(id);
          setIsLoading(false);
          setMessages((prev) => [
            ...prev,
            {
              id,
              content: line.trim(),
              isUser: false,
              timestamp: new Date().toLocaleTimeString(),
              webSources: pendingWebSourcesRef.current.length
                ? [...pendingWebSourcesRef.current]
                : undefined,
            },
          ]);
        } else {
          streamAccumRef.current.text = mergeStreamingDelta(streamAccumRef.current.text, line);
          scheduleStreamFlush();
        }
      },
      onStreamDone: () => {
        if (!isCurrentStreamConversation()) return;
        if (streamFlushRafRef.current != null) {
          cancelAnimationFrame(streamFlushRafRef.current);
          streamFlushRafRef.current = null;
        }
        pendingStreamEndRef.current = true;
        scheduleTypewriterTick();
      },
      onDone: () => {
        if (isCurrentStreamConversation()) {
          void loadConversations();
        }
      },
      onStatus: (text: string) => {
        if (!isCurrentStreamConversation()) return;
        setLoadingStatusText(text);
      },
      onWebSources: (sources: WebSource[]) => {
        if (!isCurrentStreamConversation()) return;
        const cleaned = sanitizeWebSources(sources);
        pendingWebSourcesRef.current = cleaned;
        setWebSources(cleaned);
        setLoadingStatusText(null);
        const mid = streamingMsgIdRef.current;
        if (mid && cleaned.length) {
          setMessages((prev) =>
            prev.map((m) => (m.id === mid ? { ...m, webSources: cleaned } : m)),
          );
        }
      },
      onInterrupt: (p: { kind: string; message: string }) => {
        sawInterruptRef.current = true;
        const existingId = streamingMsgIdRef.current;
        if (existingId) {
          setPdfExportHostMessageId(existingId);
        } else {
          const newId = `ai-${Date.now()}`;
          streamingMsgIdRef.current = newId;
          streamAccumRef.current = { msgId: newId, text: '' };
          typewriterRevealLenRef.current = 0;
          setStreamingAssistantId(newId);
          setIsLoading(false);
          setMessages((prev) => [
            ...prev,
            {
              id: newId,
              content: '',
              isUser: false,
              timestamp: new Date().toLocaleTimeString(),
              webSources: pendingWebSourcesRef.current.length
                ? [...pendingWebSourcesRef.current]
                : undefined,
            },
          ]);
          setPdfExportHostMessageId(newId);
        }
        setPdfExportPrompt({ kind: p.kind, message: p.message });
      },
      onPdfReady: ({ url, filename }: { url: string; filename: string }) => {
        void (async () => {
          try {
            const token = localStorage.getItem('token');
            const res = await fetch(url, {
              headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            if (handleUnauthorizedStatus(res.status)) return;
            if (!res.ok) {
              throw new Error(String(res.status));
            }
            const blob = await res.blob();
            const a = document.createElement('a');
            const href = URL.createObjectURL(blob);
            a.href = href;
            a.download = filename || 'export.pdf';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(href);
            message.success('PDF 已开始下载');
          } catch {
            message.error('PDF 下载失败，请稍后重试或检查网络');
          }
        })();
      },
    };
  };

  const runStreamCommonFinally = () => {
    if (streamFlushRafRef.current != null) {
      cancelAnimationFrame(streamFlushRafRef.current);
      streamFlushRafRef.current = null;
    }
    streamAbortRef.current = null;
    setIsLoading(false);
    setLoadingStatusText(null);
    setLoadingConversationId(undefined);

    if (pendingStreamEndRef.current) {
      scheduleTypewriterTick();
    } else {
      cancelTypewriter();
      const { msgId, text } = streamAccumRef.current;
      if (msgId && text) {
        setMessages((prev) => prev.map((m) => (m.id === msgId ? { ...m, content: text } : m)));
      }
      streamAccumRef.current = { msgId: null, text: '' };
      typewriterRevealLenRef.current = 0;
      streamSessionIdRef.current = null;
      setStreamingAssistantId(null);
      streamActiveRef.current = false;
      setStreamActive(false);
    }
  };

  const handleSendMessage = async () => {
    if (streamActiveRef.current) return;
    if (pdfExportPrompt) {
      message.info('请先点击下方按钮确认或取消 PDF 导出');
      return;
    }

    const attachmentsForSend = pendingAttachments;
    const messageText =
      inputMessage.trim() || (attachmentsForSend.length ? '请理解这些附件。' : '');
    if (!messageText) return;

    if (
      estimateChatStreamPayloadBytes(messageText, conversationId, attachmentsForSend, {
        enableWebSearch,
      }) > MAX_CHAT_STREAM_PAYLOAD_BYTES
    ) {
      message.warning(PAYLOAD_TOO_LARGE_MESSAGE);
      return;
    }

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
      attachments: attachmentsForSend,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage('');
    clearAttachments();
    setIsLoading(true);
    setLoadingConversationId(startConversationId);
    setWebSources([]);
    pendingWebSourcesRef.current = [];
    setLoadingStatusText(enableWebSearch ? '正在联网搜索...' : null);

    const streamConversationIdRef = { current: startConversationId as number | undefined };
    const streamingMsgIdRef = { current: null as string | null };
    const sawInterruptRef = { current: false };
    const cb = buildStreamCallbacks(
      startConversationId,
      streamConversationIdRef,
      streamingMsgIdRef,
      sawInterruptRef,
    );

    try {
      await chatApi.chatWithStream(messageText, conversationId, cb, {
        signal: abortController.signal,
        enableWebSearch,
        attachments: attachmentsForSend,
      });

      if (conversationIdRef.current !== startConversationId) {
        await loadConversations();
        return;
      }

      if (!streamingMsgIdRef.current && !sawInterruptRef.current) {
        setMessages((prev) => [
          ...prev,
          {
            id: `ai-${Date.now()}`,
            content: '（模型未返回内容）',
            isUser: false,
            timestamp: new Date().toLocaleTimeString(),
            webSources: pendingWebSourcesRef.current.length
              ? [...pendingWebSourcesRef.current]
              : undefined,
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
          if (!streamingMsgIdRef.current && !sawInterruptRef.current) {
            setMessages((prev) => [
              ...prev,
              {
                id: `ai-${Date.now()}`,
                content: tail,
                isUser: false,
                timestamp: new Date().toLocaleTimeString(),
              },
            ]);
          } else if (streamingMsgIdRef.current) {
            const mid = streamingMsgIdRef.current;
            cancelTypewriter();
            pendingStreamEndRef.current = false;
            const acc = streamAccumRef.current.text;
            const combined = acc ? `${acc}\n\n${tail}` : tail;
            streamAccumRef.current = { msgId: null, text: '' };
            typewriterRevealLenRef.current = 0;
            setMessages((prev) =>
              prev.map((m) => (m.id === mid ? { ...m, content: combined } : m)),
            );
            setStreamingAssistantId(null);
            streamActiveRef.current = false;
            setStreamActive(false);
          }
        }
        return;
      }

      const errorMessage = err?.message || '调用失败，请稍后重试';
      if (errorMessage.includes('认证失败') || errorMessage.includes('未登录')) {
        handleForceLogout('登录已失效，请重新登录');
        return;
      }
      if (errorMessage === PAYLOAD_TOO_LARGE_MESSAGE || errorMessage.includes('过大')) {
        message.warning(errorMessage);
      }

      if (conversationIdRef.current !== startConversationId) {
        await loadConversations();
        return;
      }

      if (!streamingMsgIdRef.current && !sawInterruptRef.current) {
        setMessages((prev) => [
          ...prev,
          {
            id: `ai-${Date.now()}`,
            content: errorMessage,
            isUser: false,
            timestamp: new Date().toLocaleTimeString(),
          },
        ]);
      } else if (streamingMsgIdRef.current) {
        const mid = streamingMsgIdRef.current;
        cancelTypewriter();
        pendingStreamEndRef.current = false;
        const acc = streamAccumRef.current.text;
        const combined = acc || errorMessage;
        streamAccumRef.current = { msgId: null, text: '' };
        typewriterRevealLenRef.current = 0;
        setMessages((prev) => prev.map((m) => (m.id === mid ? { ...m, content: combined } : m)));
        setStreamingAssistantId(null);
        streamActiveRef.current = false;
        setStreamActive(false);
      }
    } finally {
      runStreamCommonFinally();
    }
  };

  const handlePdfResume = async (approved: boolean) => {
    const cid = conversationIdRef.current;
    if (cid == null || streamActiveRef.current) return;

    setPdfExportPrompt(null);
    setPdfExportHostMessageId(null);

    const startConversationId = cid;

    userAbortRef.current = false;
    const abortController = new AbortController();
    streamAbortRef.current = abortController;
    streamActiveRef.current = true;
    setStreamActive(true);

    setIsLoading(true);
    setLoadingConversationId(startConversationId);

    const streamConversationIdRef = { current: startConversationId as number | undefined };
    const streamingMsgIdRef = { current: null as string | null };
    const sawInterruptRef = { current: false };
    const cb = buildStreamCallbacks(
      startConversationId,
      streamConversationIdRef,
      streamingMsgIdRef,
      sawInterruptRef,
    );

    try {
      await chatApi.chatWithStream('', cid, cb, {
        signal: abortController.signal,
        resumePdfExport: approved,
        enableWebSearch,
      });

      if (conversationIdRef.current !== startConversationId) {
        await loadConversations();
        return;
      }

      if (!streamingMsgIdRef.current && !sawInterruptRef.current) {
        setMessages((prev) => [
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
          if (!streamingMsgIdRef.current && !sawInterruptRef.current) {
            setMessages((prev) => [
              ...prev,
              {
                id: `ai-${Date.now()}`,
                content: tail,
                isUser: false,
                timestamp: new Date().toLocaleTimeString(),
              },
            ]);
          } else if (streamingMsgIdRef.current) {
            const mid = streamingMsgIdRef.current;
            cancelTypewriter();
            pendingStreamEndRef.current = false;
            const acc = streamAccumRef.current.text;
            const combined = acc ? `${acc}\n\n${tail}` : tail;
            streamAccumRef.current = { msgId: null, text: '' };
            typewriterRevealLenRef.current = 0;
            setMessages((prev) =>
              prev.map((m) => (m.id === mid ? { ...m, content: combined } : m)),
            );
            setStreamingAssistantId(null);
            streamActiveRef.current = false;
            setStreamActive(false);
          }
        }
        return;
      }

      const errorMessage = err?.message || '调用失败，请稍后重试';
      if (errorMessage.includes('认证失败') || errorMessage.includes('未登录')) {
        handleForceLogout('登录已失效，请重新登录');
        return;
      }
      if (errorMessage === PAYLOAD_TOO_LARGE_MESSAGE || errorMessage.includes('过大')) {
        message.warning(errorMessage);
      }

      if (conversationIdRef.current !== startConversationId) {
        await loadConversations();
        return;
      }

      if (!streamingMsgIdRef.current && !sawInterruptRef.current) {
        setMessages((prev) => [
          ...prev,
          {
            id: `ai-${Date.now()}`,
            content: errorMessage,
            isUser: false,
            timestamp: new Date().toLocaleTimeString(),
          },
        ]);
      } else if (streamingMsgIdRef.current) {
        const mid = streamingMsgIdRef.current;
        cancelTypewriter();
        pendingStreamEndRef.current = false;
        const acc = streamAccumRef.current.text;
        const combined = acc || errorMessage;
        streamAccumRef.current = { msgId: null, text: '' };
        typewriterRevealLenRef.current = 0;
        setMessages((prev) => prev.map((m) => (m.id === mid ? { ...m, content: combined } : m)));
        setStreamingAssistantId(null);
        streamActiveRef.current = false;
        setStreamActive(false);
      }
    } finally {
      runStreamCommonFinally();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (streamActiveRef.current) return;
      if (pdfExportPrompt) return;
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
        attachments={pendingAttachments}
        isLoading={showLoading}
        messagesEndRef={messagesEndRef}
        messagesContainerRef={messagesContainerRef}
        onInputChange={(e) => setInputMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        onSendMessage={handleSendMessage}
        onAttachFiles={(files) => void handleAttachFiles(files)}
        onRemoveAttachment={handleRemoveAttachment}
        enableWebSearch={enableWebSearch}
        onToggleWebSearch={() => setEnableWebSearch((v) => !v)}
        streamActive={streamActive}
        onStopStream={handleStopStream}
        onSelectConversation={handleSelectConversation}
        onCreateConversation={handleCreateConversation}
        onRenameConversation={handleRenameConversation}
        onDeleteConversation={handleDeleteConversation}
        onPinConversation={handlePinConversation}
        streamingAssistantId={streamingAssistantId}
        streamingContentRef={streamingContentRef}
        getStreamingFormatted={getStreamingFormatted}
        pdfExportPrompt={pdfExportPrompt}
        pdfExportHostMessageId={pdfExportHostMessageId}
        onPdfExportConfirm={() => void handlePdfResume(true)}
        onPdfExportCancel={() => void handlePdfResume(false)}
        inputLocked={streamActive || !!pdfExportPrompt}
        loadingStatusText={loadingStatusText}
        webSources={webSources}
      />
    </div>
  );
};

export default ChatPage;
