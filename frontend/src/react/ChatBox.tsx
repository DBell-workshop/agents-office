import React, { useState, useRef, useEffect, useCallback } from 'react';
import { EventBus } from '../shared/events/EventBus';

// Agent 定义
const AGENTS = [
  { slug: 'dispatcher', name: '调度员', color: '#ff6b6b', role: '任务分配与调度' },
  { slug: 'shopping_guide', name: '导购员', color: '#4ade80', role: '商品推荐与咨询' },
  { slug: 'product_specialist', name: '理货员', color: '#60a5fa', role: '商品数据与库存' },
  { slug: 'data_engineer', name: '数据工程师', color: '#a78bfa', role: '数据管理与上传' },
];

interface ChatMessage {
  id: string;
  role: 'user' | 'agent' | 'system' | 'dispatcher' | 'process';
  agentSlug?: string;
  agentName?: string;
  content: string;
  messageType?: string;
  timestamp: Date;
}

let msgCounter = 0;
function nextMsgId(): string {
  return `msg-${++msgCounter}-${Date.now()}`;
}

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
): Promise<{ messages: ApiMessage[]; agent_movements: Array<{ agent_id: string; room_id: string }> }> {
  const res = await fetch('/api/v1/office/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
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

// ============================================================
// ChatBox 组件
// ============================================================
export const ChatBox: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'sys-welcome',
      role: 'system',
      content: '欢迎来到 AgentsOffice！\n直接输入需求，调度员会自动分配合适的 Agent。',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [showMention, setShowMention] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const [uploading, setUploading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // 维护发送给后端的对话历史
  const historyRef = useRef<{ role: string; content: string }[]>([]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const addMessage = useCallback((msg: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    setMessages((prev) => [...prev, { ...msg, id: nextMsgId(), timestamp: new Date() }]);
  }, []);

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
    addMessage({ role: 'system', content: '调度员正在分析…' });

    try {
      const data = await sendToBackend(trimmed, historyRef.current.slice(-10));

      // 移除"正在分析"提示
      setMessages((prev) => prev.filter((m) => m.content !== '调度员正在分析…'));

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
  }, [input, sending, addMessage]);

  // 文件上传
  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

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
      // 重置 file input
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }, [addMessage]);

  // 键盘事件
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    if (e.key === 'Escape') {
      setShowMention(false);
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

  const filteredAgents = AGENTS.filter(
    (a) => a.name.includes(mentionFilter) || a.slug.includes(mentionFilter),
  );

  const getAgentColor = (slug?: string) =>
    AGENTS.find((a) => a.slug === slug)?.color || '#888';

  return (
    <div style={styles.container}>
      {/* 标题栏 */}
      <div style={styles.header}>AgentsOffice Chat</div>

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
        <label
          title="上传 CSV / Excel 文件"
          style={{
            ...styles.uploadBtn,
            opacity: (uploading || sending) ? 0.5 : 1,
            position: 'relative',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {uploading ? '...' : '\u{1F4CE}'}
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            onChange={handleFileUpload}
            disabled={uploading || sending}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              opacity: 0,
              cursor: 'pointer',
            }}
          />
        </label>
        <input
          ref={inputRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder="输入需求，调度员自动分配"
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
    width: 360,
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    background: 'rgba(10, 10, 30, 0.95)',
    borderLeft: '2px solid #444',
    pointerEvents: 'auto',
    fontFamily: 'monospace',
    color: '#e8e8e8',
  },
  header: {
    padding: '14px 16px',
    borderBottom: '1px solid #444',
    fontSize: '16px',
    color: '#ffd700',
    fontWeight: 'bold',
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
};
