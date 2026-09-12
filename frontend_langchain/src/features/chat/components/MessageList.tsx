import React, { useState } from 'react';
import { CopyOutlined, DownOutlined } from '@ant-design/icons';
import { message } from 'antd';
import type { WebSource } from '../../../services/chatStream';
import { formatAssistantDisplayText } from '../../../services/chatStream';
import { AssistantBubbleContent } from './AssistantBubbleContent';
import { attachmentLabel } from './ChatInput';

export type MessageListItem = {
  id: string;
  content: string;
  isUser: boolean;
  attachments?: { id: string; kind: string; name: string }[];
  webSources?: WebSource[];
};

type MessageListProps = {
  messages: MessageListItem[];
  isLoading: boolean;
  messagesEndRef: React.RefObject<HTMLDivElement>;
  messagesContainerRef: React.RefObject<HTMLDivElement>;
  streamActive: boolean;
  streamingAssistantId: string | null;
  streamingContentRef: React.MutableRefObject<HTMLDivElement | null>;
  getStreamingFormatted?: () => string;
  pdfExportPrompt: { kind: string; message: string } | null;
  pdfExportHostMessageId: string | null;
  onPdfExportConfirm: () => void;
  onPdfExportCancel: () => void;
  loadingStatusText?: string | null;
  webSources?: WebSource[];
};

const junkUrlExt = /\.(png|jpe?g|gif|webp|svg|ico|css|js|woff2?)(\?|#|$)/i;
const junkHost = /(alicdn\.com|cdn\.|static\.|\.img\.|img\.|\.cloudfront\.|googleapis\.com\/.*\/image)/i;

function WebSourcesCollapse({ sources }: { sources: WebSource[] }) {
  const [open, setOpen] = useState(false);
  const list = sources.filter((source, index, all) => {
    const url = (source.url || '').trim();
    return url && all.findIndex(item => item.url === source.url) === index && !junkUrlExt.test(url) && !junkHost.test(url);
  });
  if (!list.length) return null;
  return (
    <div className={`chat-web-sources-collapse ${open ? 'is-open' : ''}`}>
      <button type="button" className="chat-web-sources-summary" aria-expanded={open} onClick={() => setOpen(value => !value)}>
        <span>参考 {list.length} 篇资料</span>
        <DownOutlined className="chat-web-sources-chevron" />
      </button>
      {open ? (
        <ol className="chat-web-sources-list">
          {list.map((source, index) => {
            let label = (source.title || '').trim();
            if (!label || label === source.url || /^https?:\/\//i.test(label)) {
              try { label = new URL(source.url).hostname.replace(/^www\./, ''); } catch { label = source.url; }
            }
            return <li key={`${source.url}-${index}`}><a href={source.url} target="_blank" rel="noopener noreferrer" title={source.url}>{label.length > 72 ? `${label.slice(0, 72)}…` : label}</a></li>;
          })}
        </ol>
      ) : null}
    </div>
  );
}

async function copyText(text: string): Promise<void> {
  if (window.isSecureContext && navigator.clipboard?.writeText) {
    try { await navigator.clipboard.writeText(text); return; } catch { /* fall through */ }
  }
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0;pointer-events:none;';
  document.body.appendChild(textarea);
  textarea.select();
  try {
    if (!document.execCommand('copy')) throw new Error('copy failed');
  } finally {
    document.body.removeChild(textarea);
  }
}

export const MessageList = React.memo(function MessageList({
  messages,
  isLoading,
  messagesEndRef,
  messagesContainerRef,
  streamActive,
  streamingAssistantId,
  streamingContentRef,
  getStreamingFormatted,
  pdfExportPrompt,
  pdfExportHostMessageId,
  onPdfExportConfirm,
  onPdfExportCancel,
  loadingStatusText,
  webSources,
}: MessageListProps) {
  return (
    <div className="chat-messages" ref={messagesContainerRef}>
      {messages.filter(item => item.isUser || item.content.trim() || (streamActive && streamingAssistantId === item.id) || (!!pdfExportPrompt && pdfExportHostMessageId === item.id)).map(item => {
        const streamThis = !item.isUser && streamActive && streamingAssistantId === item.id;
        const pdfInThisBubble = !item.isUser && !!pdfExportPrompt && pdfExportHostMessageId === item.id;
        const display = item.isUser ? '' : streamThis && getStreamingFormatted ? getStreamingFormatted() : formatAssistantDisplayText(item.content);
        return (
          <div key={item.id} className={`message ${item.isUser ? 'user-message' : 'ai-message'}`}>
            <div className="message-bubble-row">
              <div className={`message-content ${item.isUser ? '' : 'message-content-md'}`}>
                {item.isUser ? <>{item.content}{item.attachments?.length ? <div className="chat-attachment-list chat-attachment-list-message">{item.attachments.map(attachment => <span key={attachment.id} className="chat-attachment-chip">{attachmentLabel(attachment as never)}</span>)}</div> : null}</> : <>
                  {(item.webSources?.length || (streamThis && webSources?.length)) ? <WebSourcesCollapse sources={item.webSources?.length ? item.webSources : webSources || []} /> : null}
                  {streamThis ? <div ref={element => { streamingContentRef.current = element; }} className="chat-markdown chat-stream-direct" /> : <AssistantBubbleContent rawContent={item.content} isStreaming={false} />}
                  {pdfInThisBubble ? <div className="pdf-export-embedded"><p className="pdf-export-inline-text">{pdfExportPrompt.message}</p><div className="pdf-export-inline-actions"><button type="button" className="pdf-export-confirm" onClick={onPdfExportConfirm}>确认</button><button type="button" className="pdf-export-cancel" onClick={onPdfExportCancel}>取消</button></div></div> : null}
                </>}
              </div>
              {!item.isUser ? <button type="button" className="message-copy-fab" title="复制可见正文" aria-label="复制可见正文" onClick={() => { if (!display.trim()) { message.warning('暂无可复制的正文'); return; } void copyText(display).then(() => message.success('已复制'), () => message.error('复制失败')); }}><CopyOutlined /></button> : null}
            </div>
            {streamThis ? <div className="chat-stream-progress" aria-live="polite"><span className="chat-stream-progress-text">生成中</span><div className="loading-indicator"><span className="loading-dot" /><span className="loading-dot" /><span className="loading-dot" /></div></div> : null}
          </div>
        );
      })}
      {isLoading ? <div className="message ai-message"><div className="message-content">{webSources?.length ? <WebSourcesCollapse sources={webSources} /> : null}{loadingStatusText ? <span className="chat-stream-progress-text">{loadingStatusText}</span> : null}<div className="loading-indicator"><span className="loading-dot" /><span className="loading-dot" /><span className="loading-dot" /></div></div></div> : null}
      <div ref={messagesEndRef} />
    </div>
  );
});
