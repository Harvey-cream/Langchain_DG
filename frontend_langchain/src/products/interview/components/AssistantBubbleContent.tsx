import React from 'react';
import { CopyOutlined } from '@ant-design/icons';
import { message } from 'antd';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import type { Components } from 'react-markdown';

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
  if (!ok) throw new Error('execCommand copy failed');
}

async function copyToClipboard(text: string): Promise<void> {
  if (typeof navigator !== 'undefined' && window.isSecureContext && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Fall back for HTTP and denied clipboard permissions.
    }
  }
  copyToClipboardFallback(text);
}

const MARKDOWN_COMPONENTS: Components = {
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
          <CopyOutlined />
          复制
        </button>
        <pre className="chat-pre">{children}</pre>
      </div>
    );
  },
};

const MARKDOWN_PLUGINS = [remarkGfm, remarkBreaks];

type AssistantBubbleContentProps = {
  rawContent: string;
  isStreaming: boolean;
};

export const AssistantBubbleContent = React.memo(function AssistantBubbleContent({
  rawContent,
  isStreaming,
}: AssistantBubbleContentProps) {
  if (isStreaming && !rawContent.trim()) {
    return <span className="chat-assistant-pending">正在生成回复…</span>;
  }
  if (!rawContent.trim()) {
    return <span className="chat-assistant-fallback">（无有效回复）</span>;
  }

  return (
    <div className="chat-markdown">
      <ReactMarkdown remarkPlugins={MARKDOWN_PLUGINS} components={MARKDOWN_COMPONENTS}>
        {rawContent}
      </ReactMarkdown>
    </div>
  );
});
