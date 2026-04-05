/**
 * 流式对话：展示清洗 + SSE 拉流（与 api.ts 里基于 axios 的 sendRequest 分离）。
 * 流式必须用浏览器原生 fetch + ReadableStream，才能读 body 流；sendRequest 不适合 SSE。
 */

// --- 展示：ReAct 只给用户看 Final Answer 之后 ---
export function formatAssistantDisplayText(raw: string): string {
  const s = (raw || '').trim();
  if (!s) return '';

  const afterNewlineFinal = s.match(/\nFinal Answer:\s*/i);
  if (afterNewlineFinal && afterNewlineFinal.index !== undefined) {
    return normalizeChatWhitespace(s.slice(afterNewlineFinal.index + afterNewlineFinal[0].length));
  }

  const startFinal = s.match(/^Final Answer:\s*/im);
  if (startFinal && startFinal.index === 0) {
    return normalizeChatWhitespace(s.slice(startFinal[0].length));
  }

  if (/^Thought:/im.test(s)) {
    return '';
  }

  return normalizeChatWhitespace(s);
}

export function normalizeChatWhitespace(text: string): string {
  return text.replace(/\n{3,}/g, '\n\n').trim();
}

// --- SSE：idle 内无字节则中止（默认 3 分钟），不设固定总超时 ---
const DEFAULT_IDLE_MS = 180000;
const STREAM_URL = '/api/agent/chat/stream/';

export type StreamMeta = { conversation_id: number; session_id: number };

export type ChatStreamCallbacks = {
  onMeta?: (data: StreamMeta) => void;
  onDelta?: (text: string) => void;
  onPing?: () => void;
  onDone?: () => void;
  onError?: (message: string) => void;
};

export async function chatWithAgentStream(
  message: string,
  conversationId: number | undefined,
  callbacks: ChatStreamCallbacks,
  options?: { idleMs?: number; signal?: AbortSignal }
): Promise<void> {
  const token = localStorage.getItem('token');
  if (!token) {
    throw new Error('未登录');
  }

  const idleMs = options?.idleMs ?? DEFAULT_IDLE_MS;
  const fetchAbort = new AbortController();

  if (options?.signal) {
    if (options.signal.aborted) {
      fetchAbort.abort();
    } else {
      options.signal.addEventListener('abort', () => fetchAbort.abort(), { once: true });
    }
  }

  let idleTimer: ReturnType<typeof setTimeout> | undefined;
  const scheduleIdle = () => {
    if (idleTimer !== undefined) clearTimeout(idleTimer);
    idleTimer = setTimeout(() => fetchAbort.abort(), idleMs);
  };
  scheduleIdle();

  const res = await fetch(STREAM_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message, conversation_id: conversationId }),
    signal: fetchAbort.signal,
  });

  if (!res.ok) {
    if (idleTimer !== undefined) clearTimeout(idleTimer);
    let msg = `请求失败 ${res.status}`;
    try {
      const j = (await res.json()) as { msg?: string };
      if (j?.msg) msg = j.msg;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }

  const reader = res.body?.getReader();
  if (!reader) {
    if (idleTimer !== undefined) clearTimeout(idleTimer);
    throw new Error('无法读取响应流');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value?.byteLength) {
        scheduleIdle();
      }
      buffer += decoder.decode(value, { stream: true });
// // 数据切割流程：
// 1. 后端推数据
//    → 二进制数据块 value (Uint8Array)

// 2. 前端转文字
//    → buffer += decoder.decode(value, { stream: true })
//    → 缓冲区 buffer (字符串)

// 3. 切出一条完整消息
//    → const rawEvent = buffer.slice(0, idx)
//    → rawEvent (字符串，例如："data: {\"type\":\"delta\",\"text\":\"你好\"}")

// 4. 找到 data: 开头的行
//    → const line = rawEvent.split('\n').find(l => l.startsWith('data: '))
//    → line (字符串，例如："data: {\"type\":\"delta\",\"text\":\"你好\"}")

// 5. 提取 JSON 字符串
//    → const jsonStr = line.slice(6).trim()
//    → jsonStr (字符串，例如："{\"type\":\"delta\",\"text\":\"你好\"}")
//    【看这里！slice(6) 去掉了前面的 "data: "】

// 6. 【你问的】解析 JSON
//    → data = JSON.parse(jsonStr)
//    → data (对象，例如：{ type: "delta", text: "你好" })
// // 
      let idx: number;
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const rawEvent = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const line = rawEvent.split('\n').find(l => l.startsWith('data: '));
        if (!line) continue;
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;
        let data: { type?: string; text?: string; message?: string; conversation_id?: number; session_id?: number };
        try {
          data = JSON.parse(jsonStr) as typeof data;
        } catch {
          continue;
        }
        const t = data.type;
        if (t === 'meta' && data.conversation_id != null && data.session_id != null) {
          callbacks.onMeta?.({ conversation_id: data.conversation_id, session_id: data.session_id });
        } else if (t === 'ping') {
          callbacks.onPing?.();
        } else if (t === 'delta' && data.text != null) {
          callbacks.onDelta?.(data.text);
        } else if (t === 'error' && data.message != null) {
          callbacks.onError?.(data.message);
        } else if (t === 'done') {
          callbacks.onDone?.();
        }
      }
    }
  } finally {
    if (idleTimer !== undefined) clearTimeout(idleTimer);
    reader.releaseLock?.();
  }
}
