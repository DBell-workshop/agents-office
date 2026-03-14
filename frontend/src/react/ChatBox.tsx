import React, { useState, useRef, useEffect, useCallback } from 'react';
import { EventBus } from '../shared/events/EventBus';
import { loadAgentRegistry, getAgentsCached, type AgentRegistryEntry } from '../shared/agentRegistry';

// Agent 列表辅助函数（从 agentRegistry 动态加载）
function toAgentDef(e: AgentRegistryEntry) {
  return { slug: e.slug, name: e.displayName, color: e.color, role: e.role };
}
function getAgents() { return getAgentsCached().map(toAgentDef); }
function getDirectChatAgents() { return getAgents().filter((a) => a.slug !== 'dispatcher'); }

type ChatMode = 'group' | 'direct';

interface ChatMessage {
  id: string;
  role: 'user' | 'agent' | 'system' | 'dispatcher' | 'process';
  agentSlug?: string;
  agentName?: string;
  content: string;
  messageType?: string;
  timestamp: Date;
}

interface ConversationSummary {
  conversation_id: string;
  title: string;
  message_count: number;
  last_message: string;
  created_at: string;
  updated_at: string;
}

let msgCounter = 0;
function nextMsgId(): string {
  return `msg-${++msgCounter}-${Date.now()}`;
}

const WELCOME_MSG: ChatMessage = {
  id: 'sys-welcome',
  role: 'system',
  content: '欢迎来到 AgentsOffice！\n直接输入需求，调度员会自动分配合适的 Agent。',
  timestamp: new Date(),
};

