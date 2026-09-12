import React from 'react';
import { CloseOutlined, PaperClipOutlined } from '@ant-design/icons';
import type { ChatAttachment } from '../../../services/chatStream';

export type ChatInputProps = {
  inputMessage: string;
  attachments: ChatAttachment[];
  inputLocked: boolean;
  enableWebSearch: boolean;
  streamActive: boolean;
  onInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  onSendMessage: () => void;
  onAttachFiles: (files: FileList | null) => void;
  onRemoveAttachment: (id: string) => void;
  onToggleWebSearch: () => void;
  onStopStream: () => void;
};

export function attachmentLabel(item: ChatAttachment): string {
  const kindLabel = item.kind === 'image' ? '图片' : item.kind === 'pdf' ? 'PDF' : '文件';
  return `${kindLabel}：${item.name}`;
}

export const ChatInput = React.memo(function ChatInput({
  inputMessage,
  attachments,
  inputLocked,
  enableWebSearch,
  streamActive,
  onInputChange,
  onKeyDown,
  onSendMessage,
  onAttachFiles,
  onRemoveAttachment,
  onToggleWebSearch,
  onStopStream,
}: ChatInputProps) {
  return (
    <div className="chat-input-area">
      {attachments.length ? (
        <div className="chat-attachment-list">
          {attachments.map(item => (
            <span key={item.id} className="chat-attachment-chip">
              {attachmentLabel(item)}
              <button
                type="button"
                className="chat-attachment-remove"
                aria-label={`移除 ${item.name}`}
                onClick={() => onRemoveAttachment(item.id)}
                disabled={inputLocked}
              >
                <CloseOutlined />
              </button>
            </span>
          ))}
        </div>
      ) : null}
      <div className="chat-input-row">
        <label className={`chat-attach-button ${inputLocked ? 'disabled' : ''}`} title="上传图片、PDF 或文本文件">
          <PaperClipOutlined />
          <input
            type="file"
            multiple
            accept="image/*,.pdf,.txt,.md,.markdown,.json,.csv,.tsv,.js,.jsx,.ts,.tsx,.py,.java,.go,.rs,.c,.cpp,.h,.hpp,.css,.html,.xml,.yaml,.yml,.log"
            disabled={inputLocked}
            onChange={e => {
              onAttachFiles(e.target.files);
              e.currentTarget.value = '';
            }}
          />
        </label>
        <button
          type="button"
          className={`web-search-toggle ${enableWebSearch ? 'active' : ''}`}
          onClick={onToggleWebSearch}
          disabled={inputLocked}
        >
          联网搜索
        </button>
        <input
          type="text"
          value={inputMessage}
          onChange={onInputChange}
          onKeyDown={onKeyDown}
          placeholder="请输入消息..."
          className="chat-input"
          disabled={inputLocked}
        />
        {streamActive ? (
          <button type="button" onClick={onStopStream} className="send-button send-button-stop">
            中止
          </button>
        ) : (
          <button
            type="button"
            onClick={onSendMessage}
            className="send-button"
            disabled={inputLocked || (!inputMessage.trim() && attachments.length === 0)}
          >
            发送
          </button>
        )}
      </div>
    </div>
  );
});
