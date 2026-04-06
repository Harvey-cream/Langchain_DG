/**
 * 流式对话：展示清洗 + SSE 拉流（与 api.ts 里基于 axios 的 sendRequest 分离）。
 * 流式必须用浏览器原生 fetch + ReadableStream，才能读 body 流；sendRequest 不适合 SSE。
 *
 * 调试：在控制台执行 localStorage.setItem('DEBUG_STREAM','1') 后刷新，
 * 每次 delta 会在控制台打印 [chatStream] / [Chat] 与时间戳，用于确认是否「边收边回调」。
 */

// --- 展示：ReAct 只给用户看 Final Answer 之后（与后端 SSE 分割规则一致：支持全角冒号、可选 **）---
const FINAL_ANSWER_SPLIT = /(?:^|\n)\s*\*{0,2}Final Answer\*{0,2}\s*(?::|：)\s*/i;
const FINAL_ANSWER_START = /^\s*\*{0,2}Final Answer\*{0,2}\s*(?::|：)\s*/i;
/** Final Answer 正文后模型又续写一轮 Question/Thought/… 时截断（与后端 SSE 一致，含 **。Thought: 同行续写） */
const REACT_RESTART_AFTER_FINAL =
  /\n\s*(?:\*\*)?(?:Question|Thought|Action|Action Input|Observation)\s*(?::|：)\s*|\*\*\s*[。！？]\s*\*{0,2}Thought\s*(?::|：)\s*|(?<=[。！？])\s*Thought\s*(?::|：)\s*/i;

/** 正文里误重复写的第二处「Final Answer:」（与后端 SSE 一致） */
const INLINE_DUP_FINAL_ANSWER =
  /(?:\n[\t ]*){1,2}\*{0,2}Final Answer\*{0,2}\s*(?::|：)?\s*|(?<=[。！？,，、.])\s*\*{0,2}Final Answer\*{0,2}\s*(?::|：)?\s*/gi;

function stripDuplicateFinalAnswerLabels(body: string): string {
  return body.replace(INLINE_DUP_FINAL_ANSWER, '');
}

function stripRepeatedReactAfterFinal(body: string): string {
  const m = REACT_RESTART_AFTER_FINAL.exec(body);
  if (m && m.index !== undefined) return body.slice(0, m.index).trimEnd();
  // 模型偶发在同一行末尾续写 Thought:（无前导换行）
  const tail = body.replace(/(?:\s+|^)(?:\*\*)?Thought\s*(?::|：)[^\n]*$/i, '').trimEnd();
  return tail;
}

export function formatAssistantDisplayText(raw: string): string {
  const s = (raw || '').trim();
  if (!s) return '';

  const afterMarker = s.match(FINAL_ANSWER_SPLIT);
  if (afterMarker && afterMarker.index !== undefined) {
    let body = s.slice(afterMarker.index + afterMarker[0].length);
    body = stripDuplicateFinalAnswerLabels(stripRepeatedReactAfterFinal(body));
    return normalizeChatWhitespace(body);
  }

  const startFinal = s.match(FINAL_ANSWER_START);
  if (startFinal && startFinal.index === 0) {
    let body = s.slice(startFinal[0].length);
    body = stripDuplicateFinalAnswerLabels(stripRepeatedReactAfterFinal(body));
    return normalizeChatWhitespace(body);
  }

  // 仍含 ReAct 痕迹则宁可空白，也不要把 Thought/Action/Observation 整段展示
  if (/(?:^|\n)\s*(?:Question|Thought|Action|Action Input|Observation)\s*[:：]/im.test(s)) {
    return '';
  }

  return normalizeChatWhitespace(s);
}

export function normalizeChatWhitespace(text: string): string {
  return text.replace(/\n{3,}/g, '\n\n').trim();
}

// --- SSE：idle 内无字节则中止（默认 3 分钟），不设固定总超时 ---
const DEFAULT_IDLE_MS = 180000;
const AGENT_STREAM_URL = '/api/agent/chat/stream/';
/** 面试大师独立库 */
export const INTERVIEW_STREAM_URL = '/api/interview/chat/stream/';

export type StreamMeta = { conversation_id: number; session_id: number };

export type ChatStreamCallbacks = {
  onMeta?: (data: StreamMeta) => void;
  onDelta?: (text: string) => void;
  onPing?: () => void;
  onDone?: () => void;
  onError?: (message: string) => void;
};

async function chatWithStreamAt(
  streamUrl: string,
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

  const res = await fetch(streamUrl, {
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
  /** 已处理过 type=done 则立即结束拉流，避免再 await reader.read() 在部分环境下阻塞（流不结束 → 无法切 Markdown） */
  let finished = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        if (!finished) {
          finished = true;
          callbacks.onDone?.();
        }
        break;
      }
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
          const chunk = data.text;
          if (typeof localStorage !== 'undefined' && localStorage.getItem('DEBUG_STREAM') === '1') {
            console.log(
              '[chatStream] delta',
              typeof performance !== 'undefined' ? performance.now().toFixed(1) : 0,
              'len=',
              chunk.length,
              JSON.stringify(chunk.slice(0, 48))
            );
          }
          // 必须同步调用：若用 queueMicrotask，同一缓冲区内「最后一个 delta」会晚于「done」执行，
          // ChatPage 已在 done 后 flush/清流式状态，会出现快结束时内容被清空再补上的错觉。
          callbacks.onDelta?.(chunk);
        } else if (t === 'error' && data.message != null) {
          callbacks.onError?.(data.message);
        } else if (t === 'done') {
          if (!finished) {
            finished = true;
            callbacks.onDone?.();
          }
          try {
            await reader.cancel();
          } catch {
            /* ignore */
          }
          return;
        }
      }
    }
  } finally {
    if (idleTimer !== undefined) clearTimeout(idleTimer);
    reader.releaseLock?.();
  }
}

/** 超级智能体：/api/agent/chat/stream/ */
export async function chatWithAgentStream(
  message: string,
  conversationId: number | undefined,
  callbacks: ChatStreamCallbacks,
  options?: { idleMs?: number; signal?: AbortSignal }
): Promise<void> {
  return chatWithStreamAt(AGENT_STREAM_URL, message, conversationId, callbacks, options);
}

/** AI 面试大师：/api/interview/chat/stream/（独立会话表） */
export async function chatWithInterviewStream(
  message: string,
  conversationId: number | undefined,
  callbacks: ChatStreamCallbacks,
  options?: { idleMs?: number; signal?: AbortSignal }
): Promise<void> {
  return chatWithStreamAt(INTERVIEW_STREAM_URL, message, conversationId, callbacks, options);
}