// ============================================================
// Markdown 表格 + 基本格式解析
// ============================================================
function parseMarkdownContent(content: string): React.ReactNode[] {
  const lines = content.split('\n');
  const result: React.ReactNode[] = [];
  let i = 0;
  let textBuffer: string[] = [];

  const flushText = () => {
    if (textBuffer.length > 0) {
      result.push(
        <span key={`t-${result.length}`} style={{ whiteSpace: 'pre-wrap' }}>
          {formatInlineMarkdown(textBuffer.join('\n'))}
        </span>,
      );
      textBuffer = [];
    }
  };

  while (i < lines.length) {
    // 检测 markdown 表格：当前行含 | 且下一行是分隔行（|----|）
    if (
      lines[i].includes('|') &&
      i + 1 < lines.length &&
      /^\|[\s\-:|]+\|$/.test(lines[i + 1].trim())
    ) {
      flushText();

      // 解析表头
      const headerCells = parseTableRow(lines[i]);
      i += 2; // 跳过分隔行

      // 解析数据行
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
        rows.push(parseTableRow(lines[i]));
        i++;
      }

      result.push(
        <div key={`tbl-${result.length}`} style={tableStyles.wrapper}>
          <table style={tableStyles.table}>
            <thead>
              <tr>
                {headerCells.map((h, ci) => (
                  <th key={ci} style={tableStyles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} style={ri % 2 === 1 ? tableStyles.trAlt : undefined}>
                  {row.map((cell, ci) => (
                    <td key={ci} style={tableStyles.td}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > 0 && (
            <div style={tableStyles.footer}>{rows.length} 行数据</div>
          )}
        </div>,
      );
    } else {
      textBuffer.push(lines[i]);
      i++;
    }
  }

  flushText();
  return result;
}

function parseTableRow(line: string): string[] {
  return line
    .split('|')
    .slice(1, -1) // 去掉首尾空串
    .map((c) => c.trim());
}

function formatInlineMarkdown(text: string): React.ReactNode[] {
  // 处理 **粗体** 和 `代码`
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*(.+?)\*\*|`([^`]+)`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    if (match[2]) {
      parts.push(<strong key={`b-${match.index}`}>{match[2]}</strong>);
    } else if (match[3]) {
      parts.push(
        <code key={`c-${match.index}`} style={{ background: 'rgba(255,255,255,0.1)', padding: '1px 4px', borderRadius: 3 }}>
          {match[3]}
        </code>,
      );
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}

const tableStyles: Record<string, React.CSSProperties> = {
  wrapper: {
    overflowX: 'auto',
    margin: '8px 0',
    border: '1px solid #444',
    borderRadius: 4,
    background: 'rgba(0, 0, 0, 0.3)',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '12px',
    fontFamily: 'monospace',
  },
  th: {
    padding: '6px 8px',
    borderBottom: '2px solid #555',
    textAlign: 'left',
    color: '#ffd700',
    fontWeight: 'bold',
    whiteSpace: 'nowrap',
    background: 'rgba(255, 215, 0, 0.08)',
  },
  td: {
    padding: '5px 8px',
    borderBottom: '1px solid #333',
    color: '#ddd',
    whiteSpace: 'nowrap',
  },
  trAlt: {
    background: 'rgba(255, 255, 255, 0.03)',
  },
  footer: {
    padding: '4px 8px',
    fontSize: '11px',
    color: '#888',
    borderTop: '1px solid #333',
    textAlign: 'right' as const,
  },
};

// ============================================================
// 调用后端 Chat API
// ============================================================
interface ApiMessage {
  role: string;
  agent_slug: string;
  agent_name: string;
  content: string;
  usage?: { input_tokens: number; output_tokens: number; total_tokens: number };
  message_type?: string;
  movement?: { agent_id: string; room_id: string } | null;
}

async function sendToBackend(
  message: string,
  history: { role: string; content: string }[],
  conversationId?: string | null,
): Promise<{
  conversation_id: string;
  messages: ApiMessage[];
  agent_movements: Array<{ agent_id: string; room_id: string }>;
}> {
  const res = await fetch('/api/v1/office/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      history,
      conversation_id: conversationId || undefined,
    }),
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  const envelope = await res.json();
  return envelope.data;
}

async function sendDirectToBackend(
  message: string,
  agentSlug: string,
  history: { role: string; content: string }[],
  conversationId?: string | null,
): Promise<{
  conversation_id: string;
  messages: ApiMessage[];
  agent_movements: Array<{ agent_id: string; room_id: string }>;
}> {
  const res = await fetch('/api/v1/office/chat/direct', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      agent_slug: agentSlug,
      history,
      conversation_id: conversationId || undefined,
    }),
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  const envelope = await res.json();
  return envelope.data;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function formatRelativeTime(isoStr: string): string {
  const d = new Date(isoStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return '刚刚';
  if (diffMin < 60) return `${diffMin} 分钟前`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} 小时前`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `${diffDay} 天前`;
  return d.toLocaleDateString('zh-CN');
}

// ============================================================
// ChatBox 组件
// ============================================================
export const ChatBox: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MSG]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [showMention, setShowMention] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [panelWidth, setPanelWidth] = useState(360);
  const [resizing, setResizing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const resizeStartX = useRef(0);
  const resizeStartW = useRef(360);
  // 维护发送给后端的对话历史
  const historyRef = useRef<{ role: string; content: string }[]>([]);

  // 会话管理
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Agent 列表（从 API 动态加载，fallback 为内置默认）
  const [agents, setAgents] = useState(getAgents());
  const directChatAgents = agents.filter((a) => a.slug !== 'dispatcher');

  useEffect(() => {
    loadAgentRegistry().then(() => setAgents(getAgents()));
  }, []);

  // 聊天模式：群聊 / 私聊
  const [chatMode, setChatMode] = useState<ChatMode>('group');
  const [directAgent, setDirectAgent] = useState<string>(getDirectChatAgents()[0]?.slug || '');
  const [showAgentPicker, setShowAgentPicker] = useState(false);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 广播 ChatBox 宽度变化，让 AgentStatusBar 等组件跟随调整
  useEffect(() => {
    EventBus.emit('chatbox:resize', { width: panelWidth });
  }, [panelWidth]);

  // 加载会话列表
  const loadConversations = useCallback(() => {
    fetch('/api/v1/office/conversations?limit=30')
      .then((r) => r.json())
      .then((envelope) => {
        setConversations(envelope?.data?.conversations || []);
      })
      .catch(() => {});
  }, []);

  // 组件挂载时加载一次
  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const addMessage = useCallback((msg: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    setMessages((prev) => [...prev, { ...msg, id: nextMsgId(), timestamp: new Date() }]);
  }, []);

  // 新建会话
  const startNewConversation = useCallback(() => {
    setConversationId(null);
    setMessages([WELCOME_MSG]);
    historyRef.current = [];
    setShowHistory(false);
    setShowAgentPicker(false);
    inputRef.current?.focus();
  }, []);

  // 切换到历史会话
  const switchToConversation = useCallback(async (convId: string) => {
    setLoadingHistory(true);
    setShowHistory(false);
    try {
      const res = await fetch(`/api/v1/office/conversations/${convId}`);
      const envelope = await res.json();
      const data = envelope?.data;
      if (!data || envelope.error) {
        setLoadingHistory(false);
        return;
      }

      setConversationId(convId);
      historyRef.current = [];

      // 转换后端消息为前端格式
      const loaded: ChatMessage[] = (data.messages || []).map((m: any) => {
        // 重建 historyRef
        if (m.role === 'user') {
          historyRef.current.push({ role: 'user', content: m.content });
        } else if (m.role === 'agent' && m.message_type !== 'process') {
          historyRef.current.push({ role: 'assistant', content: m.content });
        }
        return {
          id: `db-${m.message_id}`,
          role: m.message_type === 'process' ? 'process' : m.role,
          agentSlug: m.agent_slug || undefined,
          agentName: m.agent_name || undefined,
          content: m.content,
          messageType: m.message_type || undefined,
          timestamp: new Date(m.created_at),
        } as ChatMessage;
      });

      setMessages(loaded.length > 0 ? loaded : [WELCOME_MSG]);
    } catch {
      // ignore
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  // 删除会话
  const deleteConversation = useCallback(async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(`/api/v1/office/conversations/${convId}`, { method: 'DELETE' });
      setConversations((prev) => prev.filter((c) => c.conversation_id !== convId));
      // 如果删的是当前会话，新建一个
      if (convId === conversationId) {
        startNewConversation();
      }
    } catch {
      // ignore
    }
  }, [conversationId, startNewConversation]);

  // 发送消息到后端
  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    // 显示用户消息
    addMessage({ role: 'user', content: trimmed });
    setInput('');
    setShowMention(false);
    setSending(true);

    // 加入历史
    historyRef.current.push({ role: 'user', content: trimmed });

    // 显示等待状态
    const directAgentDef = chatMode === 'direct' ? agents.find((a) => a.slug === directAgent) : null;
    const waitingMsg = chatMode === 'direct'
      ? `${directAgentDef?.name || directAgent} 正在思考…`
      : '调度员正在分析…';
    addMessage({ role: 'system', content: waitingMsg });

    try {
      const data = chatMode === 'direct'
        ? await sendDirectToBackend(trimmed, directAgent, historyRef.current.slice(-10), conversationId)
        : await sendToBackend(trimmed, historyRef.current.slice(-10), conversationId);

      // 后端返回的 conversation_id（首次对话时由后端生成）
      if (data.conversation_id && !conversationId) {
        setConversationId(data.conversation_id);
      }

      // 移除等待提示
      setMessages((prev) => prev.filter((m) => m.content !== waitingMsg));

      // 顺序播放消息 — 模拟 Agent 协作过程
      for (let i = 0; i < data.messages.length; i++) {
        const msg = data.messages[i];
        const isProcess = msg.message_type === 'process';

        // 更新 Agent 状态为"工作中"
        if (msg.agent_slug) {
          EventBus.emit('agent:status', { agentSlug: msg.agent_slug, status: 'working' });
        }

        // 触发地图上的 Agent 移动
        if (msg.movement) {
          EventBus.emit('chat:agent-move', {
            agentId: msg.movement.agent_id,
            roomId: msg.movement.room_id,
          });
        }

        // 添加消息到聊天面板
        addMessage({
          role: isProcess ? 'process' : 'agent',
          agentSlug: msg.agent_slug,
          agentName: msg.agent_name,
          content: msg.content,
          messageType: msg.message_type,
        });

        // Agent 头顶显示对话气泡（持续 10 秒）
        if (msg.agent_slug) {
          EventBus.emit('chat:agent-bubble', {
            agentSlug: msg.agent_slug,
            text: msg.content,
            duration: 10000,
          });
        }

        // 上报 Token 用量
        if (msg.usage && msg.agent_slug) {
          EventBus.emit('agent:token-usage', {
            agentSlug: msg.agent_slug,
            tokens: msg.usage.total_tokens || 0,
          });
        }

        // 非 process 消息加入对话历史
        if (!isProcess) {
          historyRef.current.push({ role: 'assistant', content: msg.content });
        }

        // 消息之间延迟，让用户看到协作过程
        if (i < data.messages.length - 1) {
          await delay(2500);
        }
      }

      // 所有 Agent 恢复空闲状态
      for (const msg of data.messages) {
        if (msg.agent_slug) {
          EventBus.emit('agent:status', { agentSlug: msg.agent_slug, status: 'idle' });
        }
      }

      // 通知状态栏从数据库重新同步成本数据
      EventBus.emit('chat:round-complete');

      // 刷新会话列表
      loadConversations();
    } catch (err) {
      // 移除"正在分析"提示
      setMessages((prev) => prev.filter((m) => m.content !== '调度员正在分析…'));
      addMessage({
        role: 'system',
        content: `连接失败: ${err instanceof Error ? err.message : '未知错误'}。请确认后端已启动。`,
      });
    } finally {
      setSending(false);
    }
  }, [input, sending, addMessage, conversationId, loadConversations]);

  // 文件上传（接受 File 对象）
  const uploadFile = useCallback(async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!ext || !['csv', 'xlsx', 'xls'].includes(ext)) {
      addMessage({ role: 'system', content: `不支持的文件格式 .${ext}，请上传 .csv 或 .xlsx 文件` });
      return;
    }

    setUploading(true);
    addMessage({ role: 'system', content: `正在上传 ${file.name}...` });

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/v1/office/upload', {
        method: 'POST',
        body: formData,
      });

      // 移除上传提示
      setMessages((prev) => prev.filter((m) => m.content !== `正在上传 ${file.name}...`));

      if (res.ok) {
        const envelope = await res.json();
        const data = envelope?.data;
        const analysis = data?.analysis;
        const rows = analysis?.total_rows ?? '?';
        const cols = analysis?.total_columns ?? '?';

        addMessage({
          role: 'system',
          content: `文件 ${file.name} 上传成功 (${rows} 行 x ${cols} 列)。\n输入需求让数据工程师帮你处理，例如：\n"帮我分析刚才上传的文件并导入数据库"`,
        });

        // 自动把文件信息加入对话上下文
        historyRef.current.push({
          role: 'user',
          content: `[系统通知] 用户上传了文件: ${file.name}，路径: ${data?.file_path}，${rows} 行 x ${cols} 列`,
        });
      } else {
        const err = await res.json().catch(() => null);
        addMessage({ role: 'system', content: `上传失败: ${err?.detail || res.statusText}` });
      }
    } catch {
      setMessages((prev) => prev.filter((m) => m.content !== `正在上传 ${file.name}...`));
      addMessage({ role: 'system', content: '上传失败: 网络错误' });
    } finally {
      setUploading(false);
    }
  }, [addMessage]);

  // 点击上传按钮 — 动态创建 <input type="file"> 避免 DOM 层级问题
  const triggerFileDialog = useCallback(() => {
    if (uploading || sending) return;
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv,.xlsx,.xls';
    input.style.display = 'none';
    document.body.appendChild(input);
    input.onchange = () => {
      const file = input.files?.[0];
      if (file) uploadFile(file);
      document.body.removeChild(input);
    };
    input.click();
  }, [uploading, sending, uploadFile]);

  // 拖拽上传处理
  const dragCounter = useRef(0);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (e.dataTransfer.types.includes('Files')) {
      setDragging(true);
    }
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current === 0) {
      setDragging(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
    dragCounter.current = 0;

    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
  }, [uploadFile]);

  // 宽度拖拽调整
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setResizing(true);
    resizeStartX.current = e.clientX;
    resizeStartW.current = panelWidth;

    const onMouseMove = (ev: MouseEvent) => {
      // 向左拖 → 宽度增大（因为面板在右侧）
      const delta = resizeStartX.current - ev.clientX;
      const newWidth = Math.max(360, Math.min(window.innerWidth * 0.8, resizeStartW.current + delta));
      setPanelWidth(newWidth);
    };

    const onMouseUp = () => {
      setResizing(false);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }, [panelWidth]);

  // 键盘事件
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    if (e.key === 'Escape') {
      setShowMention(false);
      setShowHistory(false);
    }
  };

  // 输入变化 — 检测 @
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInput(val);

    const lastAt = val.lastIndexOf('@');
    if (lastAt >= 0) {
      const afterAt = val.slice(lastAt + 1);
      if (!afterAt.includes(' ')) {
        setShowMention(true);
        setMentionFilter(afterAt);
        return;
      }
    }
    setShowMention(false);
  };

  // 插入 @提及
  const insertMention = (agentName: string) => {
    const lastAt = input.lastIndexOf('@');
    const newInput = input.slice(0, lastAt) + `@${agentName} `;
    setInput(newInput);
    setShowMention(false);
    inputRef.current?.focus();
  };

  const filteredAgents = agents.filter(
    (a) => a.name.includes(mentionFilter) || a.slug.includes(mentionFilter),
  );

  const directAgentDef = agents.find((a) => a.slug === directAgent);

  const getAgentColor = (slug?: string) =>
    agents.find((a) => a.slug === slug)?.color || '#888';

  // 打开历史面板时刷新列表
  const toggleHistory = useCallback(() => {
    const next = !showHistory;
    setShowHistory(next);
    if (next) loadConversations();
  }, [showHistory, loadConversations]);

  return (
    <div
      style={{ ...styles.container, width: panelWidth }}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* 左侧拖拽调整宽度手柄 */}
      <div
        style={{
          ...styles.resizeHandle,
          ...(resizing ? { background: 'rgba(74, 222, 128, 0.4)' } : {}),
        }}
        onMouseDown={handleResizeStart}
      />
      {/* 拖拽上传遮罩 */}
      {dragging && (
        <div style={styles.dropOverlay}>
          <div style={styles.dropIcon}>📂</div>
          <div style={styles.dropText}>松开鼠标上传文件</div>
          <div style={styles.dropHint}>支持 .csv / .xlsx / .xls</div>
        </div>
      )}

      {/* 标题栏 */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <button
            onClick={toggleHistory}
            title="会话历史"
            style={{
              ...styles.headerBtn,
              color: showHistory ? '#ffd700' : '#888',
            }}
          >
            {showHistory ? '✕' : '☰'}
          </button>
          {chatMode === 'group' ? (
            <span style={{ color: '#ffd700', fontWeight: 'bold' }}>AgentsOffice Chat</span>
          ) : (
            <span
              style={{ color: directAgentDef?.color || '#ffd700', fontWeight: 'bold', cursor: 'pointer' }}
              onClick={() => setShowAgentPicker(!showAgentPicker)}
            >
              与 {directAgentDef?.name} 私聊 ▾
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {/* 群聊/私聊切换 */}
          <button
            onClick={() => {
              const next: ChatMode = chatMode === 'group' ? 'direct' : 'group';
              setChatMode(next);
              setShowAgentPicker(false);
              // 切换模式时新建会话
              startNewConversation();
              if (next === 'direct') {
                setMessages([{
                  id: 'sys-direct',
                  role: 'system',
                  content: `进入私聊模式。你现在直接和${agents.find(a => a.slug === directAgent)?.name || directAgent}对话，消息不经过调度员。`,
                  timestamp: new Date(),
                }]);
              }
            }}
            title={chatMode === 'group' ? '切换到私聊' : '切换到群聊'}
            style={{
              ...styles.headerBtn,
              fontSize: '13px',
              color: chatMode === 'direct' ? '#ffd700' : '#888',
            }}
          >
            {chatMode === 'group' ? '👤' : '👥'}
          </button>
          <button
            onClick={startNewConversation}
            title="新建对话"
            style={styles.headerBtn}
          >
            +
          </button>
        </div>
      </div>

      {/* 私聊 Agent 选择器 */}
      {showAgentPicker && chatMode === 'direct' && (
        <div style={{
          background: '#2a2218', borderBottom: '1px solid #44382a',
          padding: '8px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4,
        }}>
          {directChatAgents.map((a) => (
            <button
              key={a.slug}
              onClick={() => {
                setDirectAgent(a.slug);
                setShowAgentPicker(false);
                startNewConversation();
                setMessages([{
                  id: 'sys-direct',
                  role: 'system',
                  content: `进入私聊模式。你现在直接和${a.name}对话，消息不经过调度员。`,
                  timestamp: new Date(),
                }]);
              }}
              style={{
                background: a.slug === directAgent ? 'rgba(255, 215, 0, 0.15)' : 'rgba(255,255,255,0.05)',
                border: a.slug === directAgent ? '1px solid #ffd700' : '1px solid #44382a',
                borderRadius: 4, padding: '6px 8px', cursor: 'pointer', textAlign: 'left',
              }}
            >
              <span style={{ color: a.color, fontSize: '12px', fontWeight: 'bold' }}>{a.name}</span>
              <span style={{ color: '#888', fontSize: '10px', marginLeft: 4 }}>{a.role}</span>
            </button>
          ))}
        </div>
      )}

      {/* 会话历史面板（覆盖在消息列表上方） */}
      {showHistory && (
        <div style={styles.historyPanel}>
          <div style={styles.historyHeader}>
            <span>会话历史</span>
            <span style={{ color: '#888', fontSize: 12 }}>{conversations.length} 个会话</span>
          </div>
          <div style={styles.historyList}>
            {conversations.length === 0 ? (
              <div style={styles.historyEmpty}>暂无历史会话</div>
            ) : (
              conversations.map((conv) => (
                <div
                  key={conv.conversation_id}
                  onClick={() => switchToConversation(conv.conversation_id)}
                  style={{
                    ...styles.historyItem,
                    ...(conv.conversation_id === conversationId ? styles.historyItemActive : {}),
                  }}
                  onMouseEnter={(e) => {
                    if (conv.conversation_id !== conversationId) {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (conv.conversation_id !== conversationId) {
                      e.currentTarget.style.background = 'transparent';
                    }
                  }}
                >
                  <div style={styles.historyItemMain}>
                    <div style={styles.historyTitle}>
                      {conv.title || '新对话'}
                    </div>
                    <div style={styles.historyMeta}>
                      <span>{conv.message_count} 条消息</span>
                      <span>{formatRelativeTime(conv.updated_at)}</span>
                    </div>
                    {conv.last_message && (
                      <div style={styles.historyPreview}>
                        {conv.last_message}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={(e) => deleteConversation(conv.conversation_id, e)}
                    title="删除会话"
                    style={styles.historyDeleteBtn}
                  >
                    ✕
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* 加载中提示 */}
      {loadingHistory && (
        <div style={styles.loadingOverlay}>
          加载历史消息中...
        </div>
      )}

      {/* 消息列表 */}
      <div style={styles.messageList}>
        {messages.map((msg) => (
          <div key={msg.id} style={{ marginBottom: 10 }}>
            {msg.role === 'system' ? (
              <div style={styles.systemMsg}>{msg.content}</div>
            ) : msg.role === 'user' ? (
              <div>
                <div style={styles.senderLabel}>你</div>
                <div style={styles.userBubble}>{msg.content}</div>
              </div>
            ) : msg.role === 'process' ? (
              <div style={styles.processMsg}>
                <span style={{ color: getAgentColor(msg.agentSlug), fontWeight: 'bold' }}>
                  {msg.agentName}
                </span>
                {' '}{msg.content}
              </div>
            ) : (
              <div>
                <div style={{ ...styles.senderLabel, color: getAgentColor(msg.agentSlug) }}>
                  {msg.agentName}
                </div>
                <div
                  style={{
                    ...styles.agentBubble,
                    borderColor: `${getAgentColor(msg.agentSlug)}44`,
                  }}
                >
                  {parseMarkdownContent(msg.content)}
                </div>
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* @提及下拉 */}
      {showMention && filteredAgents.length > 0 && (
        <div style={styles.mentionMenu}>
          {filteredAgents.map((agent) => (
            <div
              key={agent.slug}
              onClick={() => insertMention(agent.name)}
              style={styles.mentionItem}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = 'rgba(255,255,255,0.1)')
              }
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <span style={{ color: agent.color }}>@{agent.name}</span>
              <span style={{ color: '#888', fontSize: '12px' }}>{agent.role}</span>
            </div>
          ))}
        </div>
      )}

      {/* 输入区 */}
      <div style={styles.inputArea}>
        <button
          type="button"
          title="上传 CSV / Excel 文件（也可拖拽文件到聊天区）"
          onClick={triggerFileDialog}
          disabled={uploading || sending}
          style={{
            ...styles.uploadBtn,
            opacity: (uploading || sending) ? 0.5 : 1,
          }}
        >
          {uploading ? '⏳' : '📎'}
        </button>
        <input
          ref={inputRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={chatMode === 'direct' ? `和${directAgentDef?.name || ''}说点什么...` : '输入需求，调度员自动分配'}
          disabled={sending}
          style={{
            ...styles.input,
            opacity: sending ? 0.5 : 1,
          }}
        />
        <button
          onClick={handleSend}
          disabled={sending}
          style={{
            ...styles.sendBtn,
            opacity: sending ? 0.5 : 1,
          }}
        >
          {sending ? '…' : '发送'}
        </button>
      </div>
    </div>
  );
};

// ============================================================
// 内联样式 — Retro Terminal 风格
// ============================================================
const styles: Record<string, React.CSSProperties> = {
  container: {
    position: 'absolute',
    top: 0,
    right: 0,
    width: 360, // 默认值，运行时由 panelWidth 覆盖
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    background: 'rgba(10, 10, 30, 0.95)',
    borderLeft: '2px solid #444',
    pointerEvents: 'auto',
    fontFamily: 'monospace',
    color: '#e8e8e8',
  },
  resizeHandle: {
    position: 'absolute' as const,
    top: 0,
    left: -3,
    width: 6,
    height: '100%',
    cursor: 'col-resize',
    background: 'transparent',
    zIndex: 200,
    transition: 'background 0.15s',
  },
  header: {
    padding: '10px 12px',
    borderBottom: '1px solid #444',
    fontSize: '16px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexShrink: 0,
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  headerBtn: {
    background: 'none',
    border: 'none',
    color: '#888',
    fontSize: 18,
    cursor: 'pointer',
    fontFamily: 'monospace',
    padding: '2px 6px',
    borderRadius: 3,
    lineHeight: 1,
  },
  // 会话历史面板
  historyPanel: {
    position: 'absolute' as const,
    top: 44,
    left: 0,
    right: 0,
    bottom: 56,
    background: 'rgba(8, 8, 24, 0.98)',
    zIndex: 150,
    display: 'flex',
    flexDirection: 'column' as const,
    borderBottom: '1px solid #444',
  },
  historyHeader: {
    padding: '10px 14px',
    borderBottom: '1px solid #333',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: 14,
    color: '#ffd700',
    fontWeight: 'bold',
    flexShrink: 0,
  },
  historyList: {
    flex: 1,
    overflowY: 'auto' as const,
    padding: '6px 8px',
  },
  historyEmpty: {
    textAlign: 'center' as const,
    color: '#666',
    padding: '40px 0',
    fontSize: 13,
  },
  historyItem: {
    padding: '10px 10px',
    borderRadius: 4,
    cursor: 'pointer',
    marginBottom: 2,
    display: 'flex',
    alignItems: 'flex-start',
    gap: 6,
    transition: 'background 0.1s',
  },
  historyItemActive: {
    background: 'rgba(255, 215, 0, 0.1)',
    borderLeft: '3px solid #ffd700',
  },
  historyItemMain: {
    flex: 1,
    minWidth: 0,
  },
  historyTitle: {
    fontSize: 13,
    fontWeight: 'bold',
    color: '#ddd',
    overflow: 'hidden' as const,
    textOverflow: 'ellipsis' as const,
    whiteSpace: 'nowrap' as const,
  },
  historyMeta: {
    fontSize: 11,
    color: '#777',
    marginTop: 3,
    display: 'flex',
    gap: 10,
  },
  historyPreview: {
    fontSize: 12,
    color: '#999',
    marginTop: 3,
    overflow: 'hidden' as const,
    textOverflow: 'ellipsis' as const,
    whiteSpace: 'nowrap' as const,
  },
  historyDeleteBtn: {
    background: 'none',
    border: 'none',
    color: '#555',
    fontSize: 12,
    cursor: 'pointer',
    padding: '2px 4px',
    borderRadius: 3,
    flexShrink: 0,
    marginTop: 2,
  },
  loadingOverlay: {
    textAlign: 'center' as const,
    color: '#ffd700',
    padding: '12px 0',
    fontSize: 13,
    borderBottom: '1px solid #333',
  },
  messageList: {
    flex: 1,
    overflowY: 'auto',
    padding: '10px 14px',
  },
  systemMsg: {
    fontSize: '13px',
    color: '#999',
    textAlign: 'center' as const,
    padding: '6px 0',
    whiteSpace: 'pre-wrap' as const,
  },
  processMsg: {
    fontSize: '12px',
    color: '#aaa',
    fontStyle: 'italic',
    padding: '4px 10px',
    borderLeft: '2px solid #555',
    background: 'rgba(255, 255, 255, 0.03)',
  },
  senderLabel: {
    fontSize: '12px',
    color: '#bbb',
    marginBottom: 3,
    fontWeight: 'bold',
  },
  userBubble: {
    background: 'rgba(74, 222, 128, 0.15)',
    border: '1px solid rgba(74, 222, 128, 0.35)',
    borderRadius: '4px',
    padding: '10px 12px',
    fontSize: '14px',
    lineHeight: '1.6',
    whiteSpace: 'pre-wrap' as const,
  },
  agentBubble: {
    background: 'rgba(255, 255, 255, 0.06)',
    border: '1px solid rgba(255, 255, 255, 0.15)',
    borderRadius: '4px',
    padding: '10px 12px',
    fontSize: '14px',
    lineHeight: '1.6',
    whiteSpace: 'pre-wrap' as const,
  },
  mentionMenu: {
    padding: '6px',
    background: 'rgba(20, 20, 50, 0.98)',
    border: '1px solid #555',
    borderRadius: '4px',
    margin: '0 14px',
  },
  mentionItem: {
    padding: '8px 10px',
    cursor: 'pointer',
    fontSize: '14px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderRadius: '3px',
  },
  inputArea: {
    padding: '12px 14px',
    borderTop: '1px solid #444',
    display: 'flex',
    gap: '8px',
    flexShrink: 0,
  },
  input: {
    flex: 1,
    background: 'rgba(255, 255, 255, 0.1)',
    border: '1px solid #555',
    borderRadius: '4px',
    color: '#f0f0f0',
    padding: '10px 12px',
    fontFamily: 'monospace',
    fontSize: '14px',
    outline: 'none',
  },
  sendBtn: {
    background: 'rgba(74, 222, 128, 0.25)',
    border: '1px solid #4ade80',
    borderRadius: '4px',
    color: '#4ade80',
    padding: '10px 16px',
    cursor: 'pointer',
    fontFamily: 'monospace',
    fontSize: '14px',
    fontWeight: 'bold',
  },
  uploadBtn: {
    background: 'rgba(167, 139, 250, 0.2)',
    border: '1px solid #a78bfa',
    borderRadius: '4px',
    color: '#a78bfa',
    padding: '10px 12px',
    cursor: 'pointer',
    fontFamily: 'monospace',
    fontSize: '16px',
    flexShrink: 0,
  },
  dropOverlay: {
    position: 'absolute' as const,
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    background: 'rgba(167, 139, 250, 0.15)',
    border: '3px dashed #a78bfa',
    borderRadius: '0',
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 100,
    pointerEvents: 'none' as const,
  },
  dropIcon: {
    fontSize: '48px',
    marginBottom: '12px',
  },
  dropText: {
    fontSize: '16px',
    color: '#a78bfa',
    fontWeight: 'bold',
    fontFamily: 'monospace',
  },
  dropHint: {
    fontSize: '12px',
    color: '#888',
    marginTop: '6px',
    fontFamily: 'monospace',
  },
};
