import { useState, useCallback, useEffect } from 'react';
import { message } from 'antd';
import { type ChatAttachment, MAX_ATTACHMENT_COUNT, MAX_ATTACHMENT_MB, MAX_ATTACHMENT_BYTES, MAX_TEXT_ATTACHMENT_CHARS } from '../../../services/chatStream';

async function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error('read failed'));
    reader.readAsDataURL(file);
  });
}

function isTextFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return (
    file.type.startsWith('text/') ||
    /\.(txt|md|markdown|json|csv|tsv|js|jsx|ts|tsx|py|java|go|rs|c|cpp|h|hpp|css|html|xml|yaml|yml|log)$/i.test(name)
  );
}

function isPdfFile(file: File): boolean {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
}

async function fileToAttachment(file: File): Promise<ChatAttachment | null> {
  if (file.size > MAX_ATTACHMENT_BYTES) {
    message.warning(`${file.name} 超过 ${MAX_ATTACHMENT_MB}MB，已跳过`);
    return null;
  }
  const base = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    name: file.name,
    mime_type: file.type || 'application/octet-stream',
    size: file.size,
  };
  if (file.type.startsWith('image/')) {
    return { ...base, kind: 'image', data_url: await readAsDataUrl(file) };
  }
  if (isPdfFile(file)) {
    return { ...base, kind: 'pdf', data_url: await readAsDataUrl(file) };
  }
  if (isTextFile(file)) {
    const text = await file.text();
    return { ...base, kind: 'text', text: text.slice(0, MAX_TEXT_ATTACHMENT_CHARS) };
  }
  message.warning(`${file.name} 暂不支持，请上传图片、PDF 或文本/代码文件`);
  return null;
}

export function useChatAttachments(storageKey: string) {
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);

  const clearAttachments = useCallback(() => setAttachments([]), []);

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(storageKey);
      if (saved) setAttachments(JSON.parse(saved));
    } catch { /* ignore */ }
  }, [storageKey]);

  useEffect(() => {
    try {
      if (attachments.length) sessionStorage.setItem(storageKey, JSON.stringify(attachments));
      else sessionStorage.removeItem(storageKey);
    } catch { /* ignore */ }
  }, [attachments, storageKey]);

  const addFiles = useCallback(async (files: FileList | null) => {
    if (!files?.length) return;
    const remaining = MAX_ATTACHMENT_COUNT - attachments.length;
    if (remaining <= 0) {
      message.warning(`最多同时上传 ${MAX_ATTACHMENT_COUNT} 个附件`);
      return;
    }
    const selected = Array.from(files).slice(0, remaining);
    const next = (await Promise.all(selected.map(fileToAttachment))).filter((item): item is ChatAttachment => item !== null);
    if (next.length) {
      setAttachments(prev => [...prev, ...next].slice(0, MAX_ATTACHMENT_COUNT));
    }
    if (files.length > remaining) {
      message.warning(`最多同时上传 ${MAX_ATTACHMENT_COUNT} 个附件，多余文件已跳过`);
    }
  }, [attachments.length]);

  const removeAttachment = useCallback((id: string) => {
    setAttachments(prev => prev.filter(item => item.id !== id));
  }, []);

  return { attachments, addFiles, removeAttachment, clearAttachments };
}
